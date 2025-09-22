import re
from typing import Any, List, Optional
import logging

logger = logging.getLogger(__name__)

def is_valid_symbol(symbol: str) -> bool:
    """Validate Iranian stock symbol"""
    if not symbol or not isinstance(symbol, str):
        return False
    
    # Iranian stock symbols are typically Persian characters
    # This is a basic validation - adjust based on actual requirements
    symbol = symbol.strip()
    if len(symbol) < 1 or len(symbol) > 20:
        return False
    
    return True

def is_valid_api_key(api_key: str) -> bool:
    """Validate API key format"""
    if not api_key or not isinstance(api_key, str):
        return False
    
    api_key = api_key.strip()
    if len(api_key) < 10:  # Minimum length check
        return False
    
    if api_key == "your_api_key_here" or api_key == "YourApiKey":
        return False
    
    return True

def validate_date_range(start_date: Optional[str], end_date: Optional[str]) -> bool:
    """Validate date range"""
    # Add date validation logic here
    return True

def validate_numeric_range(value: Any, min_val: Optional[float] = None, max_val: Optional[float] = None) -> bool:
    """Validate numeric value is within range"""
    try:
        num_val = float(value)
        
        if min_val is not None and num_val < min_val:
            return False
        
        if max_val is not None and num_val > max_val:
            return False
        
        return True
        
    except (ValueError, TypeError):
        return False

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file operations"""
    if not filename:
        return "unnamed"
    
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip('. ')
    
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    
    return filename or "unnamed"
