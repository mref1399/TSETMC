import requests
import re
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify
import threading
import gc
import logging
from dataclasses import dataclass
import os
from collections import defaultdict

# Configuration Management
@dataclass
class Config:
    MAX_WORKERS: int = int(os.getenv('MAX_WORKERS', 8))
    CACHE_DURATION: int = int(os.getenv('CACHE_DURATION', 60))
    REQUEST_TIMEOUT: int = int(os.getenv('REQUEST_TIMEOUT', 10))
    API_BASE_URL: str = os.getenv('API_BASE_URL', 'http://old.tsetmc.com')
    MAX_CACHE_SIZE: int = int(os.getenv('MAX_CACHE_SIZE', 1000))

config = Config()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Performance Metrics
METRICS = defaultdict(list)
CACHE_HITS = 0
CACHE_MISSES = 0

# Global cache with thread safety
REQUEST_CACHE = {}
cache_lock = threading.Lock()

# Session with connection pooling
session = requests.Session()
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

retry_strategy = Retry(
    total=3,
    backoff_factor=0.1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=15, pool_maxsize=25)
session.mount("http://", adapter)
session.mount("https://", adapter)

# همه سهام‌های بورس تهران (نمونه گسترده)
TARGET_SYMBOLS = [
    # بانک‌ها
    '778253364357513', '35700344742885862', '46348559193224090', '35828394729201797',
    '778253364480056', '35700344847892417', '17302480709999821', '33694683594744209',
    
    # پتروشیمی
    '18249962325560969', '12925422174241869', '38761402489687313', '44891854946084002',
    '9211775239375291', '6380266985415173', '77607686677439233', '54410052518174820',
    
    # فولاد و معدن
    '71483646978964608', '13515285141324007', '61919693120463977', '17256071160472705',
    '17638742387805057', '62235992343204880', '33284194325454868', '4734776654497965',
    
    # نفت و گاز
    '7745894403636165', '21075262043560181', '44891854946084002', '76401267505881205',
    '46618266999893169', '17638742387805057', '28284512495657573', '31257663563524101',
    
    # خودرو
    '65883838195688438', '46651230535529136', '54410052518174820', '47676425952754965',
    '29837848785875113', '8577135366993672', '23962711729094049', '35828394729201797',
    
    # دارو و درمان
    '9111445462715329', '34461547122740389', '9211775239375291', '18249962325560969',
    '15983736993307333', '26878417446096477', '73262239950394692', '16693221131072644',
    
    # غذایی
    '14576636646376525', '60126538636866580', '33987841116007652', '65547030581161596',
    '48950709086749693', '62070132173522900', '4734776654497965', '53169862549042081',
    
    # سیمان
    '11763102142752641', '71483646978964608', '16693221131072644', '28284512495657573',
    '33987841116007652', '13515285141324007', '62235992343204880', '54410052518174820',
    
    # مخابرات و فناوری
    '9211775239375291', '73262239950394692', '15983736993307333', '34461547122740389',
    '53169862549042081', '77607686677439233', '26878417446096477', '65547030581161596',
    
    # سایر صنایع
    '48950709086749693', '60126538636866580', '62070132173522900', '44891854946084002',
    '76401267505881205', '46618266999893169', '31257663563524101', '29837848785875113',
    '8577135366993672', '23962711729094049', '47676425952754965', '65883838195688438',
    '46651230535529136', '17302480709999821', '33694683594744209', '35700344847892417'
]

def track_performance(func):
    """Decorator برای ردیابی عملکرد"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        METRICS[func.__name__].append(execution_time)
        return result
    return wrapper

@app.before_request
def cleanup_cache():
    """پاک‌سازی cache قدیمی"""
    global REQUEST_CACHE, CACHE_HITS, CACHE_MISSES
    
    with cache_lock:
        current_time = time.time()
        expired_keys = [
            key for key, (data, timestamp) in REQUEST_CACHE.items()
            if current_time - timestamp > config.CACHE_DURATION
        ]
        
        for key in expired_keys:
            del REQUEST_CACHE[key]
        
        # Memory management
        if len(REQUEST_CACHE) > config.MAX_CACHE_SIZE:
            # حذف قدیمی‌ترین entries
            sorted_items = sorted(REQUEST_CACHE.items(), key=lambda x: x[1][1])
            keys_to_remove = [item[0] for item in sorted_items[:config.MAX_CACHE_SIZE//2]]
            for key in keys_to_remove:
                del REQUEST_CACHE[key]
            gc.collect()

def get_cached_data(key):
    """دریافت داده از cache"""
    global CACHE_HITS, CACHE_MISSES
    
    with cache_lock:
        if key in REQUEST_CACHE:
            data, timestamp = REQUEST_CACHE[key]
            if time.time() - timestamp < config.CACHE_DURATION:
                CACHE_HITS += 1
                return data
            else:
                del REQUEST_CACHE[key]
    
    CACHE_MISSES += 1
    return None

def set_cached_data(key, data):
    """ذخیره داده در cache"""
    with cache_lock:
        REQUEST_CACHE[key] = (data, time.time())

def parse_stock_data(data, symbol):
    """تجزیه داده‌های سهم"""
    try:
        parts = data.split(',')
        if len(parts) < 10:
            return None
        
        return {
            'symbol': symbol,
            'last_price': float(parts[2]) if parts[2] != '' else 0,
            'close_price': float(parts[3]) if parts[3] != '' else 0,
            'first_price': float(parts[4]) if parts[4] != '' else 0,
            'yesterday_price': float(parts[5]) if parts[5] != '' else 0,
            'volume': int(parts[6]) if parts[6] != '' else 0,
            'value': float(parts[7]) if parts[7] != '' else 0,
            'min_price': float(parts[8]) if parts[8] != '' else 0,
            'max_price': float(parts[9]) if parts[9] != '' else 0,
            'count': int(parts[10]) if len(parts) > 10 and parts[10] != '' else 0,
        }
    except (ValueError, IndexError) as e:
        logger.warning(f"خطا در تجزیه داده سهم {symbol}: {e}")
        return None

@track_performance
def get_stock_data(symbol, max_retries=3):
    """دریافت داده‌های سهم با retry mechanism"""
    # بررسی cache
    cached_data = get_cached_data(symbol)
    if cached_data:
        return cached_data
    
    url = f"{config.API_BASE_URL}/tsev2/data/instinfodata.aspx?i={symbol}&c=27%20"
    
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            if response.text and len(response.text) > 10:
                stock_data = parse_stock_data(response.text, symbol)
                if stock_data:
                    # ذخیره در cache
                    set_cached_data(symbol, stock_data)
                    return stock_data
                    
        except Exception as e:
            logger.warning(f"تلاش {attempt + 1} برای {symbol} ناموفق: {e}")
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))  # Exponential backoff
    
    logger.error(f"دریافت داده برای سهم {symbol} پس از {max_retries} تلاش ناموفق بود")
    return None

def calculate_relative_volume(current_volume, avg_volume):
    """محاسبه حجم نسبی"""
    if avg_volume == 0:
        return 0
    return current_volume / avg_volume

def calculate_price_change_percent(current_price, yesterday_price):
    """محاسبه درصد تغییر قیمت"""
    if yesterday_price == 0:
        return 0
    return ((current_price - yesterday_price) / yesterday_price) * 100

@track_performance
def analyze_smart_money_fast(stock_data):
    """تحلیل سریع پول هوشمند"""
    if not stock_data:
        return {
            'symbol': 'N/A',
            'smart_money_score': 0,
            'analysis': 'داده دریافت نشد',
            'recommendation': 'نامشخص'
        }
    
    try:
        # محاسبات اساسی
        volume = stock_data.get('volume', 0)
        value = stock_data.get('value', 0)
        last_price = stock_data.get('last_price', 0)
        yesterday_price = stock_data.get('yesterday_price', 0)
        count = stock_data.get('count', 0)
        
        # محاسبه متریک‌های کلیدی
        price_change_percent = calculate_price_change_percent(last_price, yesterday_price)
        avg_trade_size = value / count if count > 0 else 0
        
        # امتیازدهی پول هوشمند (0-100)
        smart_money_score = 0
        analysis_points = []
        
        # بررسی حجم معامله (وزن: 30%)
        if volume > 1000000:  # حجم بالا
            smart_money_score += 30
            analysis_points.append("حجم معامله بالا")
        elif volume > 500000:  # حجم متوسط
            smart_money_score += 20
            analysis_points.append("حجم معامله متوسط")
        else:
            smart_money_score += 5
            analysis_points.append("حجم معامله پایین")
        
        # بررسی ارزش معامله (وزن: 25%)
        if value > 10000000000:  # ارزش بالا (10 میلیارد)
            smart_money_score += 25
            analysis_points.append("ارزش معامله بالا")
        elif value > 5000000000:  # ارزش متوسط (5 میلیارد)
            smart_money_score += 18
            analysis_points.append("ارزش معامله متوسط")
        else:
            smart_money_score += 8
            analysis_points.append("ارزش معامله پایین")
        
        # بررسی اندازه متوسط معامله (وزن: 20%)
        if avg_trade_size > 50000000:  # معاملات بزرگ
            smart_money_score += 20
            analysis_points.append("معاملات بزرگ (نهادی)")
        elif avg_trade_size > 20000000:  # معاملات متوسط
            smart_money_score += 12
            analysis_points.append("معاملات متوسط")
        else:
            smart_money_score += 3
            analysis_points.append("معاملات کوچک (خرد)")
        
        # بررسی تغییر قیمت (وزن: 15%)
        if abs(price_change_percent) > 5:  # تغییر قیمت قابل توجه
            smart_money_score += 15
            analysis_points.append(f"تغییر قیمت قابل توجه: {price_change_percent:.2f}%")
        elif abs(price_change_percent) > 2:
            smart_money_score += 8
            analysis_points.append(f"تغییر قیمت متوسط: {price_change_percent:.2f}%")
        
        # بررسی تعداد معاملات (وزن: 10%)
        if count > 1000:  # تعداد معاملات بالا
            smart_money_score += 10
            analysis_points.append("تعداد معاملات بالا")
        elif count > 500:
            smart_money_score += 6
            analysis_points.append("تعداد معاملات متوسط")
        
        # تعیین توصیه
        if smart_money_score >= 80:
            recommendation = "خرید قوی - حضور پررنگ پول هوشمند"
        elif smart_money_score >= 65:
            recommendation = "خرید - نشانه‌های مثبت پول هوشمند"
        elif smart_money_score >= 50:
            recommendation = "نگهداری - وضعیت متعادل"
        elif smart_money_score >= 35:
            recommendation = "احتیاط - ضعف نسبی"
        else:
            recommendation = "فروش - عدم حضور پول هوشمند"
        
        return {
            'symbol': stock_data.get('symbol', 'N/A'),
            'smart_money_score': round(smart_money_score, 2),
            'analysis': ' | '.join(analysis_points),
            'recommendation': recommendation,
            'metrics': {
                'volume': volume,
                'value': value,
                'price_change_percent': round(price_change_percent, 2),
                'avg_trade_size': round(avg_trade_size, 0),
                'trade_count': count,
                'last_price': last_price
            }
        }
        
    except Exception as e:
        logger.error(f"خطا در تحلیل سهم {stock_data.get('symbol', 'N/A')}: {e}")
        return {
            'symbol': stock_data.get('symbol', 'N/A'),
            'smart_money_score': 0,
            'analysis': f'خطا در تحلیل: {str(e)}',
            'recommendation': 'نامشخص'
        }

def calculate_cache_hit_rate():
    """محاسبه نرخ موفقیت cache"""
    total_requests = CACHE_HITS + CACHE_MISSES
    if total_requests == 0:
        return 0
    return (CACHE_HITS / total_requests) * 100

@track_performance
def get_smart_money():
    """تحلیل پول هوشمند برای همه سهام‌ها"""
    start_time = time.time()
    results = []
    
    try:
        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            # ارسال همزمان درخواست‌ها
            future_to_symbol = {
                executor.submit(get_stock_data, symbol): symbol 
                for symbol in TARGET_SYMBOLS
            }
            
            # دریافت نتایج با timeout
            for future in as_completed(future_to_symbol, timeout=45):
                symbol = future_to_symbol[future]
                try:
                    stock_data = future.result()
                    analysis = analyze_smart_money_fast(stock_data)
                    results.append(analysis)
                except Exception as e:
                    logger.error(f"خطا در پردازش سهم {symbol}: {e}")
                    results.append({
                        'symbol': symbol,
                        'smart_money_score': 0,
                        'analysis': f'خطا در پردازش: {str(e)}',
                        'recommendation': 'نامشخص'
                    })
        
        # مرتب‌سازی بر اساس امتیاز پول هوشمند
        results.sort(key=lambda x: x.get('smart_money_score', 0), reverse=True)
        
        execution_time = time.time() - start_time
        
        return {
            'status': 'success',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_stocks': len(TARGET_SYMBOLS),
            'analyzed_stocks': len(results),
            'execution_time_seconds': round(execution_time, 2),
            'performance': {
                'cache_hit_rate': round(calculate_cache_hit_rate(), 2),
                'cache_size': len(REQUEST_CACHE),
                'max_workers': config.MAX_WORKERS,
                'threading_active': threading.active_count()
            },
            'top_recommendations': [
                r for r in results[:10] if r.get('smart_money_score', 0) > 0
            ],
            'all_analysis': results
        }
        
    except Exception as e:
        logger.error(f"خطای کلی در تحلیل: {e}")
        return {
            'status': 'error',
            'message': f'خطا در تحلیل پول هوشمند: {str(e)}',
            'execution_time_seconds': round(time.time() - start_time, 2)
        }

@app.route('/smart-money', methods=['GET'])
def smart_money_endpoint():
    """API endpoint برای تحلیل پول هوشمند"""
    try:
        result = get_smart_money()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطای سرور: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """بررسی وضعیت سیستم"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'config': {
            'max_workers': config.MAX_WORKERS,
            'cache_duration': config.CACHE_DURATION,
            'request_timeout': config.REQUEST_TIMEOUT,
            'max_cache_size': config.MAX_CACHE_SIZE
        },
        'performance': {
            'cache_size': len(REQUEST_CACHE),
            'cache_hit_rate': round(calculate_cache_hit_rate(), 2),
            'active_threads': threading.active_count(),
            'average_execution_times': {
                func: round(sum(times)/len(times), 2) if times else 0
                for func, times in METRICS.items()
            }
        },
        'total_symbols': len(TARGET_SYMBOLS)
    })

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """دریافت متریک‌های عملکرد تفصیلی"""
    return jsonify({
        'cache_statistics': {
            'hits': CACHE_HITS,
            'misses': CACHE_MISSES,
            'hit_rate': round(calculate_cache_hit_rate(), 2),
            'cache_size': len(REQUEST_CACHE)
        },
        'performance_metrics': {
            func: {
                'count': len(times),
                'average': round(sum(times)/len(times), 2) if times else 0,
                'min': round(min(times), 2) if times else 0,
                'max': round(max(times), 2) if times else 0
            }
            for func, times in METRICS.items()
        },
        'system': {
            'active_threads': threading.active_count(),
            'total_symbols': len(TARGET_SYMBOLS)
        }
    })

@app.after_request
def cleanup_memory(response):
    """پاکسازی حافظه پس از هر درخواست"""
    if len(REQUEST_CACHE) > config.MAX_CACHE_SIZE:
        gc.collect()
    return response

if __name__ == '__main__':
    logger.info(f"شروع سرویس تحلیل پول هوشمند با {len(TARGET_SYMBOLS)} سهم")
    logger.info(f"تنظیمات: MAX_WORKERS={config.MAX_WORKERS}, CACHE_DURATION={config.CACHE_DURATION}s")
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
