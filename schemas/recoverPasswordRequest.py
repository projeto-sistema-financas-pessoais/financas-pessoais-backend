from pydantic import BaseModel

class RecoverPasswordRequest(BaseModel):
    email: str