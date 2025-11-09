from fastapi import APIRouter
from api.v1.endpoints import usuario, conta, categoria, cartao_de_credito, fatura, parente, movimentacao

api_router = APIRouter()
api_router.include_router(usuario.router, prefix='/usuarios', tags=["usuarios"])
api_router.include_router(conta.router, prefix='/contas', tags=["contas"])
api_router.include_router(categoria.router, prefix='/categorias', tags=["categorias"])
api_router.include_router(cartao_de_credito.router, prefix='/cartaoCredito', tags=["cartao_credito"])
api_router.include_router(fatura.router, prefix='/fatura', tags=["fatura"])
api_router.include_router(parente.router, prefix='/parente', tags=["parente"])
api_router.include_router(movimentacao.router, prefix='/movimentacao', tags=["movimentacao"])

