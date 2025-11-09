from pydantic import BaseModel, ConfigDict, field_validator
from models.enums import TipoMovimentacao, TipoCategoria
from typing import Optional
from decimal import Decimal

class CategoriaSchema(BaseModel):
    nome: str
    tipo_categoria: TipoCategoria
    modelo_categoria: TipoMovimentacao
    valor_categoria: Optional[Decimal] = None
    nome_icone: str
    ativo : Optional[bool] = True
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator("valor_categoria", mode="before")
    def handle_empty_string(cls, value):
        if value == "":
            return None
        return value


class CategoriaSchemaUpdate(BaseModel):
    nome: Optional[str] = None
    tipo_categoria: Optional[TipoCategoria] = None
    modelo_categoria: Optional[TipoMovimentacao] = None
    valor_categoria: Optional[Decimal] = None
    nome_icone: Optional[str] = None
    ativo : Optional[bool] = True
    
    @field_validator("valor_categoria", mode="before")
    def handle_empty_string(cls, value):
        if value == "":
            return None
        return value
      
class CategoriaSchemaId(CategoriaSchema):
    id_usuario: int
    id_categoria: int
    valor_categoria: Optional[Decimal] = None
    
    @field_validator("valor_categoria", mode="before")
    def handle_empty_string(cls, value):
        if value == "":
            return None
        return value


