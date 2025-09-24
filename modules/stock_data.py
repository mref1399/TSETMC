# modules/stock_data.py
import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class StockDataFetcher:
    def __init__(self):
        self.base_url = "http://old.tsetmc.com/tsev2/data"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_full_data(self, symbol: str) -> Optional[Dict]:
        """دریافت همه داده‌های یک نماد از TSETMC"""
        try:
            # داده روز جاری
            res_info = self.session.get(
                f"{self.base_url}/InstInfoData.aspx?i={symbol}",
                timeout=10
            )
            info_data = res_info.text.strip()

            # تاریخچه معاملات
            res_trade = self.session.get(
                f"{self.base_url}/InstTradeHistory.aspx?i={symbol}&Top=5&A=0",
                timeout=10
            )
            trade_data = res_trade.text.strip()

            # حقیقی-حقوقی
            res_legal = self.session.get(
                f"{self.base_url}/ClientTypeHistory.aspx?i={symbol}",
                timeout=10
            )
            legal_data = res_legal.text.strip()

            return {
                'symbol': symbol,
                'info': info_data,
                'trade_history': trade_data,
                'legal_history': legal_data
            }

        except Exception as e:
            logger.error(f"خطا در گرفتن داده {symbol}: {str(e)}")
            return None

    def fetch_all_from_file(self, file_path: str = 'symbols.txt'):
        """خواندن نمادها از فایل و دریافت داده‌ها"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                symbols = [line.strip() for line in f.readlines() if line.strip()]

            results = []
            for symbol in symbols:
                data = self.get_full_data(symbol)
                if data:
                    results.append(data)

            return results

        except FileNotFoundError:
            logger.error("فایل symbols.txt پیدا نشد.")
            return []
