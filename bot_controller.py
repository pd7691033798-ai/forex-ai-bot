import asyncio
import logging
import signal
import time

try:
    import hft_core
except ImportError:
    raise ImportError(
        "hft_core C++ extension not found. Make sure 'pip install -e .' was executed."
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)

class TradingBotController:
    def __init__(self):
        self.engine = hft_core.MasterSystemCore()
        self.is_running = True
        logging.info("C++ Core Engine initialized successfully.")

    def ingest_tick(self, symbol: str, price: float, volume: float, latency_ms: float):
        t_start = time.perf_counter_ns()
        tick = hft_core.FastPriceTick(symbol, price, volume, latency_ms, 0)
        self.engine.run_tick_lifecycle(tick)
        t_end = time.perf_counter_ns()
        duration_us = (t_end - t_start) / 1000.0
        logging.info(f"[SPEED] Ingestion latency: {duration_us:.2f} µs")

    async def run_hourly_maintenance(self):
        while self.is_running:
            try:
                await asyncio.sleep(3600)
                logging.info("[MAINTENANCE] Running Diagnostic Health Check & DRL Retraining...")
                self.engine.trigger_background_retrain()
            except asyncio.CancelledError:
                break

    async def start(self):
        logging.info("Starting Master Trading Bot Loop...")
        maintenance_task = asyncio.create_task(self.run_hourly_maintenance())

        # Test Mock Ticks
        self.ingest_tick("BTC/USDT", 65000.0, 2.5, 12.0)
        await asyncio.sleep(1)

        self.ingest_tick("BTC/USDT", 66350.0, 1.8, 8.5)
        await asyncio.sleep(1)

        self.ingest_tick("BTC/USDT", 64500.0, 1.2, 5.0)
        await asyncio.sleep(1)

        best_pair = self.engine.select_best_pair()
        logging.info(f"[VOLATILITY PAIR] Selected Pair: {best_pair}")

        try:
            while self.is_running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            logging.info("Shutting down bot gracefully...")
            self.is_running = False
            maintenance_task.cancel()
            await asyncio.gather(maintenance_task, return_exceptions=True)

if __name__ == "__main__":
    bot = TradingBotController()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def handle_shutdown(signum, frame):
        logging.info(f"Received signal {signum}, initiating shutdown...")
        bot.is_running = False

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        loop.run_until_complete(bot.start())
    finally:
        loop.close()
          
