import email
import secrets
import string
from email.utils import formatdate
from fastapi import Request
import smtplib
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from models.usuario_model import UsuarioModel
from pydantic import EmailStr
from sqlalchemy.future import select
from typing import Optional, List
from core.security  import check_password
from pytz import timezone
from datetime import datetime, timedelta
from core.configs import settings
from jose import jwt, JWTError
from decouple import config
import asyncio



oauth2_schema = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/usuarios/login"
)

RECOVER_PASSWORD_SECRET = config('JWT_SECRET')

async def auth(email: EmailStr, senha: str, db: AsyncSession) -> Optional[UsuarioModel]:
    async with db as session:
        query = select(UsuarioModel).filter(UsuarioModel.email == email)
        result = await session.execute(query)
        usuario: UsuarioModel = result.scalars().unique().one_or_none()
        if not usuario:
            print("check=>>> user")

            return None
        if not check_password(senha, usuario.senha):
            return None
        
        return usuario
    
    
def _generate_token(tipo_token: str, tempo_vida: timedelta, sub:str) -> str:
    payload = {}
    sp = timezone('America/Sao_Paulo')
    expira = datetime.now(tz=sp) + tempo_vida
    
    payload["type"] = tipo_token
    payload["exp"] = expira
    payload["iat"] = datetime.now(tz=sp)
    payload["sub"] = str(sub)
    
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)

def generate_token_access(sub: str) -> str:
    # https://jwt.io
    
    return _generate_token(
        tipo_token='access_token',
        tempo_vida=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        sub = sub
    )
    
def generate_password(length: int = 8) -> str:
    characters = string.ascii_letters + string.digits
    password = "".join(secrets.choice(characters) for _ in range(length))
    return password

def send_email(email_data: dict, user_email: str) -> None:
    try:
        # Verifique se os dados de e-mail foram lidos corretamente
        sender_email = config("EMAIL_ADDRESS")
        sender_password = config("EMAIL_PASSWORD")

        print("Endereço de e-mail do remetente:", sender_email)
        print("Senha de aplicativo lida:", sender_password)

        # Configura a mensagem
        msg = email.message.EmailMessage()
        msg["Subject"] = email_data["email_subject"]
        msg["From"] = sender_email
        msg["To"] = user_email
        msg["Date"] = formatdate(localtime=True)
        msg.set_content(email_data["email_body"], subtype="html", charset="utf-8")

        # Conectar ao servidor SMTP do Gmail
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)  # Usa as credenciais
            server.send_message(msg)
    
    except Exception as e:
        raise Exception(f"Error occurred while sending email: {e}")


async def send_email_to_reset_password(request: Request, user_data, token: str, from_scfp_web: bool=True) -> None:
    
    if from_scfp_web:
        base_url = config('URL_WEB')
    else:
        base_url = config('DATABASE_URL_SINC')
    
    url = base_url + f'/login/redefinir-senha/{token}'
    email_data = {
        "email_subject": "Redefinição de senha - Finanças Pessoais",
        "email_body": f"""
                        <p style="font-size: medium;">Redefinição de senha - Finanças Pessoais</p>
                        <p style="font-size: medium;">Olá, <b>{user_data.nome_completo}</b>!</p>
                        <p style="font-size: medium;">Clique <a href="{url}">aqui</a> para redefinir sua senha. Lembre-se de que este link é válido por apenas 5 minutos. Se você não solicitou a redefinição de senha, ignore este e-mail.</p>
                        <p style="font-size: medium;">Atenciosamente,<br>Equipe Finanças Pessoais</p>
                    """,
    }
    try:
        await asyncio.to_thread(send_email, email_data, user_data.email)

    except Exception as e:
        raise Exception(f"Error occurred while sending email: {e}")

def decoded_token(token: str) -> dict:
    sp = timezone('America/Sao_Paulo')  # Define o fuso horário de São Paulo
    try:
        decoded_token = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        return decoded_token
    except JWTError as e:
        raise Exception(f"Token inválido ou expirado: {str(e)}")