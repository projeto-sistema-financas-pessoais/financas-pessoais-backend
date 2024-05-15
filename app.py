from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2 import sql, errors
from pydantic import BaseModel, EmailStr
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Conectar ao banco de dados PostgreSQL
conn = psycopg2.connect(
    dbname="SCFP",
    user="postgres",
    password="3003",
    host="localhost"
)
cur = conn.cursor()

app = FastAPI()

# Configuração do middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

class Cliente(BaseModel):
    nome_completo: str
    data_nascimento: datetime
    email: EmailStr
    senha: str

@app.post("/clientes/")
async def cadastrar_cliente(cliente: Cliente):
    try:
        cur.execute(
            sql.SQL("INSERT INTO cliente (nome_completo, data_nascimento, email, senha) VALUES (%s, %s, %s, %s)"),
            (cliente.nome_completo, cliente.data_nascimento, cliente.email, cliente.senha)
        )
        conn.commit()
        return {"mensagem": "Cliente cadastrado com sucesso"}
    except psycopg2.IntegrityError as e:
        conn.rollback()
        logging.error(f"IntegrityError: {str(e)}")
        raise HTTPException(status_code=409, detail="Email already exists")
    except Exception as e:
        conn.rollback()
        logging.error(f"Exception: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@app.get("/scfp/{nome_completo}")
async def obter_cliente(nome_completo: str):
    try:
        cur.execute(
            sql.SQL("SELECT * FROM cliente WHERE nome_completo = %s"),
            (nome_completo,)
        )
        cliente = cur.fetchone()
        if cliente:
            return {
                "nome_completo": cliente[0],
                "data_nascimento": cliente[1],
                "email": cliente[2],
                "senha": cliente[3]
            }
        else:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
    except Exception as e:
        logging.error(f"Exception: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro interno do servidor: {str(e)}")
