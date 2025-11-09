from datetime import date
from pydantic import BaseModel, ConfigDict
from typing import Optional
from decimal import Decimal

class CartaoCreditoSchema(BaseModel):
    nome: str
    limite: Decimal
    nome_icone: str
    ativo: Optional[bool] = True

    model_config = ConfigDict(from_attributes=True)


class CartaoCreditoSchemaId(CartaoCreditoSchema):
    id_usuario: int
    id_cartao_credito: int
    limite_disponivel: Decimal
    dia_fechamento: Optional[int] = None
    data_fechamento: Optional[date] = None
    dia_vencimento: Optional[int] = None
    fatura_gastos: Optional[Decimal] = None

class CartaoCreditoSchemaUpdate(CartaoCreditoSchema):
    nome: Optional[str] = None
    limite: Optional[Decimal] = None
    nome_icone: Optional[str] = None
    ativo: Optional[bool] = None
    dia_fechamento: Optional[int] = None
    dia_vencimento: Optional[int] = None

class CartaoCreditoSchemaFatura(CartaoCreditoSchema):
    dia_fechamento: int
    dia_vencimento: int

