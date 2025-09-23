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

def safe_float(value, default=0.0):
    """تبدیل ایمن به float"""
    try:
        if value == '' or value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    """تبدیل ایمن به int"""
    try:
        if value == '' or value is None:
            return default
        return int(float(value))  # ابتدا به float تبدیل می‌کنیم سپس به int
    except (ValueError, TypeError):
        return default

def parse_stock_data(data, symbol):
    """تجزیه اصلاح شده داده‌های سهم"""
    try:
        # پاک‌سازی داده‌ها
        data = data.strip()
        if not data or len(data) < 10:
            logger.warning(f"داده خالی یا کوتاه برای سهم {symbol}")
            return None
        
        # تقسیم بر اساس کاما و حذف فضاهای خالی
        parts = [part.strip() for part in data.split(',')]
        
        if len(parts) < 11:
            logger.warning(f"تعداد فیلدهای کافی برای سهم {symbol} وجود ندارد: {len(parts)} فیلد")
            return None
        
        # استخراج داده‌ها با بررسی صحت
        parsed_data = {
            'symbol': symbol,
            'last_price': safe_float(parts[2]),
            'close_price': safe_float(parts[3]),  
            'first_price': safe_float(parts[4]),
            'yesterday_price': safe_float(parts[5]),
            'volume': safe_int(parts[6]),
            'value': safe_float(parts[7]),
            'min_price': safe_float(parts[8]),
            'max_price': safe_float(parts[9]),
            'count': safe_int(parts[10]),
        }
        
        # اعتبارسنجی داده‌ها
        if parsed_data['last_price'] <= 0:
            logger.warning(f"قیمت نامعتبر برای سهم {symbol}: {parsed_data['last_price']}")
            return None
            
        # محاسبه اندازه متوسط معامله
        if parsed_data['count'] > 0 and parsed_data['value'] > 0:
            parsed_data['avg_trade_size'] = parsed_data['value'] / parsed_data['count']
        else:
            parsed_data['avg_trade_size'] = 0
            
        # محاسبه درصد تغییر قیمت
        if parsed_data['yesterday_price'] > 0:
            parsed_data['price_change_percent'] = (
                (parsed_data['last_price'] - parsed_data['yesterday_price']) / 
                parsed_data['yesterday_price']
            ) * 100
        else:
            parsed_data['price_change_percent'] = 0
        
        logger.info(f"داده سهم {symbol} با موفقیت پردازش شد")
        return parsed_data
        
    except Exception as e:
        logger.error(f"خطا در تجزیه داده سهم {symbol}: {str(e)}")
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
                time.sleep(0.5 * (attempt + 1))
    
    logger.error(f"دریافت داده برای سهم {symbol} پس از {max_retries} تلاش ناموفق بود")
    return None

@track_performance
def analyze_smart_money_enhanced(stock_data):
    """تحلیل بهبود یافته پول هوشمند"""
    if not stock_data:
        return {
            'symbol': 'N/A',
            'smart_money_score': 0,
            'analysis': 'داده دریافت نشد',
            'recommendation': 'نامشخص',
            'risk_level': 'بالا'
        }
    
    try:
        # استخراج داده‌های محاسبه شده
        volume = stock_data.get('volume', 0)
        value = stock_data.get('value', 0)
        last_price = stock_data.get('last_price', 0)
        yesterday_price = stock_data.get('yesterday_price', 0)
        count = stock_data.get('count', 0)
        avg_trade_size = stock_data.get('avg_trade_size', 0)
        price_change_percent = stock_data.get('price_change_percent', 0)
        
        # امتیازدهی پول هوشمند (0-100)
        smart_money_score = 0
        analysis_points = []
        risk_factors = []
        
        # 1. بررسی حجم معامله (وزن: 25%)
        if volume > 50000000:  # حجم فوق‌العاده
            smart_money_score += 25
            analysis_points.append("🔥 حجم معامله فوق‌العاده")
        elif volume > 10000000:  # حجم بالا
            smart_money_score += 20
            analysis_points.append("📈 حجم معامله بالا")
        elif volume > 1000000:  # حجم متوسط رو به بالا
            smart_money_score += 15
            analysis_points.append("📊 حجم معامله متوسط")
        elif volume > 100000:  # حجم پایین
            smart_money_score += 8
            analysis_points.append("📉 حجم معامله پایین")
            risk_factors.append("حجم پایین")
        else:
            smart_money_score += 2
            analysis_points.append("⚠️ حجم معامله بسیار پایین")
            risk_factors.append("حجم بسیار پایین")
        
        # 2. بررسی ارزش معامله (وزن: 25%)
        value_billions = value / 1000000000  # تبدیل به میلیارد
        if value_billions > 100:  # بیش از 100 میلیارد
            smart_money_score += 25
            analysis_points.append(f"💰 ارزش معامله فوق‌العاده: {value_billions:.1f} میلیارد")
        elif value_billions > 50:  # بیش از 50 میلیارد
            smart_money_score += 20
            analysis_points.append(f"💎 ارزش معامله بالا: {value_billions:.1f} میلیارد")
        elif value_billions > 10:  # بیش از 10 میلیارد
            smart_money_score += 15
            analysis_points.append(f"💵 ارزش معامله خوب: {value_billions:.1f} میلیارد")
        elif value_billions > 1:  # بیش از 1 میلیارد
            smart_money_score += 10
            analysis_points.append(f"💳 ارزش معامله متوسط: {value_billions:.1f} میلیارد")
        else:
            smart_money_score += 3
            analysis_points.append(f"💴 ارزش معامله پایین: {value_billions:.1f} میلیارد")
            risk_factors.append("ارزش پایین")
        
        # 3. بررسی اندازه متوسط معامله (وزن: 20%)
        avg_millions = avg_trade_size / 1000000  # تبدیل به میلیون
        if avg_millions > 100:  # معاملات نهادی بزرگ
            smart_money_score += 20
            analysis_points.append(f"🏛️ معاملات نهادی بزرگ: {avg_millions:.1f}M")
        elif avg_millions > 50:  # معاملات نهادی
            smart_money_score += 15
            analysis_points.append(f"🏢 معاملات نهادی: {avg_millions:.1f}M")
        elif avg_millions > 10:  # معاملات متوسط
            smart_money_score += 10
            analysis_points.append(f"🏪 معاملات متوسط: {avg_millions:.1f}M")
        elif avg_millions > 1:  # معاملات کوچک
            smart_money_score += 5
            analysis_points.append(f"🏠 معاملات کوچک: {avg_millions:.1f}M")
        else:
            smart_money_score += 1
            analysis_points.append(f"🪙 معاملات خرد: {avg_millions:.1f}M")
            risk_factors.append("معاملات خرد")
        
        # 4. بررسی تغییر قیمت (وزن: 15%)
        if price_change_percent > 7:  # رشد قوی
            smart_money_score += 15
            analysis_points.append(f"🚀 رشد قوی: +{price_change_percent:.1f}%")
        elif price_change_percent > 3:  # رشد خوب
            smart_money_score += 12
            analysis_points.append(f"📈 رشد مثبت: +{price_change_percent:.1f}%")
        elif price_change_percent > 0:  # رشد ملایم
            smart_money_score += 8
            analysis_points.append(f"🔼 رشد ملایم: +{price_change_percent:.1f}%")
        elif price_change_percent > -3:  # کاهش ملایم
            smart_money_score += 5
            analysis_points.append(f"🔽 کاهش ملایم: {price_change_percent:.1f}%")
        elif price_change_percent > -7:  # کاهش قابل توجه
            smart_money_score += 2
            analysis_points.append(f"📉 کاهش قابل توجه: {price_change_percent:.1f}%")
            risk_factors.append("کاهش قیمت")
        else:  # سقوط
            smart_money_score += 0
            analysis_points.append(f"🔻 سقوط: {price_change_percent:.1f}%")
            risk_factors.append("سقوط قیمت")
        
        # 5. بررسی تعداد معاملات (وزن: 10%)
        if count > 10000:  # تعداد معاملات فوق‌العاده
            smart_money_score += 10
            analysis_points.append(f"🔥 تعداد معاملات بالا: {count:,}")
        elif count > 5000:  # تعداد معاملات بالا
            smart_money_score += 8
            analysis_points.append(f"📊 تعداد معاملات خوب: {count:,}")
        elif count > 1000:  # تعداد معاملات متوسط
            smart_money_score += 6
            analysis_points.append(f"📈 تعداد معاملات متوسط: {count:,}")
        elif count > 100:  # تعداد معاملات کم
            smart_money_score += 3
            analysis_points.append(f"📉 تعداد معاملات کم: {count:,}")
        else:
            smart_money_score += 1
            analysis_points.append(f"⚠️ تعداد معاملات بسیار کم: {count:,}")
            risk_factors.append("تعداد معاملات کم")
        
        # 6. ضریب نقدینگی (وزن: 5%)
        if volume > 0 and last_price > 0:
            liquidity_ratio = (volume * last_price) / value if value > 0 else 0
            if liquidity_ratio > 0.8:
                smart_money_score += 5
                analysis_points.append("💧 نقدینگی عالی")
            elif liquidity_ratio > 0.5:
                smart_money_score += 3
                analysis_points.append("💧 نقدینگی خوب")
            else:
                smart_money_score += 1
                analysis_points.append("💧 نقدینگی پایین")
                risk_factors.append("نقدینگی کم")
        
        # تعیین سطح ریسک
        if len(risk_factors) == 0:
            risk_level = "پایین"
        elif len(risk_factors) <= 2:
            risk_level = "متوسط"
        else:
            risk_level = "بالا"
        
        # تعیین توصیه بر اساس امتیاز و ریسک
        if smart_money_score >= 85 and risk_level == "پایین":
            recommendation = "🎯 خرید قوی - فرصت عالی"
        elif smart_money_score >= 75:
            recommendation = "✅ خرید - نشانه‌های قوی پول هوشمند"
        elif smart_money_score >= 60:
            recommendation = "📈 خرید تدریجی - وضعیت مطلوب"
        elif smart_money_score >= 45:
            recommendation = "⚖️ نگهداری - وضعیت متعادل"
        elif smart_money_score >= 30:
            recommendation = "⚠️ احتیاط - ضعف نسبی"
        elif smart_money_score >= 20:
            recommendation = "📉 فروش تدریجی - عدم حضور پول هوشمند"
        else:
            recommendation = "🔻 فروش - وضعیت نامطلوب"
        
        return {
            'symbol': stock_data.get('symbol', 'N/A'),
            'smart_money_score': round(smart_money_score, 1),
            'analysis': ' | '.join(analysis_points),
            'recommendation': recommendation,
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'metrics': {
                'volume': f"{volume:,}",
                'value_billions': round(value_billions, 2),
                'price_change_percent': round(price_change_percent, 2),
                'avg_trade_size_millions': round(avg_millions, 2),
                'trade_count': f"{count:,}",
                'last_price': f"{last_price:,}",
                'yesterday_price': f"{yesterday_price:,}"
            }
        }
        
    except Exception as e:
        logger.error(f"خطا در تحلیل سهم {stock_data.get('symbol', 'N/A')}: {e}")
        return {
            'symbol': stock_data.get('symbol', 'N/A'),
            'smart_money_score': 0,
            'analysis': f'خطا در تحلیل: {str(e)}',
            'recommendation': '❌ نامشخص - خطا در تحلیل',
            'risk_level': 'بالا'
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
    successful_analysis = 0
    failed_analysis = 0
    
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
                    if stock_data:
                        analysis = analyze_smart_money_enhanced(stock_data)
                        results.append(analysis)
                        successful_analysis += 1
                    else:
                        results.append({
                            'symbol': symbol,
                            'smart_money_score': 0,
                            'analysis': 'داده دریافت نشد',
                            'recommendation': '❌ نامشخص - عدم دسترسی به داده',
                            'risk_level': 'بالا'
                        })
                        failed_analysis += 1
                except Exception as e:
                    logger.error(f"خطا در پردازش سهم {symbol}: {e}")
                    results.append({
                        'symbol': symbol,
                        'smart_money_score': 0,
                        'analysis': f'خطا در پردازش: {str(e)}',
                        'recommendation': '❌ نامشخص - خطا در پردازش',
                        'risk_level': 'بالا'
                    })
                    failed_analysis += 1
        
        # مرتب‌سازی بر اساس امتیاز پول هوشمند
        results.sort(key=lambda x: x.get('smart_money_score', 0), reverse=True)
        
        # دسته‌بندی نتایج
        top_picks = [r for r in results if r.get('smart_money_score', 0) >= 70]
        good_options = [r for r in results if 50 <= r.get('smart_money_score', 0) < 70]
        watch_list = [r for r in results if 30 <= r.get('smart_money_score', 0) < 50]
        avoid_list = [r for r in results if r.get('smart_money_score', 0) < 30]
        
        execution_time = time.time() - start_time
        
        return {
            'status': 'success',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'total_stocks': len(TARGET_SYMBOLS),
                'successful_analysis': successful_analysis,
                'failed_analysis': failed_analysis,
                'success_rate': round((successful_analysis / len(TARGET_SYMBOLS)) * 100, 1),
                'top_picks_count': len(top_picks),
                'good_options_count': len(good_options),
                'watch_list_count': len(watch_list),
                'avoid_list_count': len(avoid_list)
            },
            'execution_time_seconds': round(execution_time, 2),
            'performance': {
                'cache_hit_rate': round(calculate_cache_hit_rate(), 2),
                'cache_size': len(REQUEST_CACHE),
                'max_workers': config.MAX_WORKERS,
                'threading_active': threading.active_count()
            },
            'categorized_results': {
                'top_picks': top_picks[:10],  # بهترین 10 انتخاب
                'good_options': good_options[:10],  # 10 گزینه خوب
                'watch_list': watch_list[:5],  # 5 سهم قابل نظر
                'avoid_list': avoid_list[:5]  # 5 سهم اجتناب
            },
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
    logger.info(f"🚀 شروع سرویس تحلیل پول هوشمند با {len(TARGET_SYMBOLS)} سهم")
    logger.info(f"⚙️ تنظیمات: MAX_WORKERS={config.MAX_WORKERS}, CACHE_DURATION={config.CACHE_DURATION}s")
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
