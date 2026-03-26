"""配置管理模块"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    # 应用配置
    app_name: str = "NOTAM Parser"
    debug: bool = False

    # API 配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # LLM 配置
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    llm_timeout: int = 30
    llm_max_retries: int = 3

    # 数据库配置
    database_url: Optional[str] = None  # SQLite 路径，如 ".notam.db"

    # 缓存配置
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 缓存存活时间（秒）

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings
