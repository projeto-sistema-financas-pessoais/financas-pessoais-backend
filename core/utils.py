from fastapi import HTTPException, status
import traceback
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


async def handle_db_exceptions(session, exc):
    # Rollback da sessão em caso de erro
    await session.rollback()
    
    traceback.print_exc()


    # Tratamento específico para IntegrityError
    if isinstance(exc, IntegrityError):
        print(f"Erro de integridade: {exc.orig}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro de integridade no banco de dados: {exc.orig}"
        )

    # Tratamento genérico para erros do SQLAlchemy
    elif isinstance(exc, SQLAlchemyError):
        print(f"Erro de banco de dados: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro no banco de dados, tente novamente mais tarde."
        )

    # Tratamento para qualquer outra exceção
    else:
        print(f"Erro geral: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro: {exc}"
        )
