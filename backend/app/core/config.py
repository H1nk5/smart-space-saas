"""
应用配置 - 环境变量管理
"""
import secrets
import warnings

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    APP_NAME: str = "SmartSpace SaaS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8080

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./smart_space.db"
    DATABASE_ECHO: bool = False

    # JWT配置
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8小时

    # Comma-separated origins. Keep the API private to the local frontend by default.
    CORS_ORIGINS: str = "http://127.0.0.1:5173,http://localhost:5173"

    # 多租户配置
    DEFAULT_TENANT_ID: Optional[str] = None

    # 分页配置
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    @model_validator(mode="after")
    def validate_security_settings(self):
        secret = self.SECRET_KEY.strip()
        if secret and len(secret.encode("utf-8")) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 bytes")
        if not secret:
            if not self.DEBUG:
                raise ValueError("SECRET_KEY is required when DEBUG=false")
            self.SECRET_KEY = secrets.token_urlsafe(48)
            warnings.warn(
                "SECRET_KEY is unset; using an ephemeral development secret",
                RuntimeWarning,
                stacklevel=2,
            )
        return self

    @property
    def cors_origins(self):
        return list(dict.fromkeys(
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ))

settings = Settings()
