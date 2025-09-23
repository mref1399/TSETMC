from flask import Flask, jsonify
import logging
from datetime import datetime

# تنظیم logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# import ماژول‌ها
try:
    from modules.smart_money import smart_money
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
        'message': '💰 سیستم تحلیل بورس',
        'modules': {
            'smart_money': '/smart_money'
        },
        'usage': 'برای فراخوانی هر ماژول: /{module_name}'
    })

@app.route('/smart_money')
def smart_money_endpoint():
    """ماژول پول هوشمند"""
    try:
        results = smart_money()
        jalali_date, current_time = get_current_time()

        return jsonify({
            'status': 'success',
            'module': 'smart_money',
            'timestamp': f"{jalali_date} {current_time}",
            'total_analyzed': len(results) if results else 0,
            'data': results,
            'summary': {
                'top_flow': results[0] if results else None,
                'active_flows': len([r for r in results if r['smart_money_amount'] >= 10])
            }
        })

    except Exception as e:
        logger.error(f"خطا در ماژول smart_money: {e}")
        return jsonify({
            'status': 'error',
            'module': 'smart_money',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 سیستم تحلیل بورس")
    print("="*50)
    print("🏠 صفحه اصلی: http://localhost:5000")
    print("💰 پول هوشمند: http://localhost:5000/smart_money")
    print("="*50)
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except Exception as e:
        print(f"❌ خطا: {e}")
