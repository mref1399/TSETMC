import requests
import json
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class SmartMoneyDetector:
    """تشخیص پول هوشمند با منطق فیلتر دقیق"""
    
    def __init__(self):
        self.tsetmc_base = "http://old.tsetmc.com/tsev2/data"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_symbol_data(self, symbol: str) -> Optional[Dict]:
        """دریافت داده‌های سهم از TSETMC"""
        try:
            # دریافت داده کلی سهم
            url = f"{self.tsetmc_base}/InstTradeHistory.aspx"
            params = {'i': symbol, 'Top': '1', 'A': '0'}
            
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return None
                
            data = response.text.strip()
            if not data:
                return None
                
            parts = data.split(';')
            if len(parts) < 10:
                return None
                
            # استخراج داده‌ها
            info = parts[0].split(',')
            if len(info) < 12:
                return None
                
            return {
                'symbol': symbol,
                'tvol': float(info[9]) if info[9] else 0,  # حجم امروز
                'is5': float(info[10]) if info[10] else 0,  # میانگین 5 روزه حجم
                'pl': float(info[3]) if info[3] else 0,    # آخرین قیمت
                'pc': float(info[5]) if info[5] else 0,    # قیمت پایانی دیروز
                'plp': float(info[11]) if info[11] else 0  # درصد تغییر
            }
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {str(e)}")
            return None
    
    def get_legal_data(self, symbol: str) -> Optional[Dict]:
        """دریافت داده‌های حقیقی-حقوقی"""
        try:
            url = f"{self.tsetmc_base}/ClientTypeHistory.aspx"
            params = {'i': symbol}
            
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return None
                
            data = response.text.strip()
            if not data:
                return None
                
            lines = data.split('\n')
            if len(lines) < 1:
                return None
                
            # آخرین روز
            latest = lines[0].split(',')
            if len(latest) < 8:
                return None
                
            return {
                'buy_i_volume': float(latest[2]) if latest[2] else 0,    # حجم خرید حقیقی
                'buy_count_i': float(latest[3]) if latest[3] else 1,     # تعداد خرید حقیقی
                'sell_i_volume': float(latest[4]) if latest[4] else 0,   # حجم فروش حقیقی
                'sell_count_i': float(latest[5]) if latest[5] else 1     # تعداد فروش حقیقی
            }
            
        except Exception as e:
            logger.error(f"Error fetching legal data for {symbol}: {str(e)}")
            return None
    
    def check_smart_money_condition(self, symbol: str) -> Dict:
        """بررسی شرایط پول هوشمند"""
        try:
            # دریافت داده‌ها
            symbol_data = self.get_symbol_data(symbol)
            legal_data = self.get_legal_data(symbol)
            
            if not symbol_data or not legal_data:
                return {
                    'symbol': symbol,
                    'has_smart_money': False,
                    'reason': 'داده‌ها دریافت نشد'
                }
            
            # استخراج متغیرها
            tvol = symbol_data['tvol']
            is5 = symbol_data['is5']
            pl = symbol_data['pl']
            pc = symbol_data['pc']
            plp = symbol_data['plp']
            
            buy_i_volume = legal_data['buy_i_volume']
            buy_count_i = legal_data['buy_count_i']
            sell_i_volume = legal_data['sell_i_volume']
            sell_count_i = legal_data['sell_count_i']
            
            # محاسبه شرایط
            condition1 = tvol > 1.25 * is5  # حجم امروز > 1.25 * میانگین 5 روزه
            condition2 = (buy_i_volume / buy_count_i) >= (sell_i_volume / sell_count_i)  # متوسط خرید حقیقی >= متوسط فروش
            condition3 = pl >= pc  # قیمت >= قیمت دیروز
            condition4 = plp > 0   # درصد تغییر مثبت
            
            # بررسی همه شرایط
            has_smart_money = condition1 and condition2 and condition3 and condition4
            
            return {
                'symbol': symbol,
                'has_smart_money': has_smart_money,
                'data': {
                    'tvol': tvol,
                    'is5': is5,
                    'pl': pl,
                    'pc': pc,
                    'plp': plp,
                    'avg_buy': buy_i_volume / buy_count_i,
                    'avg_sell': sell_i_volume / sell_count_i
                },
                'conditions': {
                    'volume_condition': condition1,
                    'legal_condition': condition2,
                    'price_condition': condition3,
                    'change_condition': condition4
                }
            }
            
        except Exception as e:
            logger.error(f"Error checking smart money for {symbol}: {str(e)}")
            return {
                'symbol': symbol,
                'has_smart_money': False,
                'reason': f'خطا: {str(e)}'
            }
    
    def scan_symbols_from_file(self, file_path: str = 'symbols.txt') -> Dict:
        """اسکن سهم‌ها از فایل تکست"""
        try:
            # خواندن فایل سهام
            with open(file_path, 'r', encoding='utf-8') as f:
                symbols = [line.strip() for line in f.readlines() if line.strip()]
            
            if not symbols:
                return {
                    'status': 'error',
                    'message': 'فایل symbols.txt خالی است',
                    'symbols_with_smart_money': [],
                    'total_symbols': 0,
                    'smart_money_count': 0
                }
            
            logger.info(f"اسکن {len(symbols)} سهم برای پول هوشمند...")
            
            results = []
            for symbol in symbols:
                logger.info(f"بررسی {symbol}...")
                result = self.check_smart_money_condition(symbol)
                
                if result['has_smart_money']:
                    results.append(result)
            
            return {
                'status': 'success',
                'symbols_with_smart_money': results,
                'total_symbols': len(symbols),
                'smart_money_count': len(results),
                'has_any_smart_money': len(results) > 0
            }
            
        except FileNotFoundError:
            return {
                'status': 'error',
                'message': 'فایل symbols.txt یافت نشد',
                'symbols_with_smart_money': [],
                'total_symbols': 0,
                'smart_money_count': 0
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'خطا در اسکن: {str(e)}',
                'symbols_with_smart_money': [],
                'total_symbols': 0,
                'smart_money_count': 0
            }

# به‌روزرسانی endpoint در app.py
@app.route('/api/smart-money')
def smart_money_api():
    """API پول هوشمند با منطق دقیق"""
    detector = SmartMoneyDetector()
    results = detector.scan_symbols_from_file('symbols.txt')
    
    if results['status'] == 'error':
        return jsonify({
            'status': 'error',
            'message': results['message']
        }), 400
    
    if results['has_any_smart_money']:
        # پول هوشمند شناسایی شد
        symbols_list = [item['symbol'] for item in results['symbols_with_smart_money']]
        
        response = {
            'status': 'success',
            'message': f"پول هوشمند در {results['smart_money_count']} سهم از {results['total_symbols']} سهم شناسایی شد",
            'symbols_with_smart_money': symbols_list,
            'details': []
        }
        
        for item in results['symbols_with_smart_money']:
            response['details'].append({
                'symbol': item['symbol'],
                'volume_today': f"{item['data']['tvol']:,.0f}",
                'avg_volume_5d': f"{item['data']['is5']:,.0f}",
                'price_current': f"{item['data']['pl']:,.0f}",
                'price_yesterday': f"{item['data']['pc']:,.0f}",
                'change_percent': f"{item['data']['plp']:.2f}%",
                'avg_legal_buy': f"{item['data']['avg_buy']:,.0f}",
                'avg_legal_sell': f"{item['data']['avg_sell']:,.0f}"
            })
        
    else:
        # هیچ پول هوشمندی شناسایی نشد
        response = {
            'status': 'no_smart_money',
            'message': f"در هیچ‌کدام از {results['total_symbols']} سهم بررسی شده، پول هوشمند شناسایی نشد",
            'symbols_with_smart_money': [],
            'details': []
        }
    
    return jsonify(response)

@app.route('/telegram')
def telegram_format():
    """خروجی تلگرام برای پول هوشمند"""
    detector = SmartMoneyDetector()
    results = detector.scan_symbols_from_file('symbols.txt')
    
    if results['status'] == 'error':
        message = f"❌ خطا: {results['message']}"
    elif results['has_any_smart_money']:
        symbols_list = [item['symbol'] for item in results['symbols_with_smart_money']]
        message = f"🧠 پول هوشمند شناسایی شد!\n\n"
        message += f"📊 {results['smart_money_count']} سهم از {results['total_symbols']} سهم:\n"
        message += "🔥 " + ", ".join(symbols_list) + "\n\n"
        message += "📈 شرایط تأیید شده:\n"
        message += "✅ حجم بالای میانگین\n"
        message += "✅ خرید حقیقی قوی‌تر\n"
        message += "✅ قیمت مثبت\n"
    else:
        message = f"😴 هیچ پول هوشمندی شناسایی نشد\n\n"
        message += f"📊 {results['total_symbols']} سهم بررسی شد\n"
        message += "📉 شرایط تأیید نشد"
    
    return message, 200, {'Content-Type': 'text/plain; charset=utf-8'}
