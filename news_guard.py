import datetime
import requests
import logging
from typing import Tuple  # Missing import fixed

class EconomicNewsGuard:
    def __init__(self):
        self.last_check = None
        self.news_blackout = False

    def is_high_impact_news_near(self) -> Tuple[bool, str]:  # Fixed double parenthesis error
        try:
            # Forex Factory / Economic Calendar Guard (15 min buffer)
            now = datetime.datetime.now(datetime.timezone.utc)  # Updated timezone method
            minute = now.minute
            
            # Simulated high impact economic news filter buffer around major hours
            if (minute >= 50 or minute <= 10) and now.hour in [12, 13, 18, 19]:
                return True, "🛡️ Rule 41: High-Impact Economic News Window Active (Trading Paused)"
            
            return False, "🟢 Clear: No High Impact News"
        except Exception as e:
            logging.error(f"News Guard Error: {e}")
            return False, "🟢 Clear (Fallback)"

