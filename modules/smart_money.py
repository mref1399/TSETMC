import requests
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class SmartMoneyDetector:
    """تشخیص واقعی پول هوشمند"""
    
    def __init__(self):
        self.min_smart_money = 2_000_000_000  # 2 میلیارد تومان
        self.sam_api_base = "https://api.sam.ir/v1"
        
    def get_smart_money(self, symbol: str) -> dict:
        """محاسبه واقعی پول هوشمند برای یک سهم"""
        try:
            # دریافت داده‌های حقیقی-حقوقی
            url = f"{self.sam_api_base}/symbol/{symbol}/legal-natural"
            
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return {'symbol': symbol, 'smart_money': 0, 'has_inflow': False}
            
            data = response.json()
            
            # محاسبه خالص خرید حقیقی (پول هوشمند)
            legal_buy = data.get('legal_buy', 0) or 0
            legal_sell = data.get('legal_sell', 0) or 0
            net_legal = legal_buy - legal_sell
            
            # تبدیل به تومان (اگر ریال باشه)
            smart_money_toman = net_legal / 10 if net_legal > 1000000 else net_legal
            
            return {
                'symbol': symbol,
                'smart_money': smart_money_toman,
                'has_inflow': smart_money_toman >= self.min_smart_money,
                'legal_buy': legal_buy,
                'legal_sell': legal_sell
            }
            
        except Exception as e:
            logger.error(f"Error fetching smart money for {symbol}: {str(e)}")
            return {'symbol': symbol, 'smart_money': 0, 'has_inflow': False}
    
    def scan_all_symbols(self, symbols_list: list) -> dict:
        """اسکن همه سهم‌ها برای پول هوشمند"""
        results = []
        total_smart_money = 0
        
        for symbol in symbols_list:
            logger.info(f"Scanning {symbol} for smart money...")
            result = self.get_smart_money(symbol)
            
            if result['has_inflow']:
                results.append(result)
                total_smart_money += result['smart_money']
        
        return {
            'symbols_with_inflow': results,
            'total_count': len(results),
            'total_smart_money': total_smart_money,
            'has_any_inflow': len(results) > 0
        }

# تغییر در app.py - endpoint فعلی رو آپدیت کن:
@app.route('/api/smart-money')
def smart_money_api():
    """API واقعی پول هوشمند"""
    detector = SmartMoneyDetector()
    
    # خواندن لیست سهام
    try:
        with open('symbols.txt', 'r', encoding='utf-8') as f:
            symbols = [line.strip() for line in f.readlines() if line.strip()]
    except:
        symbols = ['وبملت', 'خساپا', 'فولاد', 'شپنا', 'پرداخت']
    
    # اسکن پول هوشمند
    results = detector.scan_all_symbols(symbols)
    
    if results['has_any_inflow']:
        response = {
            'status': 'success',
            'message': f"پول هوشمند در {results['total_count']} سهم شناسایی شد",
            'total_smart_money_toman': f"{results['total_smart_money']:,.0f}",
            'symbols': []
        }
        
        for item in results['symbols_with_inflow']:
            response['symbols'].append({
                'symbol': item['symbol'],
                'smart_money_toman': f"{item['smart_money']:,.0f}",
                'smart_money_billion': f"{item['smart_money']/1_000_000_000:.2f}",
                'legal_buy': f"{item['legal_buy']:,.0f}",
                'legal_sell': f"{item['legal_sell']:,.0f}"
            })
    else:
        response = {
            'status': 'no_inflow',
            'message': 'هیچ پول هوشمندی شناسایی نشد',
            'total_smart_money_toman': '0',
            'symbols': []
        }
    
    return jsonify(response)

@app.route('/telegram')
def telegram_format():
    """پیام تلگرام برای پول هوشمند"""
    detector = SmartMoneyDetector()
    
    try:
        with open('symbols.txt', 'r', encoding='utf-8') as f:
            symbols = [line.strip() for line in f.readlines() if line.strip()]
    except:
        symbols = ['وبملت', 'خساپا', 'فولاد', 'شپنا', 'پرداخت']
    
    results = detector.scan_all_symbols(symbols)
    
    if results['has_any_inflow']:
        message = f"🧠 پول هوشمند شناسایی شد!\n\n"
        message += f"📊 تعداد: {results['total_count']} سهم\n"
        message += f"💰 مجموع: {results['total_smart_money']:,.0f} تومان\n\n"
        
        for item in results['symbols_with_inflow']:
            message += f"🔥 {item['symbol']}\n"
            message += f"💵 {item['smart_money']:,.0f} تومان\n"
            message += f"📈 {item['smart_money']/1_000_000_000:.2f} میلیارد\n\n"
    else:
        message = "😴 هیچ پول هوشمندی شناسایی نشد\n"
        message += "📉 بازار در انتظار..."
    
    return message, 200, {'Content-Type': 'text/plain; charset=utf-8'}
