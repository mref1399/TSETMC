import os
import requests
from flask import Flask, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

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
                "first_3_symbols": data[:3],
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

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
v
