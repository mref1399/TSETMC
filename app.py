import requests
import json
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import pytz
import jdatetime
from flask import Flask, jsonify, render_template_string
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# تنظیمات
MAX_WORKERS = 100  # افزایش برای پردازش همه سهم‌ها
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
            logger.info("در حال دریافت لیست کامل سهام از بورس...")
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
            logger.error(f"خطا در دریافت نمادها: {e}")
        
        logger.warning("از لیست پشتیبان استفاده می‌شود...")
        return []

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
        logger.debug(f"خطا در دریافت داده {symbol}: {e}")
    
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
    """دریافت زمان فعلی"""
    tehran_tz = pytz.timezone('Asia/Tehran')
    now = datetime.now(tehran_tz)
    jalali_date = jdatetime.datetime.now().strftime('%Y/%m/%d')
    time_str = now.strftime('%H:%M:%S')
    return jalali_date, time_str

# قالب HTML برای نمایش جدول
TABLE_TEMPLATE = '''
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>جریان پول هوشمند بورس تهران</title>
    <style>
        * { font-family: 'Tahoma', Arial, sans-serif; }
        body { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0; padding: 20px; color: #333;
        }
        .header { 
            background: white; border-radius: 15px; padding: 20px; 
            margin-bottom: 20px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .header h1 { color: #2c3e50; margin: 0; }
        .info { 
            display: flex; justify-content: space-around; 
            margin-top: 15px; font-size: 14px; color: #7f8c8d;
        }
        .table-container { 
            background: white; border-radius: 15px; 
            padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            overflow-x: auto;
        }
        table { 
            width: 100%; border-collapse: collapse; 
            font-size: 14px; margin-top: 10px;
        }
        th { 
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white; padding: 12px 8px; 
            text-align: center; font-weight: bold;
            border: 1px solid #2980b9;
        }
        td { 
            padding: 10px 8px; text-align: center; 
            border: 1px solid #ecf0f1;
            transition: background-color 0.3s;
        }
        tr:nth-child(even) { background-color: #f8f9fa; }
        tr:hover { background-color: #e8f4f8; }
        .amount { font-weight: bold; color: #27ae60; }
        .symbol { font-weight: bold; color: #2c3e50; }
        .no-data { 
            text-align: center; padding: 40px; 
            color: #7f8c8d; font-size: 16px;
        }
        .summary { 
            background: #ecf0f1; padding: 15px; 
            border-radius: 10px; margin-bottom: 15px;
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px; text-align: center;
        }
        .summary div { 
            background: white; padding: 10px; 
            border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .summary strong { color: #2c3e50; display: block; font-size: 18px; }
        .summary span { color: #7f8c8d; font-size: 12px; }
        .refresh-btn {
            background: linear-gradient(135deg, #27ae60, #2ecc71);
            color: white; border: none; padding: 10px 20px;
            border-radius: 25px; cursor: pointer; font-size: 14px;
            margin: 10px; transition: transform 0.3s;
        }
        .refresh-btn:hover { transform: scale(1.05); }
        @media (max-width: 768px) {
            .info { flex-direction: column; gap: 5px; }
            table { font-size: 12px; }
            th, td { padding: 8px 4px; }
        }
    </style>
    <script>
        function autoRefresh() {
            setTimeout(() => location.reload(), 300000); // هر 5 دقیقه
        }
        function manualRefresh() {
            location.reload();
        }
        window.onload = autoRefresh;
    </script>
</head>
<body>
    <div class="header">
        <h1>🏛️ جریان پول هوشمند بورس تهران</h1>
        <div class="info">
            <span>📅 تاریخ: {{ scan_date }}</span>
            <span>🕐 زمان اسکن: {{ scan_time }}</span>
            <span>📊 تعداد نمادها: {{ total_symbols }}</span>
            <span>💰 جریان‌های فعال: {{ active_flows }}</span>
            <span>⏱️ زمان پردازش: {{ processing_time }}s</span>
        </div>
        <button class="refresh-btn" onclick="manualRefresh()">🔄 بروزرسانی</button>
    </div>

    <div class="table-container">
        {% if flows %}
        <div class="summary">
            <div><strong>{{ total_symbols }}</strong><span>کل نمادها</span></div>
            <div><strong>{{ active_flows }}</strong><span>جریان فعال</span></div>
            <div><strong>{{ significant_flows }}</strong><span>جریان قابل توجه</span></div>
            <div><strong>{{ top_flow_amount }}</strong><span>بالاترین جریان</span></div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>ردیف</th>
                    <th>نماد سهم</th>
                    <th>مقدار پول هوشمند وارد شده</th>
                    <th>واحد</th>
                    <th>زمان</th>
                </tr>
            </thead>
            <tbody>
                {% for flow in flows %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td class="symbol">{{ flow.symbol }}</td>
                    <td class="amount">{{ "{:,.0f}".format(flow.smart_money_amount) if flow.smart_money_amount > 1000 else "{:.2f}".format(flow.smart_money_amount) }}</td>
                    <td>{{ flow.currency_unit }}</td>
                    <td>{{ flow.time }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <div class="no-data">
            <h3>📭 هیچ جریان پول هوشمند قابل توجهی یافت نشد</h3>
            <p>لطفاً چند دقیقه بعد دوباره تلاش کنید</p>
        </div>
        {% endif %}
    </div>
</body>
</html>
'''

@app.route('/', methods=['GET'])
@app.route('/table', methods=['GET'])
def smart_money_table():
    """نمایش جدول جریان پول هوشمند"""
    try:
        start_time = time.time()
        api_client = StockAPI()
        
        # دریافت همه نمادها
        symbols = api_client.get_all_symbols()
        if not symbols:
            logger.error("هیچ نمادی دریافت نشد!")
            return "❌ خطا در دریافت لیست سهام", 500
        
        logger.info(f"🔍 در حال بررسی {len(symbols)} نماد...")
        
        smart_money_flows = []
        processed = 0
        
        # پردازش موازی همه سهام
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_symbol = {
                executor.submit(get_stock_data, symbol, api_client): symbol 
                for symbol in symbols
            }
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                processed += 1
                
                if processed % 50 == 0:
                    logger.info(f"⏳ پردازش شده: {processed}/{len(symbols)}")
                
                try:
                    stock_data = future.result()
                    if stock_data:
                        amount, unit = calculate_smart_money(stock_data)
                        
                        # فقط سهام با پول هوشمند قابل توجه (حداقل 10 میلیون تومان)
                        if (unit == "میلیون تومان" and amount >= 10) or \
                           (unit == "میلیارد تومان") or \
                           (unit == "هزار میلیارد تومان"):
                            
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
                    logger.debug(f"خطا در پردازش {symbol}: {e}")
                    continue
        
        # مرتب‌سازی بر اساس مقدار پول هوشمند
        smart_money_flows.sort(key=lambda x: x['raw_value'], reverse=True)
        
        processing_time = round(time.time() - start_time, 2)
        jalali_date, time_str = get_current_time()
        
        # محاسبه آمار
        significant_flows = len([f for f in smart_money_flows 
                               if f['currency_unit'] in ['میلیارد تومان', 'هزار میلیارد تومان']])
        
        top_flow_amount = f"{smart_money_flows[0]['smart_money_amount']} {smart_money_flows[0]['currency_unit']}" if smart_money_flows else "0"
        
        logger.info(f"✅ پردازش کامل شد: {len(smart_money_flows)} جریان فعال یافت شد")
        
        return render_template_string(TABLE_TEMPLATE,
            flows=smart_money_flows,
            scan_date=jalali_date,
            scan_time=time_str,
            total_symbols=len(symbols),
            active_flows=len(smart_money_flows),
            significant_flows=significant_flows,
            top_flow_amount=top_flow_amount,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"خطای کلی: {e}")
        return f"❌ خطا در پردازش: {str(e)}", 500

@app.route('/api/smart-money', methods=['GET'])
def api_smart_money():
    """API برای دریافت داده‌های خام"""
    try:
        start_time = time.time()
        api_client = StockAPI()
        symbols = api_client.get_all_symbols()
        
        flows = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
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
            'total_symbols': len(symbols),
            'active_flows': len(flows),
            'processing_time': round(time.time() - start_time, 2),
            'scan_time': f"{jalali_date} {time_str}",
            'flows': flows
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    """وضعیت سیستم"""
    jalali_date, time_str = get_current_time()
    return jsonify({
        'status': 'آنلاین ✅',
        'cache_size': len(CACHE),
        'current_time': f"{jalali_date} {time_str}",
        'workers': MAX_WORKERS
    })

if __name__ == '__main__':
    print("🚀 سیستم تحلیل جریان پول هوشمند بورس تهران")
    print("=" * 60)
    print("📊 دسترسی به جدول: http://localhost:5000")
    print("🔗 API داده‌ها: http://localhost:5000/api/smart-money")
    print("⚡ وضعیت سیستم: http://localhost:5000/status")
    print("=" * 60)
    print("🔄 در حال راه‌اندازی...")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
