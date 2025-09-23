import os
import requests
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()

app = Flask(__name__)

# لیست سیمبل‌های خاص برای بررسی پول هوشمند
TARGET_SYMBOLS = [
    'وخارزم', 'فرآور', 'سدور', 'سخاش', 'گشان', 
    'وساپا', 'ورنا', 'ختوقا', 'فباهنر', 'شرانل', 
    'شاوان', 'رکیش'
]

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "BRS API Service is running!",
        "endpoints": {
            "/": "This page",
            "/health": "Health check",
            "/symbols": "Get all symbols from BRS API",
            "/smart-money": "Detect smart money flow for specific symbols",
            "/smart-money/<symbol>": "Get smart money for specific symbol"
        },
        "target_symbols": TARGET_SYMBOLS
    })

@app.route('/symbols', methods=['GET'])
def get_symbols():
    try:
        api_key = os.getenv('BRSAPI_KEY')
        
        url = f"https://BrsApi.ir/Api/Tsetmc/AllSymbols.php?key={api_key}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/106.0.0.0",
            "Accept": "application/json, text/plain, */*"
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                "success": True,
                "total_symbols": len(data),
                "target_symbols": TARGET_SYMBOLS,
                "target_symbols_count": len(TARGET_SYMBOLS),
                "all_symbols": data
            })
        else:
            return jsonify({
                "success": False,
                "error": f"API Error: {response.status_code}",
                "response": response.text
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/smart-money', methods=['GET'])
def get_smart_money():
    """تشخیص ورود پول هوشمند به سهم‌های خاص"""
    try:
        api_key = os.getenv('BRSAPI_KEY')
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/106.0.0.0",
            "Accept": "application/json, text/plain, */*"
        }
        
        smart_money_stocks = []
        failed_symbols = []
        
        # بررسی فقط سیمبل‌های تعریف شده
        for symbol in TARGET_SYMBOLS:
            try:
                # دریافت اطلاعات معاملاتی هر نماد
                stock_url = f"https://BrsApi.ir/Api/Tsetmc/StockInfo.php?key={api_key}&symbol={symbol}"
                stock_response = requests.get(stock_url, headers=headers)
                
                if stock_response.status_code == 200:
                    stock_data = stock_response.json()
                    
                    # تحلیل پول هوشمند
                    smart_money_analysis = analyze_smart_money(stock_data, symbol)
                    
                    if smart_money_analysis['has_smart_money']:
                        smart_money_stocks.append(smart_money_analysis)
                else:
                    failed_symbols.append({
                        "symbol": symbol,
                        "error": f"API Error: {stock_response.status_code}"
                    })
                        
            except Exception as e:
                print(f"Error analyzing {symbol}: {str(e)}")
                failed_symbols.append({
                    "symbol": symbol,
                    "error": str(e)
                })
                continue
        
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
            "target_symbols": TARGET_SYMBOLS,
            "analyzed_symbols": len(TARGET_SYMBOLS),
            "smart_money_detected": len(smart_money_stocks),
            "failed_symbols": len(failed_symbols),
            "stocks_with_smart_money": smart_money_stocks,
            "failed_analyses": failed_symbols if failed_symbols else None
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "❌ خطا در بررسی پول هوشمند"
        }), 500

@app.route('/smart-money/<symbol>', methods=['GET'])
def get_symbol_smart_money(symbol):
    """تحلیل پول هوشمند برای یک نماد خاص"""
    try:
        api_key = os.getenv('BRSAPI_KEY')
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/106.0.0.0",
            "Accept": "application/json, text/plain, */*"
        }
        
        # چک کردن اینکه سیمبل در لیست هدف هست یا نه
        is_target_symbol = symbol in TARGET_SYMBOLS
        
        # دریافت اطلاعات نماد
        stock_url = f"https://BrsApi.ir/Api/Tsetmc/StockInfo.php?key={api_key}&symbol={symbol}"
        stock_response = requests.get(stock_url, headers=headers)
        
        if stock_response.status_code != 200:
            return jsonify({
                "success": False,
                "error": f"Failed to get data for symbol {symbol}: {stock_response.status_code}",
                "message": f"❌ خطا در دریافت اطلاعات {symbol}"
            }), 500
            
        stock_data = stock_response.json()
        
        # تحلیل پول هوشمند
        analysis = analyze_smart_money(stock_data, symbol)
        
        # تعیین پیام بر اساس نتایج
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

def analyze_smart_money(stock_data, symbol):
    """
    تحلیل ورود پول هوشمند به سهم - نسخه بهبود یافته با معیارهای نسبی
    """
    try:
        analysis = {
            "symbol": symbol,
            "has_smart_money": False,
            "confidence": 0,
            "entry_time": None,
            "signals": [],
            "volume_analysis": {},
            "price_analysis": {},
            "value_analysis": {},
            "raw_data": stock_data
        }
        
        if not stock_data or not isinstance(stock_data, dict):
            return analysis
            
        # استخراج داده‌های اساسی
        current_price = float(stock_data.get('last_price', 0))
        volume = float(stock_data.get('volume', 0))
        value = float(stock_data.get('value', 0))
        
        # داده‌های تاریخی (اگه موجود باشه) - اگه نباشه از امروز استفاده می‌کنیم
        avg_volume_30d = float(stock_data.get('avg_volume_30d', volume * 0.8))  # فرض: امروز 20% بیشتر از میانگین
        
        # معیار 1: نسبت حجم نسبی (Relative Volume)
        relative_volume = volume / avg_volume_30d if avg_volume_30d > 0 else 1
        
        if relative_volume >= 3:  # 3 برابر میانگین
            analysis["signals"].append(f"Very high relative volume: {relative_volume:.1f}x normal")
            analysis["confidence"] += 40
        elif relative_volume >= 2:  # 2 برابر میانگین
            analysis["signals"].append(f"High relative volume: {relative_volume:.1f}x normal")
            analysis["confidence"] += 30
        elif relative_volume >= 1.5:  # 1.5 برابر میانگین
            analysis["signals"].append(f"Above average volume: {relative_volume:.1f}x normal")
            analysis["confidence"] += 15
            
        # معیار 2: ارزش معامله نسبی (بر اساس قیمت سهم)
        # برای سهم‌های ارزان: حداقل 1 میلیارد
        # برای سهم‌های گران: متناسب با قیمت
        min_value_threshold = max(1_000_000_000, current_price * 1_000_000)  # حداقل 1 میلیارد یا 1M سهم
        
        if value >= min_value_threshold * 10:  # 10 برابر حداقل
            analysis["signals"].append(f"Exceptional trading value: {value:,.0f} Toman")
            analysis["confidence"] += 35
        elif value >= min_value_threshold * 5:  # 5 برابر حداقل
            analysis["signals"].append(f"Very high trading value: {value:,.0f} Toman")
            analysis["confidence"] += 25
        elif value >= min_value_threshold * 2:  # 2 برابر حداقل
            analysis["signals"].append(f"High trading value: {value:,.0f} Toman")
            analysis["confidence"] += 15
            
        # معیار 3: متوسط قیمت معامله vs قیمت فعلی
        avg_trade_price = value / volume if volume > 0 else current_price
        price_premium = ((avg_trade_price - current_price) / current_price * 100) if current_price > 0 else 0
        
        if price_premium >= 2:  # 2% پریمیوم
            analysis["signals"].append(f"Premium trading: {price_premium:.1f}% above market price")
            analysis["confidence"] += 25
        elif price_premium >= 1:  # 1% پریمیوم
            analysis["signals"].append(f"Slight premium: {price_premium:.1f}% above market price")
            analysis["confidence"] += 15
        elif price_premium <= -2:  # 2% تخفیف (فروش با عجله)
            analysis["signals"].append(f"Discount trading: {abs(price_premium):.1f}% below market (possible selling pressure)")
            analysis["confidence"] -= 10
            
        # معیار 4: اندازه معامله متوسط (تشخیص معامله‌های بزرگ)
        trade_count = stock_data.get('trade_count', 0)
        if trade_count > 0:
            avg_trade_size = value / trade_count
            large_trade_threshold = max(50_000_000, current_price * 50_000)  # حداقل 50M یا 50K سهم
            
            if avg_trade_size >= large_trade_threshold * 5:
                analysis["signals"].append(f"Very large trades: {avg_trade_size:,.0f} Toman per trade")
                analysis["confidence"] += 25
            elif avg_trade_size >= large_trade_threshold:
                analysis["signals"].append(f"Large trades detected: {avg_trade_size:,.0f} Toman per trade")
                analysis["confidence"] += 15
                
        # معیار 5: زمان‌بندی (ساعات مهم بازار)
        current_hour = datetime.now().hour
        current_minute = datetime.now().minute
        
        if 9 <= current_hour <= 10:  # ساعت اول بازار
            analysis["signals"].append("Early market activity (9-10 AM) - Smart money entry time")
            analysis["confidence"] += 15
        elif current_hour == 8 and current_minute >= 45:  # قبل شروع بازار
            analysis["signals"].append("Pre-market activity - Very early positioning")
            analysis["confidence"] += 20
        elif 13 <= current_hour <= 14:  # بعد از استراحت
            analysis["signals"].append("Post-break activity (1-2 PM)")
            analysis["confidence"] += 10
        elif current_hour >= 15:  # انتهای روز
            analysis["signals"].append("End of day activity - Possible position closing")
            analysis["confidence"] += 5
            
        # معیار 6: نسبت ارزش به کل بازار (اگه داده موجود باشه)
        market_total_value = stock_data.get('market_total_value', 0)
        if market_total_value > 0:
            market_share = (value / market_total_value) * 100
            if market_share >= 1:  # 1% از کل بازار
                analysis["signals"].append(f"High market share: {market_share:.2f}% of total market value")
                analysis["confidence"] += 20
                
        # تعیین وجود پول هوشمند
        if analysis["confidence"] >= 60:
            analysis["has_smart_money"] = True
            analysis["entry_time"] = datetime.now().isoformat()
            
        # اطمینان از اینکه confidence منفی نشه
        analysis["confidence"] = max(0, analysis["confidence"])
            
        # تحلیل‌های تفصیلی
        analysis["volume_analysis"] = {
            "current_volume": int(volume),
            "average_volume_30d": int(avg_volume_30d),
            "relative_volume": round(relative_volume, 2),
            "volume_category": (
                "exceptional" if relative_volume >= 3 else
                "very_high" if relative_volume >= 2 else
                "high" if relative_volume >= 1.5 else
                "normal"
            )
        }
        
        analysis["value_analysis"] = {
            "current_value": int(value),
            "minimum_threshold": int(min_value_threshold),
            "value_ratio": round(value / min_value_threshold, 1) if min_value_threshold > 0 else 0,
            "value_category": (
                "exceptional" if value >= min_value_threshold * 10 else
                "very_high" if value >= min_value_threshold * 5 else
                "high" if value >= min_value_threshold * 2 else
                "normal"
            )
        }
        
        analysis["price_analysis"] = {
            "current_price": current_price,
            "average_trade_price": round(avg_trade_price, 2),
            "premium_percentage": round(price_premium, 2),
            "trade_count": trade_count,
            "avg_trade_size": round(value / trade_count, 0) if trade_count > 0 else 0
        }
        
        return analysis
        
    except Exception as e:
        return {
            "symbol": symbol,
            "has_smart_money": False,
            "error": str(e),
            "confidence": 0,
            "signals": [],
            "raw_data": stock_data
        }

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "target_symbols": TARGET_SYMBOLS,
        "target_symbols_count": len(TARGET_SYMBOLS)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
