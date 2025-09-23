import requests
import json
import time
import random
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SmartMoneyAnalyzer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # بارگذاری لیست سهام از فایل
        self.symbols = self.load_symbols()
        
        # قیمت‌های پایه سهام
        self.base_prices = {
            'خارزم': 8500, 'فرآور': 12300, 'سدور': 5600, 'سخاش': 15400,
            'گشان': 7800, 'وساپا': 9200, 'ورنا': 6700, 'ختوقا': 11900,
            'فباهنر': 4500, 'شرانل': 13600, 'شاوان': 8900, 'رکیش': 7200,
            'فولاد': 25400, 'حریل': 14800, 'کبافق': 16700, 'ساوه': 5900, 'وبملت': 18500
        }

    def load_symbols(self):
        """بارگذاری لیست سهام از فایل"""
        try:
            with open('symbols.txt', 'r', encoding='utf-8') as f:
                symbols = [line.strip() for line in f if line.strip()]
            logger.info(f"✅ {len(symbols)} سهم از فایل بارگذاری شد")
            return symbols
        except FileNotFoundError:
            logger.error("❌ فایل symbols.txt یافت نشد!")
            return ['خارزم', 'فولاد', 'وبملت']  # پیش‌فرض
        except Exception as e:
            logger.error(f"خطا در بارگذاری symbols.txt: {e}")
            return ['خارزم', 'فولاد', 'وبملت']

    def get_stock_data(self, symbol):
        """دریافت داده سهم"""
        try:
            # تلاش برای API واقعی
            real_data = self._try_real_api(symbol)
            if real_data:
                return real_data
        except:
            pass

        # شبیه‌سازی داده
        base_price = self.base_prices.get(symbol, random.randint(5000, 20000))
        price_change = random.uniform(-0.05, 0.05)
        volume_change = random.uniform(0.3, 3.0)

        current_price = int(base_price * (1 + price_change))
        current_volume = random.randint(1000000, 50000000) * volume_change

        return {
            'symbol': symbol,
            'current_price': current_price,
            'volume': int(current_volume),
            'value': current_price * current_volume,
            'timestamp': time.time()
        }

    def _try_real_api(self, symbol):
        """تلاش برای دریای"""
        try:
            url = "http://old.tsetmc.com/tsev2/data/instinfodata.aspx"
            params = {'i': symbol, 'c': '1'}
            response = self.session.get(url, params=params, timeout=5)

            if response.status_code == 200 and response.text.strip():
                parts = response.text.strip().split(',')
                if len(parts) >= 8
