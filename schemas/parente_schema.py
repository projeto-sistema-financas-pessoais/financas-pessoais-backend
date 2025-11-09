from pydantic import BaseModel, ConfigDict
from typing import Optional

class ParenteSchema(BaseModel):
    nome: str
    email: Optional[str] = None
    grau_parentesco: str
    ativo : Optional[bool] = True

    model_config = ConfigDict(from_attributes=True)


class ParenteSchemaId(ParenteSchema):
    id_usuario: int
    id_parente: int

class ParenteSchemaUpdate(ParenteSchema):
    grau_parentesco: Optional[str] = None
    nome: Optional[str] = None
    email: Optional[str] = None
    ativo : Optional[bool] = True

class ParenteSchemaCobranca(BaseModel):
    mes: int
    ano: int
    id_parente: int