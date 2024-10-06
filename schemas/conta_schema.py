from pydantic import BaseModel, EmailStr
from typing import Optional
from decimal import Decimal

from models.enums import TipoConta


class ContaSchema(BaseModel):
    descricao: Optional[str] = None
    tipo_conta: TipoConta
    nome: str
    nome_icone: str
    ativo : Optional[bool] = True
    
    class Config:
        from_attributes = True
    
class ContaSchemaId(ContaSchema):
    id_usuario: int
    id_conta: int
    saldo: Decimal
       
    
class ContaSchemaUpdate(ContaSchema):
    descricao: Optional[str] = None
    tipo_conta: Optional[TipoConta] = None
    nome: Optional[str] = None
    nome_icone: Optional[str] = None
    ativo : Optional[bool] = True