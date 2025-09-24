from flask import Flask, jsonify, request
import logging
from datetime import datetime

# تنظیم logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# import ماژول‌ها
try:
    from modules.daily_data import DailyDataFetcher
except ImportError as e:
    logger.error(f"خطا در import ماژول‌ها: {e}")
    exit(1)

app = Flask(__name__)

def get_current_time():
    """زمان فعلی"""
    now = datetime.now()
    jalali_year = now.year - 621
    jalali_month = now.month + 9 if now.month <= 3 else now.month - 3
    if jalali_month > 12:
        jalali_month -= 12
        jalali_year += 1
    return f"{jalali_year}/{jalali_month:02d}/{now.day:02d}", now.strftime('%H:%M')

@app.route('/')
def home():
    """صفحه اصلی"""
    return jsonify({
        'message': '📊 سیستم تحلیل بورس - داده‌های روز جاری',
        'modules': {
            'daily_data': '/daily_data',
            'market_summary': '/market_summary',
            'symbol_data': '/symbol_data/<symbol>'
        },
        'usage': 'برای فراخوانی هر ماژول: /{module_name}',
        'status': 'running'
    })

@app.route('/daily_data')
def daily_data_endpoint():
    """ماژول داده‌های روز جاری"""
    try:
        # دریافت پارامترهای اختیاری برای فیلتر
        min_volume = request.args.get('min_volume', type=int)
        min_price = request.args.get('min_price', type=float)
        positive_change = request.args.get('positive_change', type=bool, default=False)
        
        fetcher = DailyDataFetcher()
        
        # اگر فیلتری تعریف شده، از get_filtered_data استفاده کن
        if min_volume or min_price or positive_change:
            filters = {}
            if min_volume:
                filters['min_volume'] = min_volume
            if min_price:
                filters['min_price'] = min_price
            if positive_change:
                filters['positive_change'] = positive_change
                
            results = fetcher.get_filtered_data(filters)
        else:
            results = fetcher.get_all_symbols_data()
        
        jalali_date, current_time = get_current_time()

        if results['status'] == 'error':
            return jsonify({
                'status': 'error',
                'message': results['message'],
                'timestamp': f"{jalali_date} {current_time}"
            }), 400

        return jsonify({
            'status': 'success',
            'module': 'daily_data',
            'timestamp': f"{jalali_date} {current_time}",
            'message': results['message'],
            'data': results['data'],
            'total_symbols': len(results['data']) if isinstance(results['data'], list) else 1
        })

    except Exception as e:
        logger.error(f"خطا در ماژول daily_data: {e}")
        return jsonify({
            'status': 'error',
            'module': 'daily_data',
            'error': str(e)
        }), 500

@app.route('/market_summary')
def market_summary_endpoint():
    """خلاصه بازار"""
    try:
        fetcher = DailyDataFetcher()
        results = fetcher.get_market_summary()
        jalali_date, current_time = get_current_time()

        if results['status'] == 'error':
            return jsonify({
                'status': 'error',
                'message': results['message'],
                'timestamp': f"{jalali_date} {current_time}"
            }), 400

        return jsonify({
            'status': 'success',
            'module': 'market_summary',
            'timestamp': f"{jalali_date} {current_time}",
            'message': results['message'],
            'summary': results['summary']
        })

    except Exception as e:
        logger.error(f"خطا در ماژول market_summary: {e}")
        return jsonify({
            'status': 'error',
            'module': 'market_summary',
            'error': str(e)
        }), 500

@app.route('/symbol_data/<symbol>')
def symbol_data_endpoint(symbol):
    """داده‌های یک نماد خاص"""
    try:
        fetcher = DailyDataFetcher()
        results = fetcher.get_symbol_data(symbol)
        jalali_date, current_time = get_current_time()

        if results['status'] == 'error':
            return jsonify({
                'status': 'error',
                'message': results['message'],
                'timestamp': f"{jalali_date} {current_time}"
            }), 400
        
        if results['status'] == 'not_found':
            return jsonify({
                'status': 'not_found',
                'message': results['message'],
                'timestamp': f"{jalali_date} {current_time}"
            }), 404

        return jsonify({
            'status': 'success',
            'module': 'symbol_data',
            'timestamp': f"{jalali_date} {current_time}",
            'message': results['message'],
            'symbol': symbol,
            'data': results['data']
        })

    except Exception as e:
        logger.error(f"خطا در ماژول symbol_data: {e}")
        return jsonify({
            'status': 'error',
            'module': 'symbol_data',
            'error': str(e)
        }), 500

@app.route('/health')
def health_check():
    """بررسی سلامت سرویس"""
    return jsonify({
        'status': 'healthy',
        'service': 'TSETMC Data API',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 سیستم تحلیل بورس - داده‌های روز جاری")
    print("="*50)
    print("🏠 صفحه اصلی: http://localhost:5000")
    print("📊 داده‌های روزانه: http://localhost:5000/daily_data")
    print("📈 خلاصه بازار: http://localhost:5000/market_summary")
    print("🔍 داده نماد: http://localhost:5000/symbol_data/نماد")
    print("❤️ Health Check: http://localhost:5000/health")
    print("="*50)

    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except Exception as e:
        print(f"❌ خطا: {e}")
