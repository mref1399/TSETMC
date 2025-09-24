from flask import Flask, jsonify
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from modules.smart_money import SmartMoneyDetector
except ImportError as e:
    logger.error(f"خطا در import ماژول‌ها: {e}")
    exit(1)

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
        'message': '💰 سیستم تحلیل بورس',
        'modules': {'smart_money': '/smart_money'},
        'usage': 'برای فراخوانی هر ماژول: /{module_name}'
    })

@app.route('/smart_money')
def smart_money_endpoint():
    try:
        detector = SmartMoneyDetector()
        results = detector.scan_symbols_from_file('symbols.txt')
        jalali_date, current_time = get_current_time()

        if results['status'] == 'error':
            return jsonify({
                'status': 'error',
                'message': results['message']
            }), 400

        return jsonify({
            'status': 'success',
            'module': 'smart_money',
            'timestamp': f"{jalali_date} {current_time}",
            'message': f"بررسی {results['total_symbols']} سهم انجام شد",
            'symbols_with_smart_money': [item['symbol'] for item in results['symbols_with_smart_money']],
            'smart_money_count': results['smart_money_count'],
            'total_symbols': results['total_symbols']
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
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
