# Iran Stock Market Analyzer

A comprehensive Python library for Iranian stock market analysis with data fetching, technical indicators, and backtesting capabilities.

## Features

- Real-time data fetching from BrsApi
- Data caching system
- Technical indicators (Coming soon)
- Backtesting engine (Coming soon)
- Portfolio management (Coming soon)

## Installation

### Using Docker (Recommended)
```bash
git clone https://github.com/yourusername/iran-stock-analyzer.git
cd iran-stock-analyzer
docker build -t iran-stock-analyzer .
docker run -e BRS_API_KEY=your_api_key iran-stock-analyzer

### Local Installation

bash
pip install -r requirements.txt

## Quick Start

python
from src.data.data_manager import DataManager

# Initialize with your API key
data_manager = DataManager(api_key="your_api_key")

# Fetch all symbols
symbols = data_manager.get_all_symbols()
print(f"Found {len(symbols)} symbols")

# Get symbol info
symbol_info = data_manager.get_symbol_info("فولاد")
print(symbol_info)

## Configuration

Copy `.env.example` to `.env` and set your API key:

bash
cp .env.example .env

## License

MIT License


**requirements.txt**
```txt
requests>=2.31.0
pandas>=2.0.0
numpy>=1.24.0
python-dotenv>=1.0.0
redis>=4.5.0
schedule>=1.2.0
pydantic>=2.0.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
click>=8.1.0
rich>=13.0.0
