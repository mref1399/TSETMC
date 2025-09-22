import requests
import json
import time
from typing import Dict, List, Optional
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

class BrsApiClient:
    """Client for BRS API communication"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.brs_api_key
        self.base_url = base_url or settings.brs_base_url
        self.session = requests.Session()
        
        # Setup default headers
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        })
        
    def _make_request(self, endpoint: str, params: Dict = None, retry_count: Optional[int] = None) -> Optional[Dict]:
        """Make API request with error handling"""
        if params is None:
            params = {}
        
        params['key'] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        retry_count = retry_count or settings.api_retry_count
        
        for attempt in range(retry_count):
            try:
                response = self.session.get(
                    url, 
                    params=params, 
                    timeout=settings.api_timeout
                )
                
                if response.status_code == 200:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        return {"raw_data": response.text}
                        
                elif response.status_code == 429:  # Rate limit
                    logger.warning("Rate limit reached. Waiting 60 seconds...")
                    time.sleep(60)
                    continue
                    
                else:
                    logger.error(f"HTTP Error {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout:
                logger.error(f"Timeout error on attempt {attempt + 1}")
                time.sleep(2 ** attempt)
                
            except requests.exceptions.ConnectionError:
                logger.error(f"Connection error on attempt {attempt + 1}")
                time.sleep(2 ** attempt)
                
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                
        return None
    
    def get_all_symbols(self) -> Optional[List[Dict]]:
        """Get all stock symbols"""
        logger.info("Fetching all symbols...")
        result = self._make_request("Tsetmc/AllSymbols.php")
        
        if result and isinstance(result, dict) and 'symbols' in result:
            return result['symbols']
        elif result and isinstance(result, list):
            return result
        
        return None
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Get symbol information"""
        logger.info(f"Fetching info for symbol: {symbol}")
        return self._make_request("Tsetmc/SymbolInfo.php", {"symbol": symbol})
    
    def get_market_watch(self) -> Optional[List[Dict]]:
        """Get market watch data"""
        logger.info("Fetching market watch data...")
        result = self._make_request("Tsetmc/MarketWatch.php")
        
        if result and isinstance(result, dict) and 'data' in result:
            return result['data']
        elif result and isinstance(result, list):
            return result
            
        return None
    
    def get_symbol_history(self, symbol: str, days: int = 30) -> Optional[List[Dict]]:
        """Get symbol price history"""
        logger.info(f"Fetching {days} days history for {symbol}")
        return self._make_request("Tsetmc/History.php", {
            "symbol": symbol,
            "days": days
        })
    
    def get_intraday_data(self, symbol: str) -> Optional[Dict]:
        """Get intraday data"""
        logger.info(f"Fetching intraday data for {symbol}")
        return self._make_request("Tsetmc/Intraday.php", {"symbol": symbol})
    
    def get_index_data(self, index_name: str = "TEDPIX") -> Optional[Dict]:
        """Get index data"""
        logger.info(f"Fetching index data for {index_name}")
        return self._make_request("Tsetmc/Index.php", {"index": index_name})
    
    def search_symbol(self, query: str) -> Optional[List[Dict]]:
        """Search symbols"""
        logger.info(f"Searching for symbol: {query}")
        return self._make_request("Tsetmc/Search.php", {"q": query})
