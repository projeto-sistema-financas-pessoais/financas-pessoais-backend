from pydantic import BaseModel, ConfigDict
from datetime import date
from typing import Optional
from decimal import Decimal

class FaturaSchema(BaseModel):
    id_conta: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class FaturaSchemaId(FaturaSchema):
    id_fatura: int
    

class FaturaSchemaUpdate(BaseModel):
    data_vencimento: Optional[date] = None
    data_fechamento: Optional[date] = None
    data_pagamento: Optional[date] = None
    id_conta: Optional[int] = None
    id_cartao_credito: Optional[int] = None
    
    
class FaturaSchemaInfo(FaturaSchema):
    data_vencimento: date
    data_fechamento: date
    data_pagamento: Optional[date]
    id_cartao_credito: int
    fatura_gastos: Decimal
    nome_conta: Optional[str] = None
    nome_cartao: Optional[str] = None

