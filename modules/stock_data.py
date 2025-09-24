# modules/stock_data.py
import requests
import logging
import os
from typing import Dict, Optional, List
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی
load_dotenv()

logger = logging.getLogger(__name__)

class StockDataFetcher:
    def __init__(self):
        self.api_key = os.getenv('BRSAPI_KEY')
        if not self.api_key:
            raise ValueError("BRSAPI_KEY در فایل .env تنظیم نشده است")
        
        self.base_url = "https://BrsApi.ir/Api/Tsetmc"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/106.0.0.0',
            'Accept': 'application/json, text/plain, */*'
        })

    def get_all_symbols(self) -> Optional[Dict]:
        """دریافت همه نمادها از BrsApi"""
        try:
            url = f"{self.base_url}/AllSymbols.php"
            params = {'key': self.api_key}
            
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                return {
                    'status': 'success',
                    'raw_data': response.text,
                    'json_data': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
                }
            else:
                logger.error(f"خطا در دریافت همه نمادها: {response.status_code}")
                return {
                    'status': 'error',
                    'error_code': response.status_code,
                    'raw_data': response.text
                }
        except Exception as e:
            logger.error(f"خطا در اتصال به API: {str(e)}")
            return None

    def get_symbol_data(self, symbol: str) -> Optional[Dict]:
        """دریافت اطلاعات یک نماد خاص"""
        try:
            # احتمالاً endpoint‌های مختلف برای اطلاعات مختلف وجود داشته باشد
            endpoints = {
                'info': f"{self.base_url}/SymbolInfo.php",
                'trade': f"{self.base_url}/TradeHistory.php", 
                'legal': f"{self.base_url}/LegalData.php"
            }
            
            result = {'symbol': symbol}
            
            for data_type, url in endpoints.items():
                try:
                    params = {'key': self.api_key, 'symbol': symbol}
                    response = self.session.get(url, params=params, timeout=15)
                    
                    if response.status_code == 200:
                        result[data_type] = {
                            'raw_data': response.text,
                            'json_data': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
                        }
                    else:
                        result[data_type] = {
                            'error': f"HTTP {response.status_code}",
                            'raw_data': response.text
                        }
                except Exception as e:
                    result[data_type] = {
                        'error': str(e),
                        'raw_data': ''
                    }
            
            return result
            
        except Exception as e:
            logger.error(f"خطا در گرفتن اطلاعات {symbol}: {str(e)}")
            return None

    def fetch_symbols_from_file(self, file_path: str = 'symbols.txt') -> List[Dict]:
        """خواندن نمادها از فایل و دریافت اطلاعات هر کدام"""
        try:
            # خواندن لیست نمادها
            with open(file_path, 'r', encoding='utf-8') as f:
                symbols = [line.strip() for line in f if line.strip()]
            
            logger.info(f"📋 خواندن {len(symbols)} نماد از فایل {file_path}")
            
            results = []
            for i, symbol in enumerate(symbols, 1):
                logger.info(f"🔄 دریافت داده‌های {symbol} ({i}/{len(symbols)})")
                
                data = self.get_symbol_data(symbol)
                if data:
                    results.append(data)
                
                # تاخیر کمی برای جلوگیری از محدودیت API
                import time
                time.sleep(0.5)
            
            return results
            
        except FileNotFoundError:
            logger.error(f"❌ فایل {file_path} پیدا نشد")
            return []
        except Exception as e:
            logger.error(f"❌ خطا در پردازش فایل: {str(e)}")
            return []

    def fetch_all_symbols_data(self) -> Optional[Dict]:
        """دریافت اطلاعات همه نمادهای موجود در بورس"""
        return self.get_all_symbols()
