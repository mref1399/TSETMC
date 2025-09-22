import re
from typing import Any, Dict, List, Optional
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

def clean_persian_text(text: str) -> str:
    """Clean Persian text"""
    if not text:
        return ""
    
    # Remove extra whitespaces
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Convert Persian numbers to English
    persian_to_english = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
    }
    
    for persian, english in persian_to_english.items():
        text = text.replace(persian, english)
    
    return text

def safe_convert_to_number(value: Any, default: float = 0.0) -> float:
    """Safely convert value to number"""
    if value is None:
        return default
    
    if isinstance(value, (int, float)):
        return float(value)
    
    if isinstance(value, str):
        # Clean the string
        cleaned = clean_persian_text(value)
        cleaned = re.sub(r'[^\d.-]', '', cleaned)
        
        try:
            return float(cleaned) if cleaned else default
        except ValueError:
            logger.warning(f"Could not convert '{value}' to number, using default {default}")
            return default
    
    return default

def format_number(number: float, decimal_places: int = 2) -> str:
    """Format number with thousand separators"""
    return f"{number:,.{decimal_places}f}"

def get_jalali_date_string() -> str:
    """Get current Jalali date as string"""
    # This is a placeholder - you might want to use a proper Jalali library
    today = date.today()
    return today.strftime("%Y/%m/%d")

def create_cache_key(*args, **kwargs) -> str:
    """Create a cache key from arguments"""
    key_parts = []
    
    # Add positional arguments
    for arg in args:
        key_parts.append(str(arg))
    
    # Add keyword arguments
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={v}")
    
    return ":".join(key_parts)

def chunk_list(data: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks"""
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

def flatten_dict(d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
    """Flatten nested dictionary"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)
