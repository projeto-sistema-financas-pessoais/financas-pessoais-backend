from datetime import date
from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional

class UsuarioSchema(BaseModel):
    nome_completo: str
    data_nascimento: date
    email: EmailStr
    senha: str

class LoginDataSchema(BaseModel):
    email: EmailStr
    senha: str

class UpdateUsuarioSchema(BaseModel):
    nome_completo: Optional[str] = None
    data_nascimento: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


    