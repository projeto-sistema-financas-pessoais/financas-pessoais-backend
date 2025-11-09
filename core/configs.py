from typing import ClassVar, List

from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from sqlalchemy.orm import declarative_base
from decouple import config

class Settings(BaseSettings):
    """ 
    Configurações gerais usadas na aplicação
    """
    API_V1_STR: str = '/api/v1'
    DB_URL: str = config("DATABASE_URL")
    DBBaseModel: ClassVar = declarative_base() 
    URL_WEB: str = config("URL_WEB")
    
    JWT_SECRET: str = config("JWT_SECRET")  # em uma api real não se deve fornecer isso aqui pra ninguem
    """
    import secrets
    token: str = secrets.token_urlsafe(32)
    """
    ALGORITHM: str = config("ALGORITHM")
    EMAIL_ADDRESS: str = config("EMAIL_ADDRESS")
    EMAIL_PASSWORD: str = config("EMAIL_PASSWORD")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60*8
    
    model_config = ConfigDict(case_sensitive=True)


settings = Settings()