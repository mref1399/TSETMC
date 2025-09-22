import os
from typing import Optional
from pydantic import BaseSettings, validator

class Settings(BaseSettings):
    # API Configuration
    brs_api_key: str
    brs_base_url: str = "https://BrsApi.ir/Api"
    api_timeout: int = 30
    api_retry_count: int = 3
    
    # Cache Configuration
    cache_duration: int = 300
    redis_url: Optional[str] = None
    
    # Logging Configuration
    log_level: str = "INFO"
    log_file: str = "logs/app.log"
    
    # Data Configuration
    data_dir: str = "data"
    cache_dir: str = "data/cache"
    
    @validator('brs_api_key')
    def api_key_must_not_be_empty(cls, v):
        if not v or v == "your_api_key_here":
            raise ValueError('BRS_API_KEY must be set')
        return v
    
    @validator('cache_dir', 'data_dir')
    def create_directories(cls, v):
        os.makedirs(v, exist_ok=True)
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()
