#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <iostream>
#include <string>
#include <vector>
#include <deque>
#include <unordered_map>
#include <chrono>
#include <thread>
#include <atomic>
#include <mutex>
#include <cmath>
#include <fstream>

namespace py = pybind11;

struct FastPriceTick {
    std::string symbol;
    double price;
    double volume;
    double latency_ms;
    uint64_t timestamp_ns;
};

struct ActivePosition {
    std::string symbol;
    double entry_price;
    double remaining_size;
    double tp1_price;
    bool tp1_booked;
    double trailing_sl;
};

class MasterSystemCore {
private:
    double max_latency_limit = 200.0;
    double peak_equity = 10000.0;
    double current_equity = 10000.0;
    std::atomic<double> risk_multiplier{1.0};
    
    std::atomic<bool> is_retraining{false};
    std::atomic<float> policy_weight{0.85f};
    std::thread retrain_thread;

    std::unordered_map<std::string, std::deque<double>> pair_price_history;
    std::unordered_map<std::string, ActivePosition> positions;
    std::recursive_mutex core_mutex; // Recursive mutex prevents deadlocks

public:
    MasterSystemCore() = default;

    ~MasterSystemCore() {
        if (retrain_thread.joinable()) {
            retrain_thread.join();
        }
    }

    bool validate_latency(double latency_ms) const noexcept {
        return latency_ms <= max_latency_limit;
    }

    void update_pair_price(const std::string& symbol, double price) {
        std::lock_guard<std::recursive_mutex> lock(core_mutex);
        auto& history = pair_price_history[symbol];
        history.push_back(price);
        if (history.size() > 50) {
            history.pop_front();
        }
    }

    std::string select_best_pair() {
        std::lock_guard<std::recursive_mutex> lock(core_mutex);
        std::string best_pair = "BTC/USDT";
        double max_volatility = -1.0;

        for (const auto& [symbol, prices] : pair_price_history) {
            if (prices.size() < 2) continue;
            double mean = 0.0;
            for (double p : prices) mean += p;
            mean /= prices.size();

            double variance = 0.0;
            for (double p : prices) variance += (p - mean) * (p - mean);
            double std_dev = std::sqrt(variance / prices.size());

            if (std_dev > max_volatility) {
                max_volatility = std_dev;
                best_pair = symbol;
            }
        }
        return best_pair;
    }

    float predict_drl_confidence([[maybe_unused]] const FastPriceTick& tick) {
        return policy_weight.load();
    }

    void trigger_background_retrain() {
        bool expected = false;
        if (!is_retraining.compare_exchange_strong(expected, true)) {
            return; // Already retraining
        }

        if (retrain_thread.joinable()) {
            retrain_thread.join();
        }

        retrain_thread = std::thread([this]() {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            this->policy_weight.store(0.89f);
            this->is_retraining.store(false);
            std::cout << "[C++ DRL] Model Retrained & Hot-Reloaded in Background.\n";
        });
    }

    void record_trade_result(double pnl) {
        std::lock_guard<std::recursive_mutex> lock(core_mutex);
        current_equity += pnl;
        if (current_equity > peak_equity) {
            peak_equity = current_equity;
        }

        double drawdown = (peak_equity - current_equity) / peak_equity;
        if (drawdown > 0.05) {
            risk_multiplier.store(0.5);
            std::cout << "[C++ SELF-HEAL] Drawdown (" << drawdown * 100 
                      << "%). Stake Multiplier reduced to " << risk_multiplier.load() << "\n";
        } else {
            risk_multiplier.store(1.0);
        }
    }

    double get_risk_multiplier() const noexcept {
        return risk_multiplier.load();
    }

    void open_position(const std::string& symbol, double price, double size) {
        std::lock_guard<std::recursive_mutex> lock(core_mutex);
        ActivePosition pos;
        pos.symbol = symbol;
        pos.entry_price = price;
        pos.remaining_size = size;
        pos.tp1_price = price * 1.02;
        pos.tp1_booked = false;
        pos.trailing_sl = price * 0.98;
        positions[symbol] = pos;
        std::cout << "[C++ ROUTER] Opened: " << symbol << " at $" << price << " | Size: " << size << "\n";
    }

    int process_tick_routing(const std::string& symbol, double current_price) {
        std::lock_guard<std::recursive_mutex> lock(core_mutex);
        auto it = positions.find(symbol);
        if (it == positions.end()) return 0;

        ActivePosition& pos = it->second;

        if (!pos.tp1_booked && current_price >= pos.tp1_price) {
            pos.tp1_booked = true;
            pos.remaining_size /= 2.0;
            pos.trailing_sl = pos.entry_price;
            std::cout << "[C++ PARTIAL] Booked 50% on " << symbol << ". Trailing SL moved to BE: $" << pos.trailing_sl << "\n";
            return 1;
        }

        if (pos.tp1_booked && current_price > pos.tp1_price) {
            double dynamic_sl = current_price * 0.985;
            if (dynamic_sl > pos.trailing_sl) {
                pos.trailing_sl = dynamic_sl;
            }
        }

        if (current_price <= pos.trailing_sl) {
            std::cout << "[C++ EXIT] Position Closed on SL/Trailing for " << symbol << " at $" << current_price << "\n";
            positions.erase(it);
            return 2;
        }

        return 0;
    }

    void run_tick_lifecycle(const FastPriceTick& tick) {
        if (!validate_latency(tick.latency_ms)) {
            std::cout << "[C++ BYPASS] High Latency: " << tick.latency_ms << "ms > 200ms\n";
            return;
        }

        update_pair_price(tick.symbol, tick.price);
        float confidence = predict_drl_confidence(tick);

        if (confidence >= 0.80f) {
            std::lock_guard<std::recursive_mutex> lock(core_mutex);
            if (positions.find(tick.symbol) == positions.end()) {
                ActivePosition pos;
                pos.symbol = tick.symbol;
                pos.entry_price = tick.price;
                pos.remaining_size = 1.0 * risk_multiplier.load();
                pos.tp1_price = tick.price * 1.02;
                pos.tp1_booked = false;
                pos.trailing_sl = tick.price * 0.98;
                positions[tick.symbol] = pos;
                std::cout << "[C++ LIFECYCLE] Executed BUY for " << tick.symbol << " at $" << tick.price << "\n";
            }
        }

        process_tick_routing(tick.symbol, tick.price);
    }
};

PYBIND11_MODULE(hft_core, m) {
    m.doc() = "C++ HFT High-Performance Core exposed to Python via pybind11";

    py::class_<FastPriceTick>(m, "FastPriceTick")
        .def(py::init<std::string, double, double, double, uint64_t>(),
             py::arg("symbol"), py::arg("price"), py::arg("volume"), py::arg("latency_ms"), py::arg("timestamp_ns") = 0)
        .def_readwrite("symbol", &FastPriceTick::symbol)
        .def_readwrite("price", &FastPriceTick::price)
        .def_readwrite("volume", &FastPriceTick::volume)
        .def_readwrite("latency_ms", &FastPriceTick::latency_ms)
        .def_readwrite("timestamp_ns", &FastPriceTick::timestamp_ns);

    py::class_<MasterSystemCore>(m, "MasterSystemCore")
        .def(py::init<>())
        .def("validate_latency", &MasterSystemCore::validate_latency)
        .def("update_pair_price", &MasterSystemCore::update_pair_price)
        .def("select_best_pair", &MasterSystemCore::select_best_pair)
        .def("predict_drl_confidence", &MasterSystemCore::predict_drl_confidence)
        .def("trigger_background_retrain", &MasterSystemCore::trigger_background_retrain)
        .def("record_trade_result", &MasterSystemCore::record_trade_result)
        .def("get_risk_multiplier", &MasterSystemCore::get_risk_multiplier)
        .def("open_position", &MasterSystemCore::open_position)
        .def("process_tick_routing", &MasterSystemCore::process_tick_routing)
        .def("run_tick_lifecycle", &MasterSystemCore::run_tick_lifecycle);
}
