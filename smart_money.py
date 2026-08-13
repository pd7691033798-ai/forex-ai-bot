Import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Any

class SmartMoneyEngine:
    def __init__(self):
        pass

    def detect_order_blocks(self, prices: List[float]) -> Tuple[bool, str]:
        if len(prices) < 20:
            return False, "Insufficient Data for OB"
        
        # Calculate Swing Highs/Lows and Order Blocks
        df = pd.DataFrame({'close': prices})
        df['returns'] = df['close'].pct_change()
        
        recent_std = df['returns'].tail(10).std()
        last_return = df['returns'].iloc[-1]

        # Order Block Logic: Institutional Push validation
        if abs(last_return) > (recent_std * 1.5):
            direction = "BULLISH_OB" if last_return > 0 else "BEARISH_OB"
            return True, direction
        return False, "NO_OB"

    def detect_fvg(self, prices: List[float]) -> Tuple[bool, str]:
        if len(prices) < 3:
            return False, "NO_FVG"
        
        # 3-Candle Imbalance / Fair Value Gap Logic
        c1, c3 = prices[-3], prices[-1]
        gap_pct = abs(c3 - c1) / c1 * 100.0

        if gap_pct > 0.05:  # Valid Institutional Imbalance Gap
            return True, "FVG_DETECTED"
        return False, "NO_FVG"

    def evaluate_smart_money_rules(self, prices_1h: List[float], prices_15m: List[float], spread: float) -> Tuple[bool, str, float]:
        # Spread Guard
        if spread > 1.5:
            return False, "High Spread Detected", 0.0

        ob_found, ob_type = self.detect_order_blocks(prices_1h)
        fvg_found, fvg_type = self.detect_fvg(prices_15m)

        # Institutional Footprint Filter
        if not ob_found and not fvg_found:
            return False, "SMC Block: No Institutional Order Block or FVG Zone", 0.0

        confidence_boost = 0.0
        if ob_found: confidence_boost += 15.0
        if fvg_found: confidence_boost += 10.0

        return True, "SMC Institutional Confluence Clear", confidence_boost
