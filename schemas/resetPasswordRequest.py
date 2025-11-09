from pydantic import BaseModel

class ResetPasswordRequest(BaseModel):
    password:str