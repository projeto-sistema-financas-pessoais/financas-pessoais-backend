from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession

from core.configs import settings 



engine = create_async_engine(
    settings.DB_URL,
    pool_pre_ping=True,        # Verifica se a conexão está ativa antes de usá-la
    pool_recycle=3600,        # Recicla conexões após 3600 segundos (1 hora)
)


Session: AsyncSession = sessionmaker(
    autocommit= False,
    autoflush= False,
    expire_on_commit= False,
    class_= AsyncSession,
    bind = engine,
)

