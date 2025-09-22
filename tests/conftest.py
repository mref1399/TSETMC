import pytest
import os
from unittest.mock import Mock

@pytest.fixture
def mock_api_key():
    return "test_api_key_12345"

@pytest.fixture
def mock_brs_api_response():
    return {
        "symbols": [
            {"symbol": "فولاد", "name": "فولاد مبارکه اصفهان"},
            {"symbol": "خودro", "name": "خودروسازی ایران"}
        ]
    }

@pytest.fixture(autouse=True)
def setup_test_env(tmp_path):
    # Set test environment variables
    os.environ["BRS_API_KEY"] = "test_api_key"
    os.environ["CACHE_DURATION"] = "60"
    os.environ["LOG_LEVEL"] = "DEBUG"
    
    # Use temporary directory for test data
    test_data_dir = tmp_path / "test_data"
    test_cache_dir = tmp_path / "test_cache"
    test_logs_dir = tmp_path / "test_logs"
    
    test_data_dir.mkdir()
    test_cache_dir.mkdir()
    test_logs_dir.mkdir()
    
    os.environ["DATA_DIR"] = str(test_data_dir)
    os.environ["CACHE_DIR"] = str(test_cache_dir)
    os.environ["LOG_FILE"] = str(test_logs_dir / "test.log")
    
    yield
    
    # Cleanup
    for key in ["BRS_API_KEY", "CACHE_DURATION", "LOG_LEVEL", "DATA_DIR", "CACHE_DIR", "LOG_FILE"]:
        os.environ.pop(key, None)
