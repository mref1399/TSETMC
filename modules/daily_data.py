import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class DailyDataFetcher:
    """دریافت داده‌های روز جاری از BrsApi"""

    def __init__(self, api_key: str = "YourApiKey"):
        self.api_key = api_key
        self.base_url = "https://BrsApi.ir/Api/Tsetmc"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/106.0.0.0",
            "Accept": "application/json, text/plain, */*"
        })

    def get_all_symbols_data(self) -> Dict:
        """دریافت داده‌های همه نمادها"""
        try:
            url = f"{self.base_url}/AllSymbols.php"
            params = {"key": self.api_key}
            
            logger.info("درحال دریافت داده‌های همه نمادها...")
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json() if response.text else {}
                logger.info(f"✅ داده‌های {len(data)} نماد دریافت شد")
                
                return {
                    'status': 'success',
                    'message': f'داده‌های {len(data)} نماد دریافت شد',
                    'data': data,
                    'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
                    'source': 'BrsApi.ir'
                }
            else:
                logger.error(f"خطای API: {response.status_code}")
                return {
                    'status': 'error',
                    'message': f'خطای API: {response.status_code}',
                    'data': [],
                    'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S')
                }

        except requests.exceptions.Timeout:
            logger.error("Timeout در درخواست API")
            return {
                'status': 'error',
                'message': 'Timeout در درخواست API',
                'data': [],
                'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"خطای شبکه: {str(e)}")
            return {
                'status': 'error',
                'message': f'خطای شبکه: {str(e)}',
                'data': [],
                'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            }
        except json.JSONDecodeError:
            logger.error("خطا در تجزیه JSON")
            return {
                'status': 'error',
                'message': 'خطا در تجزیه JSON - پاسخ معتبر نیست',
                'data': [],
                'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"خطای غیرمنتظره: {str(e)}")
            return {
                'status': 'error',
                'message': f'خطای غیرمنتظره: {str(e)}',
                'data': [],
                'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            }

    def get_symbol_data(self, symbol: str) -> Dict:
        """دریافت داده‌های یک نماد خاص"""
        try:
            # اول همه داده‌ها رو بگیر
            all_data = self.get_all_symbols_data()
            
            if all_data['status'] == 'error':
                return all_data
            
            # پیدا کردن نماد مورد نظر
            symbols_data = all_data['data']
            symbol_info = None
            
            for sym_data in symbols_data:
                if isinstance(sym_data, dict) and sym_data.get('symbol') == symbol:
                    symbol_info = sym_data
                    break
            
            if symbol_info:
                return {
                    'status': 'success',
                    'message': f'داده‌های نماد {symbol} دریافت شد',
                    'data': symbol_info,
                    'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
                    'source': 'BrsApi.ir'
                }
            else:
                return {
                    'status': 'not_found',
                    'message': f'نماد {symbol} یافت نشد',
                    'data': {},
                    'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S')
                }

        except Exception as e:
            logger.error(f"خطا در دریافت داده‌های نماد {symbol}: {str(e)}")
            return {
                'status': 'error',
                'message': f'خطا در دریافت داده‌های نماد {symbol}: {str(e)}',
                'data': {},
                'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            }

    def get_filtered_data(self, filters: Dict = None) -> Dict:
        """دریافت داده‌های فیلتر شده"""
        try:
            all_data = self.get_all_symbols_data()
            
            if all_data['status'] == 'error':
                return all_data
            
            symbols_data = all_data['data']
            filtered_data = []
            
            if not filters:
                filtered_data = symbols_data
            else:
                # اعمال فیلترها
                for sym_data in symbols_data:
                    if not isinstance(sym_data, dict):
                        continue
                    
                    match = True
                    
                    # فیلتر حجم
                    if 'min_volume' in filters:
                        volume = sym_data.get('volume', 0)
                        if volume < filters['min_volume']:
                            match = False
                    
                    # فیلتر قیمت
                    if 'min_price' in filters:
                        price = sym_data.get('last_price', 0)
                        if price < filters['min_price']:
                            match = False
                    
                    # فیلتر تغییر مثبت
                    if filters.get('positive_change', False):
                        change = sym_data.get('change_percent', 0)
                        if change <= 0:
                            match = False
                    
                    if match:
                        filtered_data.append(sym_data)
            
            return {
                'status': 'success',
                'message': f'{len(filtered_data)} نماد پس از اعمال فیلتر',
                'data': filtered_data,
                'total_filtered': len(filtered_data),
                'total_original': len(symbols_data),
                'filters_applied': filters or {},
                'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
                'source': 'BrsApi.ir'
            }

        except Exception as e:
            logger.error(f"خطا در فیلتر کردن داده‌ها: {str(e)}")
            return {
                'status': 'error',
                'message': f'خطا در فیلتر کردن داده‌ها: {str(e)}',
                'data': [],
                'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            }

    def get_market_summary(self) -> Dict:
        """خلاصه بازار"""
        try:
            all_data = self.get_all_symbols_data()
            
            if all_data['status'] == 'error':
                return all_data
            
            symbols_data = all_data['data']
            
            if not symbols_data:
                return {
                    'status': 'error',
                    'message': 'هیچ داده‌ای دریافت نشد',
                    'summary': {}
                }
            
            # محاسبه آمار کلی
            total_symbols = len(symbols_data)
            positive_symbols = 0
            negative_symbols = 0
            total_volume = 0
            total_value = 0
            
            for sym_data in symbols_data:
                if not isinstance(sym_data, dict):
                    continue
                
                change = sym_data.get('change_percent', 0)
                if change > 0:
                    positive_symbols += 1
                elif change < 0:
                    negative_symbols += 1
                
                volume = sym_data.get('volume', 0)
                price = sym_data.get('last_price', 0)
                total_volume += volume
                total_value += volume * price
            
            return {
                'status': 'success',
                'message': 'خلاصه بازار محاسبه شد',
                'summary': {
                    'total_symbols': total_symbols,
                    'positive_symbols': positive_symbols,
                    'negative_symbols': negative_symbols,
                    'neutral_symbols': total_symbols - positive_symbols - negative_symbols,
                    'total_volume': total_volume,
                    'total_value': total_value,
                    'positive_ratio': round((positive_symbols / total_symbols) * 100, 2) if total_symbols > 0 else 0
                },
                'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
                'source': 'BrsApi.ir'
            }

        except Exception as e:
            logger.error(f"خطا در محاسبه خلاصه بازار: {str(e)}")
            return {
                'status': 'error',
                'message': f'خطا در محاسبه خلاصه بازار: {str(e)}',
                'summary': {},
                'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            }
