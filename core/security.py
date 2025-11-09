from passlib.context import CryptContext

pwd_context = CryptContext(schemes='bcrypt', deprecated='auto')

def check_password(senha: str, hash_senha: str) -> bool:

    return pwd_context.verify(senha, hash_senha)


def generate_hash(senha: str)-> str:
    
    return pwd_context.hash(senha)