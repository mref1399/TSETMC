# main.py
from flask import Flask, jsonify
import logging
from datetime import datetime
from modules.stock_data import StockDataFetcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_current_time():
    now = datetime.now()
    jalali_year = now.year - 621
    jalali_month = now.month + 9 if now.month <= 3 else now.month - 3
    if jalali_month > 12:
        jalali_month -= 12
        jalali_year += 1
    return f"{jalali_year}/{jalali_month:02d}/{now.day:02d}", now.strftime('%H:%M')

@app.route('/')
def home():
    return jsonify({
        'message': '💰 سیستم دریافت داده‌های بورس',
        'endpoints': {
            'all_symbols': '/stocks/all',
            'symbols_from_file': '/stocks',
        },
        'status': 'ready'
    })

@app.route('/stocks')
def stocks_from_file():
    """دریافت اطلاعات نمادهای موجود در فایل symbols.txt"""
    try:
        fetcher = StockDataFetcher()
        data = fetcher.fetch_symbols_from_file('symbols.txt')
        jalali_date, current_time = get_current_time()
        
        return jsonify({
            'status': 'success',
            'timestamp': f"{jalali_date} {current_time}",
            'total_symbols': len(data),
            'data': data
        })
        
    except Exception as e:
        logger.error(f"خطا در endpoint stocks: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/stocks/all')
def all_stocks():
    """دریافت همه نمادهای موجود در بورس"""
    try:
        fetcher = StockDataFetcher()
        data = fetcher.fetch_all_symbols_data()
        jalali_date, current_time = get_current_time()
        
        return jsonify({
            'status': 'success',
            'timestamp': f"{jalali_date} {current_time}",
            'data': data
        })
  
    except Exception as e:
        logger.error(f"خطا در endpoint all_stocks: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀سیستم دریافت داده‌های بورس")
    print("="*50)
    print("🌐 هه نمادها: http://localhost:5000/stocks/all")
    print("� نمادهای فایل: http://localhost:5000/stocks")
    print("="*50)
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
