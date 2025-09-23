import requests
import json
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import threading

# تنظیم لاگ ساده
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from flask import Flask, jsonify, render_template_string
    app = Flask(__name__)
except ImportError:
    logger.error("Flask نصب نیست! pip install flask")
    exit(1)

# تنظیمات
MAX_WORKERS = 80
REQUEST_TIMEOUT = 8
CACHE_DURATION = 30

# کش ساده
CACHE = {}
cache_lock = threading.Lock()

class StockAPI:
    BASE_URL = "http://old.tsetmc.com/tsev2/data/instinfodata.aspx"
    SYMBOLS_URL = "http://service.tsetmc.com/tsev2/data/MarketWatchPlus.aspx"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_all_symbols(self):
        """دریافت تمام نمادهای بورس"""
        try:
            logger.info("🔍 در حال دریافت لیست کامل سهام از بورس...")
            response = self.session.get(self.SYMBOLS_URL, timeout=15)
            if response.status_code == 200:
                data = response.text
                symbols = []
                for line in data.strip().split('\n'):
                    parts = line.split(',')
                    if len(parts) > 2:
                        symbol = parts[2].strip()
                        if symbol and len(symbol) <= 12 and symbol.replace(' ', ''):
                            symbols.append(symbol)
                
                unique_symbols = list(set(symbols))
                logger.info(f"✅ {len(unique_symbols)} نماد از بورس دریافت شد")
                return unique_symbols
                
        except Exception as e:
            logger.error(f"❌ خطا در دریافت نمادها: {e}")
        
        # لیست پشتیبان کامل سهام مهم بورس تهران
        logger.warning("⚠️ از لیست پشتیبان استفاده می‌شود...")
        return [
            'فولاد', 'پترو', 'وبملت', 'شپنا', 'فجر', 'خودرو', 'ساپا', 'شبندر',
            'وپارس', 'حکمت', 'تاپیکو', 'شستا', 'تامین', 'پاسا', 'دی', 'نوری',
            'ثسعادت', 'ثبهساز', 'کرمان', 'جم', 'وتجارت', 'فراسا', 'مپنا', 'خساپا',
            'کگهر', 'خزر', 'حتوکا', 'رمپنا', 'سینا', 'کرتون', 'شاخص', 'فرابورس',
            'بپاس', 'وامید', 'تلیسه', 'فسازان', 'ایران', 'پارس', 'ثقلین', 'نیرو',
            'پگاه', 'مدیر', 'مارون', 'بورس', 'تهران', 'ملی', 'بانک', 'صنعت',
            'معدن', 'نفت', 'گاز', 'شیمی', 'دارو', 'غذا', 'نساجی', 'قند',
            'سیمان', 'فلز', 'ماشین', 'الکترو', 'انرژی', 'آب', 'برق', 'ارتباط'
        ]

def get_stock_data(symbol, api_client):
    """دریافت داده سهم"""
    cache_key = f"{symbol}_{int(time.time() // CACHE_DURATION)}"
    
    # چک کش
    with cache_lock:
        if cache_key in CACHE:
            return CACHE[cache_key]
    
    try:
        params = {'i': symbol, 'c': '1'}
        response = api_client.session.get(
            api_client.BASE_URL, 
            params=params, 
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.text.strip()
            if data and len(data) > 10:
                parts = data.split(',')
                if len(parts) >= 8:
                    volume = int(float(parts[6].replace(',', ''))) if parts[6] and parts[6] != '0' else 0
                    last_price = float(parts[2].replace(',', '')) if parts[2] and parts[2] != '0' else 0
                    
                    if volume > 0 and last_price > 0:
                        result = {
                            'symbol': symbol,
                            'volume': volume,
                            'last_price': last_price,
                            'value': float(parts[7].replace(',', '')) if parts[7] else 0
                        }
                        
                        # ذخیره در کش
                        with cache_lock:
                            CACHE[cache_key] = result
                        
                        return result
    except Exception as e:
        logger.debug(f"خطا در دریافت {symbol}: {e}")
    
    return None

def calculate_smart_money(stock_data):
    """محاسبه پول هوشمند وارد شده"""
    if not stock_data:
        return 0, "تومان"
    
    volume = stock_data.get('volume', 0)
    last_price = stock_data.get('last_price', 0)
    
    if not volume or not last_price:
        return 0, "تومان"
    
    # پول هوشمند = حجم × قیمت
    smart_money = volume * last_price
    
    # تعیین واحد
    if smart_money >= 1e12:
        return round(smart_money / 1e12, 2), "هزار میلیارد تومان"
    elif smart_money >= 1e9:
        return round(smart_money / 1e9, 2), "میلیارد تومان"
    elif smart_money >= 1e6:
        return round(smart_money / 1e6, 2), "میلیون تومان"
    elif smart_money >= 1e3:
        return round(smart_money / 1e3, 2), "هزار تومان"
    else:
        return round(smart_money, 0), "تومان"

def get_current_time():
    """دریافت زمان فعلی (بدون pytz)"""
    now = datetime.now()
    
    # تبدیل ساده به تاریخ شمسی (تقریبی)
    year = now.year - 621
    month = now.month + 9 if now.month <= 3 else now.month - 3
    day = now.day
    
    if month > 12:
        month -= 12
        year += 1
    
    jalali_date = f"{year:04d}/{month:02d}/{day:02d}"
    time_str = now.strftime('%H:%M:%S')
    
    return jalali_date, time_str

# قالب HTML ساده
SIMPLE_TABLE = '''
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>پول هوشمند بورس</title>
    <style>
        body { font-family: Tahoma, Arial; margin: 20px; background: #f0f2f5; }
        .header { 
            background: #2c3e50; color: white; padding: 20px; 
            border-radius: 10px; text-align: center; margin-bottom: 20px;
        }
        .info { margin-top: 10px; font-size: 14px; }
        table { 
            width: 100%; background: white; border-radius: 10px; 
            overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        th { background: #3498db; color: white; padding: 15px; text-align: center; }
        td { padding: 12px; text-align: center; border-bottom: 1px solid #ecf0f1; }
        tr:nth-child(even) { background: #f8f9fa; }
        tr:hover { background: #e8f4f8; }
        .amount { font-weight: bold; color: #27ae60; }
        .symbol { font-weight: bold; color: #2c3e50; font-size: 16px; }
        .refresh { 
            background: #27ae60; color: white; border: none; 
            padding: 10px 20px; border-radius: 5px; cursor: pointer; margin: 10px;
        }
        .status { 
            background: #ecf0f1; padding: 15px; border-radius: 10px; 
            margin-bottom: 20px; text-align: center;
        }
        @media (max-width: 768px) {
            table { font-size: 12px; }
            th, td { padding: 8px 4px; }
        }
    </style>
    <script>
        function refresh() { location.reload(); }
        setTimeout(refresh, 300000); // 5 دقیقه
    </script>
</head>
<body>
    <div class="header">
        <h1>💰 جریان پول هوشمند بورس تهران</h1>
        <div class="info">
            📅 {{ scan_date }} | 🕐 {{ scan_time }} | 📊 {{ total_symbols }} نماد | ⚡ {{ active_flows }} فعال
        </div>
        <button class="refresh" onclick="refresh()">🔄 بروزرسانی</button>
    </div>

    <div class="status">
        <strong>آمار:</strong> {{ total_symbols }} نماد بررسی شد | 
        {{ active_flows }} جریان فعال | 
        {{ processing_time }} ثانیه پردازش
    </div>

    {% if flows %}
    <table>
        <tr>
            <th>ردیف</th>
            <th>نماد سهم</th>
            <th>مقدار پول هوشمند</th>
            <th>واحد</th>
            <th>زمان</th>
        </tr>
        {% for flow in flows %}
        <tr>
            <td>{{ loop.index }}</td>
            <td class="symbol">{{ flow.symbol }}</td>
            <td class="amount">{{ "{:,.2f}".format(flow.smart_money_amount) }}</td>
            <td>{{ flow.currency_unit }}</td>
            <td>{{ flow.time }}</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <div style="text-align: center; padding: 50px; background: white; border-radius: 10px;">
        <h3>📭 هیچ جریان پول هوشمند قابل توجهی یافت نشد</h3>
        <p>لطفاً چند دقیقه بعد مجدداً تلاش کنید</p>
    </div>
    {% endif %}
</body>
</html>
'''

@app.route('/', methods=['GET'])
def smart_money_table():
    """نمایش جدول جریان پول هوشمند"""
    try:
        start_time = time.time()
        logger.info("🚀 شروع اسکن جریان پول هوشمند...")
        
        api_client = StockAPI()
        symbols = api_client.get_all_symbols()
        
        if not symbols:
            logger.error("❌ هیچ نمادی دریافت نشد!")
            return "خطا در دریافت لیست سهام", 500
        
        logger.info(f"🔍 در حال بررسی {len(symbols)} نماد...")
        
        smart_money_flows = []
        processed = 0
        
        # پردازش موازی
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_symbol = {
                executor.submit(get_stock_data, symbol, api_client): symbol 
                for symbol in symbols
            }
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                processed += 1
                
                if processed % 25 == 0:
                    logger.info(f"⏳ پردازش: {processed}/{len(symbols)}")
                
                try:
                    stock_data = future.result()
                    if stock_data:
                        amount, unit = calculate_smart_money(stock_data)
                        
                        # فیلتر: فقط جریان‌های قابل توجه
                        if (unit == "میلیون تومان" and amount >= 50) or \
                           (unit in ["میلیارد تومان", "هزار میلیارد تومان"]):
                            
                            jalali_date, time_str = get_current_time()
                            
                            smart_money_flows.append({
                                'symbol': symbol,
                                'smart_money_amount': amount,
                                'currency_unit': unit,
                                'time': time_str,
                                'raw_value': amount * (1e12 if unit == "هزار میلیارد تومان" else 
                                                     1e9 if unit == "میلیارد تومان" else 
                                                     1e6 if unit == "میلیون تومان" else 1)
                            })
                            
                except Exception as e:
                    logger.debug(f"خطا در {symbol}: {e}")
        
        # مرتب‌سازی
        smart_money_flows.sort(key=lambda x: x['raw_value'], reverse=True)
        
        processing_time = round(time.time() - start_time, 2)
        jalali_date, time_str = get_current_time()
        
        logger.info(f"✅ اسکن کامل: {len(smart_money_flows)} جریان فعال یافت شد")
        
        return render_template_string(SIMPLE_TABLE,
            flows=smart_money_flows,
            scan_date=jalali_date,
            scan_time=time_str,
            total_symbols=len(symbols),
            active_flows=len(smart_money_flows),
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"❌ خطای کلی: {e}")
        return f"خطا در پردازش: {str(e)}", 500

@app.route('/api', methods=['GET'])
def api_data():
    """API ساده برای داده‌ها"""
    try:
        api_client = StockAPI()
        symbols = api_client.get_all_symbols()[:50]  # محدود برای API
        
        flows = []
        with ThreadPoolExecutor(max_workers=30) as executor:
            future_to_symbol = {
                executor.submit(get_stock_data, symbol, api_client): symbol 
                for symbol in symbols
            }
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    stock_data = future.result()
                    if stock_data:
                        amount, unit = calculate_smart_money(stock_data)
                        if amount > 0:
                            flows.append({
                                'symbol': symbol,
                                'amount': amount,
                                'unit': unit
                            })
                except:
                    continue
        
        flows.sort(key=lambda x: x['amount'], reverse=True)
        jalali_date, time_str = get_current_time()
        
        return jsonify({
            'status': 'success',
            'flows': flows[:20],
            'time': f"{jalali_date} {time_str}"
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    """وضعیت سیستم"""
    jalali_date, time_str = get_current_time()
    return jsonify({
        'status': 'آنلاین ✅',
        'cache_size': len(CACHE),
        'time': f"{jalali_date} {time_str}",
        'workers': MAX_WORKERS
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 سیستم تحلیل جریان پول هوشمند بورس تهران")
    print("=" * 60)
    print("📊 جدول اصلی: http://localhost:5000")
    print("🔗 API داده‌ها: http://localhost:5000/api")
    print("⚡ وضعیت: http://localhost:5000/status")
    print("=" * 60)
    print("🔄 در حال راه‌اندازی...")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"❌ خطا در راه‌اندازی: {e}")
        print("💡 راه حل: pip install flask requests")
