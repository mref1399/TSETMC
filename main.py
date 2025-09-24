from flask import Flask, jsonify
import logging
from modules.stock_data import StockDataFetcher

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/stocks')
def stocks_endpoint():
    fetcher = StockDataFetcher()
    data = fetcher.fetch_all_from_file('symbols.txt')
    return jsonify({
        'status': 'success',
        'total_symbols': len(data),
        'data': data
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
