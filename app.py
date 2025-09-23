import requests
import json
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import logging
import pytz
import jdatetime
from flask import Flask, jsonify, request
import gc

# تنظیمات لاگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@dataclass
class Config:
    max_workers: int = 50  # تعداد thread همزمان
    cache_duration: int = 60  # مدت کش (ثانیه)
    request_timeout: int = 10
    max_retries: int = 3
    batch_size: int = 100

config = Config()

# متغیرهای سراسری
REQUEST_CACHE = {}
CACHE_HITS = 0
CACHE_MISSES = 0
cache_lock = threading.Lock()
performance_metrics = {}

# لیست تمام نمادهای بورس (دریافت خودکار)
ALL_SYMBOLS = []

class TehranStockAPI:
    BASE_URL = "http://old.tsetmc.com/tsev2/data/instinfodata.aspx"
    SYMBOL_LIST_URL = "http://service.tsetmc.com/tsev2/data/MarketWatchPlus.aspx"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_all_symbols(self) -> List[str]:
        """دریافت لیست تمام نمادهای بورس"""
        try:
            response = self.session.get(self.SYMBOL_LIST_URL, timeout=config.request_timeout)
            if response.status_code == 200:
                # پارس کردن پاسخ برای استخراج نمادها
                data = response.text
                symbols = self._parse_symbols_from_response(data)
                logger.info(f"دریافت {len(symbols)} نماد از بورس")
                return symbols
        except Exception as e:
            logger.error(f"خطا در دریافت لیست نمادها: {e}")
            return self._get_backup_symbols()

    def _parse_symbols_from_response(self, data: str) -> List[str]:
        """استخراج نمادها از پاسخ API"""
        symbols = []
        try:
            # پارس کردن داده‌های CSV-like
            lines = data.strip().split('\n')
            for line in lines:
                parts = line.split(',')
                if len(parts) > 2:
                    symbol = parts[2].strip()  # نماد معمولاً در ستون سوم است
                    if symbol and len(symbol) <= 10:  # فیلتر نمادهای معتبر
                        symbols.append(symbol)
        except Exception as e:
            logger.error(f"خطا در پارس نمادها: {e}")
        
        return list(set(symbols))  # حذف تکراری‌ها

    def _get_backup_symbols(self) -> List[str]:
        """لیست پشتیبان نمادهای مهم بورس"""
        return [
            'فولاد', 'پترو', 'وبملت', 'شپنا', 'فجر', 'خودرو', 'ساپا', 'شبندر',
            'وپارس', 'حکمت', 'تاپیکو', 'شستا', 'تامین', 'پاسا', 'دی', 'نوری',
            'ثسعادت', 'ثبهساز', 'کرمان', 'جم', 'وتجارت', 'فراسا', 'مپنا', 'خساپا',
            'کگهر', 'خزر', 'حتوکا', 'رمپنا', 'سینا', 'کرتون', 'شاخص', 'فرابورس'
        ]

# تابع‌های کمکی
def safe_float(value: Any, default: float = 0.0) -> float:
    """تبدیل ایمن به float"""
    try:
        if value is None or value == '':
            return default
        return float(str(value).replace(',', ''))
    except (ValueError, TypeError):
        return default

def safe_int(value: Any, default: int = 0) -> int:
    """تبدیل ایمن به int"""
    try:
        if value is None or value == '':
            return default
        return int(float(str(value).replace(',', '')))
    except (ValueError, TypeError):
        return default

def track_performance(func):
    """Decorator برای ردیابی عملکرد"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        
        func_name = func.__name__
        if func_name not in performance_metrics:
            performance_metrics[func_name] = []
        performance_metrics[func_name].append(duration)
        
        return result
    return wrapper

# سیستم کش
def get_cache_key(symbol: str) -> str:
    """ایجاد کلید کش"""
    return f"stock_{symbol}_{int(time.time() // config.cache_duration)}"

def is_cache_valid(timestamp: float) -> bool:
    """بررسی اعتبار کش"""
    return time.time() - timestamp < config.cache_duration

def cleanup_cache():
    """پاکسازی کش قدیمی"""
    with cache_lock:
        current_time = time.time()
        expired_keys = [
            key for key, (data, timestamp) in REQUEST_CACHE.items()
            if not is_cache_valid(timestamp)
        ]
        for key in expired_keys:
            del REQUEST_CACHE[key]
        
        if len(REQUEST_CACHE) > 1000:  # محدودیت حافظه
            gc.collect()

# دریافت داده‌های سهم
@track_performance
def fetch_stock_data(symbol: str, api_client: TehranStockAPI) -> Optional[Dict]:
    """دریافت داده‌های سهم از API"""
    for attempt in range(config.max_retries):
        try:
            params = {'i': symbol, 'c': '1'}
            response = api_client.session.get(
                api_client.BASE_URL,
                params=params,
                timeout=config.request_timeout
            )
            
            if response.status_code == 200:
                data = response.text.strip()
                if data and len(data) > 10:
                    return parse_stock_data(data, symbol)
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"تلاش {attempt + 1}: خطا در دریافت {symbol}: {e}")
            if attempt < config.max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
    
    return None

def fetch_stock_data_cached(symbol: str, api_client: TehranStockAPI) -> Optional[Dict]:
    """دریافت داده‌های سهم با کش"""
    global CACHE_HITS, CACHE_MISSES
    
    cache_key = get_cache_key(symbol)
    
    with cache_lock:
        if cache_key in REQUEST_CACHE:
            data, timestamp = REQUEST_CACHE[cache_key]
            if is_cache_valid(timestamp):
                CACHE_HITS += 1
                return data

    # داده در کش نیست
    CACHE_MISSES += 1
    stock_data = fetch_stock_data(symbol, api_client)
    
    if stock_data:
        with cache_lock:
            REQUEST_CACHE[cache_key] = (stock_data, time.time())
    
    return stock_data

def parse_stock_data(raw_data: str, symbol: str) -> Dict:
    """پارس کردن داده‌های خام سهم"""
    try:
        parts = raw_data.split(',')
        if len(parts) < 10:
            return {}
        
        return {
            'symbol': symbol,
            'last_price': safe_float(parts[2]),
            'close_price': safe_float(parts[3]),
            'first_price': safe_float(parts[4]),
            'yesterday_price': safe_float(parts[5]),
            'volume': safe_int(parts[6]),
            'value': safe_float(parts[7]),
            'min_price': safe_float(parts[8]),
            'max_price': safe_float(parts[9]),
            'trade_count': safe_int(parts[10]) if len(parts) > 10 else 0,
        }
    except Exception as e:
        logger.error(f"خطا در پارس داده‌های {symbol}: {e}")
        return {}

# تحلیل پول هوشمند
@track_performance
def analyze_smart_money_complete(stock_data: Dict, symbol: str) -> Dict:
    """تحلیل کامل پول هوشمند"""
    
    # تنظیم زمان
    tehran_tz = pytz.timezone('Asia/Tehran')
    current_time = datetime.now(tehran_tz)
    jalali_date = jdatetime.datetime.now().strftime('%Y/%m/%d')
    gregorian_date = current_time.strftime('%Y/%m/%d')
    time_str = current_time.strftime('%H:%M:%S')
    
    # استخراج داده‌ها
    volume = stock_data.get('volume', 0)
    last_price = stock_data.get('last_price', 0)
    value = stock_data.get('value', 0)
    yesterday_price = stock_data.get('yesterday_price', 0)
    trade_count = stock_data.get('trade_count', 0)
    max_price = stock_data.get('max_price', 0)
    min_price = stock_data.get('min_price', 0)
    
    if not all([volume, last_price, value]):
        return {
            'symbol': symbol,
            'error': 'داده‌های ناکافی',
            'smart_money_amount': 0,
            'currency_unit': 'تومان',
            'jalali_date': jalali_date,
            'time': time_str
        }
    
    # محاسبات اصلی
    price_change = last_price - yesterday_price if yesterday_price else 0
    price_change_percent = (price_change / yesterday_price * 100) if yesterday_price else 0
    avg_trade_size = value / trade_count if trade_count else 0
    
    # محاسبه پول هوشمند (ارزش کل معاملات)
    smart_money_raw = volume * last_price
    
    # تعیین واحد مناسب
    if smart_money_raw >= 1e12:  # بیش از 1000 میلیارد
        smart_money_amount = round(smart_money_raw / 1e12, 2)
        currency_unit = "هزار میلیارد تومان"
    elif smart_money_raw >= 1e9:  # بیش از 1 میلیارد
        smart_money_amount = round(smart_money_raw / 1e9, 2)
        currency_unit = "میلیارد تومان"
    elif smart_money_raw >= 1e6:  # بیش از 1 میلیون
        smart_money_amount = round(smart_money_raw / 1e6, 2)
        currency_unit = "میلیون تومان"
    else:
        smart_money_amount = round(smart_money_raw, 0)
        currency_unit = "تومان"
    
    # امتیازدهی (0-100)
    volume_score = min(volume / 1e6 * 10, 100)  # بر اساس میلیون سهم
    value_score = min(value / 1e11 * 10, 100)   # بر اساس 100 میلیارد تومان
    activity_score = min(trade_count / 100 * 10, 100)  # بر اساس تعداد معاملات
    price_momentum = abs(price_change_percent) * 2  # قدرت حرکت قیمت
    
    smart_money_score = (volume_score * 0.3 + value_score * 0.4 + 
                        activity_score * 0.2 + price_momentum * 0.1)
    smart_money_score = min(smart_money_score, 100)
    
    # توصیه سرمایه‌گذاری
    if smart_money_score >= 80:
        recommendation = "خرید قوی"
        category = "Top Picks"
    elif smart_money_score >= 60:
        recommendation = "خرید"
        category = "Good Options"
    elif smart_money_score >= 40:
        recommendation = "نگهداری"
        category = "Watch List"
    elif smart_money_score >= 20:
        recommendation = "احتیاط"
        category = "Risky"
    else:
        recommendation = "فروش"
        category = "Avoid List"
    
    # سطح ریسک
    volatility = ((max_price - min_price) / last_price * 100) if last_price else 0
    if volatility > 5:
        risk_level = "بالا"
    elif volatility > 2:
        risk_level = "متوسط"
    else:
        risk_level = "پایین"
    
    return {
        'symbol': symbol,
        'smart_money_amount': smart_money_amount,
        'currency_unit': currency_unit,
        'smart_money_score': round(smart_money_score, 2),
        'recommendation': recommendation,
        'category': category,
        'risk_level': risk_level,
        'jalali_date': jalali_date,
        'gregorian_date': gregorian_date,
        'time': time_str,
        'full_datetime': f"{jalali_date} - {time_str}",
        'market_data': {
            'last_price': last_price,
            'price_change': round(price_change, 0),
            'price_change_percent': round(price_change_percent, 2),
            'volume': volume,
            'trade_count': trade_count,
            'avg_trade_size': round(avg_trade_size, 0),
            'min_price': min_price,
            'max_price': max_price
        },
        'analysis_scores': {
            'volume_score': round(volume_score, 2),
            'value_score': round(value_score, 2),
            'activity_score': round(activity_score, 2),
            'price_momentum': round(price_momentum, 2)
        }
    }

# API Endpoints
@app.route('/analyze-all-stocks', methods=['GET'])
@track_performance
def analyze_all_stocks():
    """تحلیل تمام سهام بورس"""
    try:
        start_time = time.time()
        api_client = TehranStockAPI()
        
        # دریافت لیست تمام نمادها
        if not ALL_SYMBOLS:
            ALL_SYMBOLS.extend(api_client.get_all_symbols())
        
        if not ALL_SYMBOLS:
            return jsonify({
                'status': 'error', 
                'message': 'نتوانست لیست نمادها را دریافت کند'
            }), 500
        
        logger.info(f"شروع تحلیل {len(ALL_SYMBOLS)} نماد...")
        
        results = []
        failed_symbols = []
        
        # پردازش به صورت batch برای مدیریت بهتر حافظه
        for i in range(0, len(ALL_SYMBOLS), config.batch_size):
            batch_symbols = ALL_SYMBOLS[i:i + config.batch_size]
            
            with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
                future_to_symbol = {
                    executor.submit(fetch_stock_data_cached, symbol, api_client): symbol 
                    for symbol in batch_symbols
                }
                
                for future in as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        stock_data = future.result()
                        if stock_data and len(stock_data) > 3:
                            analysis = analyze_smart_money_complete(stock_data, symbol)
                            results.append(analysis)
                        else:
                            failed_symbols.append(symbol)
                            
                    except Exception as e:
                        logger.error(f"خطا در تحلیل {symbol}: {e}")
                        failed_symbols.append(symbol)
            
            # پاکسازی کش پس از هر batch
            if i % (config.batch_size * 2) == 0:
                cleanup_cache()
        
        # مرتب‌سازی بر اساس مقدار پول هوشمند
        results.sort(key=lambda x: x.get('smart_money_amount', 0), reverse=True)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # آمار کلی
        total_smart_money = sum(r.get('smart_money_amount', 0) for r in results)
        top_movers = [r for r in results if r.get('smart_money_score', 0) >= 70]
        
        return jsonify({
            'status': 'success',
            'summary': {
                'total_symbols_processed': len(results),
                'failed_symbols': len(failed_symbols),
                'processing_time_seconds': round(processing_time, 2),
                'cache_hit_rate': f"{CACHE_HITS/(CACHE_HITS+CACHE_MISSES)*100:.1f}%" if (CACHE_HITS+CACHE_MISSES) > 0 else "0%",
                'top_movers_count': len(top_movers),
                'total_market_value': f"{total_smart_money:.2f} (combined units)"
            },
            'top_10_smart_money': results[:10],
            'top_movers': top_movers[:20],
            'all_data': results,
            'failed_symbols': failed_symbols,
            'generated_at': datetime.now(pytz.timezone('Asia/Tehran')).strftime('%Y/%m/%d %H:%M:%S')
        })
        
    except Exception as e:
        logger.error(f"خطای کلی در تحلیل: {e}")
        return jsonify({
            'status': 'error', 
            'message': f'خطا در پردازش: {str(e)}'
        }), 500

@app.route('/quick-scan', methods=['GET'])
def quick_scan():
    """اسکن سریع بازار - فقط اطلاعات اصلی"""
    try:
        api_client = TehranStockAPI()
        
        if not ALL_SYMBOLS:
            ALL_SYMBOLS.extend(api_client.get_all_symbols())
        
        # انتخاب تصادفی برای اسکن سریع
        import random
        sample_size = min(100, len(ALL_SYMBOLS))
        sample_symbols = random.sample(ALL_SYMBOLS, sample_size)
        
        results = []
        
        with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            future_to_symbol = {
                executor.submit(fetch_stock_data_cached, symbol, api_client): symbol 
                for symbol in sample_symbols
            }
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    stock_data = future.result()
                    if stock_data:
                        # تحلیل ساده
                        volume = stock_data.get('volume', 0)
                        last_price = stock_data.get('last_price', 0)
                        smart_money = volume * last_price
                        
                        if smart_money >= 1e9:  # حداقل 1 میلیارد
                            unit = "میلیارد تومان"
                            amount = round(smart_money / 1e9, 2)
                        else:
                            unit = "میلیون تومان" 
                            amount = round(smart_money / 1e6, 2)
                        
                        results.append({
                            'symbol': symbol,
                            'smart_money': amount,
                            'unit': unit,
                            'time': datetime.now(pytz.timezone('Asia/Tehran')).strftime('%H:%M:%S')
                        })
                except:
                    pass
        
        results.sort(key=lambda x: x['smart_money'], reverse=True)
        
        return jsonify({
            'status': 'success',
            'scan_type': 'quick',
            'sample_size': len(results),
            'top_20': results[:20],
            'scan_time': datetime.now(pytz.timezone('Asia/Tehran')).strftime('%H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """بررسی سلامت سیستم"""
    return jsonify({
        'status': 'healthy',
        'cache_size': len(REQUEST_CACHE),
        'cache_hits': CACHE_HITS,
        'cache_misses': CACHE_MISSES,
        'symbols_loaded': len(ALL_SYMBOLS),
        'server_time': datetime.now(pytz.timezone('Asia/Tehran')).strftime('%Y/%m/%d %H:%M:%S')
    })

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """متریک‌های عملکرد"""
    avg_times = {}
    for func_name, times in performance_metrics.items():
        if times:
            avg_times[func_name] = {
                'avg_time': round(sum(times) / len(times), 4),
                'calls': len(times),
                'total_time': round(sum(times), 4)
            }
    
    return jsonify({
        'performance': avg_times,
        'cache_stats': {
            'hits': CACHE_HITS,
            'misses': CACHE_MISSES,
            'hit_rate': f"{CACHE_HITS/(CACHE_HITS+CACHE_MISSES)*100:.1f}%" if (CACHE_HITS+CACHE_MISSES) > 0 else "0%",
            'cache_size': len(REQUEST_CACHE)
        },
        'system_info': {
            'symbols_count': len(ALL_SYMBOLS),
            'max_workers': config.max_workers,
            'cache_duration': config.cache_duration
        }
    })

# تنظیمات پیکربندی از درخواست
@app.route('/config', methods=['POST'])
def update_config():
    """به‌روزرسانی تنظیمات"""
    data = request.get_json()
    
    if 'max_workers' in data:
        config.max_workers = min(max(data['max_workers'], 10), 100)
    if 'cache_duration' in data:
        config.cache_duration = max(data['cache_duration'], 30)
    
    return jsonify({
        'status': 'updated',
        'config': {
            'max_workers': config.max_workers,
            'cache_duration': config.cache_duration,
            'batch_size': config.batch_size
        }
    })

if __name__ == '__main__':
    # پاکسازی دوره‌ای کش
    import threading
    
    def periodic_cleanup():
        while True:
            time.sleep(300)  # هر 5 دقیقه
            cleanup_cache()
    
    cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
    cleanup_thread.start()
    
    print("🚀 سرویس تحلیل پول هوشمند تمام سهام بورس آماده است!")
    print("📊 Endpoints:")
    print("  POST /analyze-all-stocks - تحلیل کامل تمام سهام")
    print("  GET  /quick-scan - اسکن سریع بازار") 
    print("  GET  /health - وضعیت سلامت")
    print("  GET  /metrics - متریک‌های عملکرد")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
