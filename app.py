import os
import requests
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from datetime import datetime
import json
import concurrent.futures
import threading
from functools import lru_cache

load_dotenv()

app = Flask(__name__)

# لیست سیمبل‌های خاص برای بررسی پول هوشمند
TARGET_SYMBOLS = [
    'وخارزم', 'فرآور', 'سدور', 'سخاش', 'گشان', 
    'وساپا', 'ورنا', 'ختوقا', 'فباهنر', 'شرانل', 
    'شاوان', 'رکیش'
]

# Cache برای نگهداری نتایج موقت
REQUEST_CACHE = {}
CACHE_DURATION = 60  # 60 ثانیه

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "BRS API Service is running!",
        "endpoints": {
            "/": "This page",
            "/health": "Health check",
            "/symbols": "Get all symbols from BRS API",
            "/smart-money": "Detect smart money flow for specific symbols (FAST)",
            "/smart-money/<symbol>": "Get smart money for specific symbol"
        },
        "target_symbols": TARGET_SYMBOLS,
        "optimization": "Multi-threading + Caching enabled"
    })

def get_stock_data(symbol, api_key, headers):
    """تابع دریافت داده یک سهم - برای threading"""
    try:
        # چک کردن cache
        cache_key = f"{symbol}_{int(datetime.now().timestamp() // CACHE_DURATION)}"
        if cache_key in REQUEST_CACHE:
            return symbol, REQUEST_CACHE[cache_key], None
            
        stock_url = f"https://BrsApi.ir/Api/Tsetmc/StockInfo.php?key={api_key}&symbol={symbol}"
        
        # کم کردن timeout
        response = requests.get(stock_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # ذخیره در cache
            REQUEST_CACHE[cache_key] = data
            return symbol, data, None
        else:
            return symbol, None, f"API Error: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return symbol, None, "Timeout"
    except Exception as e:
        return symbol, None, str(e)

@app.route('/smart-money', methods=['GET'])
def get_smart_money():
    """تشخیص ورود پول هوشمند به سهم‌های خاص - نسخه سریع"""
    start_time = datetime.now()
    
    try:
        api_key = os.getenv('BRSAPI_KEY')
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/106.0.0.0",
            "Accept": "application/json, text/plain, */*"
        }
        
        smart_money_stocks = []
        failed_symbols = []
        
        # استفاده از ThreadPoolExecutor برای parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            # ایجاد future objects برای همه سهم‌ها
            future_to_symbol = {
                executor.submit(get_stock_data, symbol, api_key, headers): symbol 
                for symbol in TARGET_SYMBOLS
            }
            
            # پردازش نتایج به محض آماده شدن
            for future in concurrent.futures.as_completed(future_to_symbol, timeout=30):
                symbol, stock_data, error = future.result()
                
                if error:
                    failed_symbols.append({
                        "symbol": symbol,
                        "error": error
                    })
                    continue
                    
                if stock_data:
                    try:
                        # تحلیل سریع پول هوشمند
                        smart_money_analysis = analyze_smart_money_fast(stock_data, symbol)
                        
                        if smart_money_analysis['has_smart_money']:
                            smart_money_stocks.append(smart_money_analysis)
                    except Exception as e:
                        failed_symbols.append({
                            "symbol": symbol,
                            "error": f"Analysis error: {str(e)}"
                        })
        
        # محاسبه زمان اجرا
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # تعیین پیام بر اساس نتایج
        if len(smart_money_stocks) == 0:
            message = "🚫 هیچ پول هوشمندی در سهم‌های هدف شناسایی نشد"
            status = "no_smart_money_detected"
        else:
            message = f"✅ پول هوشمند در {len(smart_money_stocks)} سهم شناسایی شد"
            status = "smart_money_detected"
        
        return jsonify({
            "success": True,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "execution_time_seconds": round(execution_time, 2),
            "target_symbols": TARGET_SYMBOLS,
            "analyzed_symbols": len(TARGET_SYMBOLS),
            "smart_money_detected": len(smart_money_stocks),
            "failed_symbols": len(failed_symbols),
            "stocks_with_smart_money": smart_money_stocks,
            "failed_analyses": failed_symbols if failed_symbols else None,
            "performance": {
                "cache_hits": len([k for k in REQUEST_CACHE.keys() if k.startswith(str(int(datetime.now().timestamp() // CACHE_DURATION)))]),
                "parallel_processing": True,
                "max_workers": 6
            }
        })
        
    except concurrent.futures.TimeoutError:
        return jsonify({
            "success": False,
            "error": "Request timeout - API taking too long",
            "message": "❌ درخواست منقضی شد - API خیلی کند است",
            "execution_time_seconds": (datetime.now() - start_time).total_seconds()
        }), 408
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "❌ خطا در بررسی پول هوشمند",
            "execution_time_seconds": (datetime.now() - start_time).total_seconds()
        }), 500

def analyze_smart_money_fast(stock_data, symbol):
    """نسخه سریع تحلیل پول هوشمند - فقط معیارهای اصلی"""
    try:
        analysis = {
            "symbol": symbol,
            "has_smart_money": False,
            "confidence": 0,
            "entry_time": None,
            "signals": [],
            "key_metrics": {}
        }
        
        if not stock_data or not isinstance(stock_data, dict):
            return analysis
            
        # استخراج داده‌های اساسی
        current_price = float(stock_data.get('last_price', 0))
        volume = float(stock_data.get('volume', 0))
        value = float(stock_data.get('value', 0))
        avg_volume_30d = float(stock_data.get('avg_volume_30d', volume * 0.8))
        
        # معیار 1: حجم نسبی (سریع)
        relative_volume = volume / avg_volume_30d if avg_volume_30d > 0 else 1
        
        if relative_volume >= 2.5:
            analysis["signals"].append(f"📈 حجم بالا: {relative_volume:.1f}x")
            analysis["confidence"] += 40
        elif relative_volume >= 1.8:
            analysis["signals"].append(f"📊 حجم مناسب: {relative_volume:.1f}x")
            analysis["confidence"] += 25
            
        # معیار 2: ارزش معامله (سریع)
        min_value_threshold = max(1_000_000_000, current_price * 1_000_000)
        value_ratio = value / min_value_threshold if min_value_threshold > 0 else 0
        
        if value_ratio >= 5:
            analysis["signals"].append(f"💰 ارزش عالی: {value/1e9:.1f}B")
            analysis["confidence"] += 35
        elif value_ratio >= 2:
            analysis["signals"].append(f"💵 ارزش خوب: {value/1e9:.1f}B")
            analysis["confidence"] += 20
            
        # معیار 3: زمان‌بندی (سریع)
        current_hour = datetime.now().hour
        if 9 <= current_hour <= 11:
            analysis["signals"].append("⏰ زمان مناسب")
            analysis["confidence"] += 15
            
        # تعیین نهایی
        if analysis["confidence"] >= 50:
            analysis["has_smart_money"] = True
            analysis["entry_time"] = datetime.now().isoformat()
            
        # متریک‌های کلیدی
        analysis["key_metrics"] = {
            "relative_volume": round(relative_volume, 1),
            "value_billions": round(value/1e9, 1),
            "confidence": analysis["confidence"],
            "price": current_price
        }
            
        return analysis
        
    except Exception as e:
        return {
            "symbol": symbol,
            "has_smart_money": False,
            "error": str(e),
            "confidence": 0,
            "signals": [],
            "key_metrics": {}
        }

@app.route('/smart-money/<symbol>', methods=['GET'])
def get_symbol_smart_money(symbol):
    """تحلیل پول هوشمند برای یک نماد خاص"""
    try:
        api_key = os.getenv('BRSAPI_KEY')
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/106.0.0.0",
            "Accept": "application/json, text/plain, */*"
        }
        
        is_target_symbol = symbol in TARGET_SYMBOLS
        
        # استفاده از تابع سریع
        symbol_result, stock_data, error = get_stock_data(symbol, api_key, headers)
        
        if error:
            return jsonify({
                "success": False,
                "error": error,
                "message": f"❌ خطا در دریافت اطلاعات {symbol}"
            }), 500
            
        # تحلیل سریع
        analysis = analyze_smart_money_fast(stock_data, symbol)
        
        if analysis['has_smart_money']:
            message = f"✅ پول هوشمند در {symbol} شناسایی شد"
            status = "smart_money_detected"
        else:
            message = f"🚫 پول هوشمند در {symbol} شناسایی نشد"
            status = "no_smart_money_detected"
        
        return jsonify({
            "success": True,
            "symbol": symbol,
            "is_target_symbol": is_target_symbol,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "symbol": symbol,
            "error": str(e),
            "message": f"❌ خطا در تحلیل {symbol}"
        }), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "target_symbols": TARGET_SYMBOLS,
        "target_symbols_count": len(TARGET_SYMBOLS),
        "cache_size": len(REQUEST_CACHE),
        "optimization": "Multi-threading + Caching enabled"
    })

# پاک‌سازی cache قدیمی
@app.before_request
def cleanup_cache():
    current_time = int(datetime.now().timestamp() // CACHE_DURATION)
    keys_to_remove = [k for k in REQUEST_CACHE.keys() if not k.endswith(str(current_time))]
    for key in keys_to_remove:
        REQUEST_CACHE.pop(key, None)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
