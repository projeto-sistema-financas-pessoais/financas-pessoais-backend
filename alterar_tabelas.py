from core.configs import settings
from core.database import engine

import logging

# Ativa o log SQL do SQLAlchemy para ver os comandos SQL que estão sendo executados
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


async def create_tables() -> None:
    import models.__all_models
    print ('Criando as tabelas no banco de dados...')
    
    async with engine.begin() as conn:
        await conn.run_sync(settings.DBBaseModel.metadata.drop_all) #para que possa excluir caso faça alguma alteração
        # await conn.run_sync(settings.DBBaseModel.metadata.create_all)
        
    print('Tabelas excluidas com sucesso')
    
if __name__ == '__main__':
    import asyncio
    asyncio.run(create_tables())
    