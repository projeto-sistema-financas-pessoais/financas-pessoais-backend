from fastapi import APIRouter, Request, status, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from core.security import generate_hash
from core.deps import get_session, get_current_user
from core.utils import handle_db_exceptions
from models.usuario_model import UsuarioModel
from models.categoria_model import CategoriaModel
from models.conta_model import ContaModel
from models.parente_model import ParenteModel
from schemas.usuario_schema import UsuarioSchema, UpdateUsuarioSchema
from schemas.resetPasswordRequest import ResetPasswordRequest
from schemas.recoverPasswordRequest import RecoverPasswordRequest
from fastapi.security import OAuth2PasswordRequestForm
from core.auth import auth, generate_token_access, decoded_token, send_email_to_reset_password
import jwt
from sqlalchemy.future import select
from fastapi import BackgroundTasks 
from sqlalchemy import text  

router = APIRouter()

@router.post('/cadastro', status_code=status.HTTP_201_CREATED)
async def post_usuario(usuario: UsuarioSchema, db: AsyncSession = Depends(get_session)):
    novo_usuario: UsuarioModel = UsuarioModel(
        nome_completo=usuario.nome_completo,
        data_nascimento=usuario.data_nascimento,
        email=usuario.email,
        senha=generate_hash(usuario.senha)
    )

    async with db as session:
        try:
            session.add(novo_usuario)
            await session.commit()
            await session.refresh(novo_usuario)

            # Criação das categorias pré-definidas
            categorias = [
                CategoriaModel(
                    nome="Saúde",
                    tipo_categoria="Fixa",
                    modelo_categoria="Despesa",
                    id_usuario=novo_usuario.id_usuario,
                    valor_categoria=None,
                    nome_icone="health2.svg",
                    ativo=True
                ),
                CategoriaModel(
                    nome="Alimentação",
                    tipo_categoria="Fixa",
                    modelo_categoria="Despesa",
                    id_usuario=novo_usuario.id_usuario,
                    valor_categoria=None,
                    nome_icone="food.svg",
                    ativo=True
                ),
                CategoriaModel(
                    nome="Transporte",
                    tipo_categoria="Fixa",
                    modelo_categoria="Despesa",
                    id_usuario=novo_usuario.id_usuario,
                    valor_categoria=None,
                    nome_icone="transport.svg",
                    ativo=True
                ),
                CategoriaModel(
                    nome="Educação",
                    tipo_categoria="Fixa",
                    modelo_categoria="Despesa",
                    id_usuario=novo_usuario.id_usuario,
                    valor_categoria=None,
                    nome_icone="schooll.svg",
                    ativo=True
                ),
                CategoriaModel(
                    nome="Lazer",
                    tipo_categoria="Variável",
                    modelo_categoria="Despesa",
                    id_usuario=novo_usuario.id_usuario,
                    valor_categoria=None,
                    nome_icone="happy.svg",
                    ativo=True
                ),
                CategoriaModel(
                    nome="Salário",
                    tipo_categoria="Fixa",
                    modelo_categoria="Receita",
                    id_usuario=novo_usuario.id_usuario,
                    valor_categoria=None,
                    nome_icone="salary.svg",
                    ativo=True
                ),
                CategoriaModel(
                    nome="Extra",
                    tipo_categoria="Extra",
                    modelo_categoria="Receita",
                    id_usuario=novo_usuario.id_usuario,
                    valor_categoria=None,
                    nome_icone="extra.svg",
                    ativo=True
                )
            ]
            session.add_all(categorias)

            # Criação da conta "Carteira"
            conta_carteira = ContaModel(
                descricao="Conta padrão para despesas em dinheiro físico",
                nome="Carteira",
                nome_icone="6_carteira.svg",
                tipo_conta="Carteira",
                id_usuario=novo_usuario.id_usuario,
                ativo=True,
                saldo=0
            )
            session.add(conta_carteira)

            parente_usuario = ParenteModel(
                nome=novo_usuario.nome_completo,
                email=novo_usuario.email,
                grau_parentesco= "Eu",
                ativo=True,
                id_usuario=novo_usuario.id_usuario
            )
            session.add(parente_usuario)

            await session.commit()
            return novo_usuario
        except Exception as e:
            await handle_db_exceptions(session, e)
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE, 
                detail='Já existe um usuário com este email cadastrado'
            )
        



@router.post('/login')
async def login(login_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_session)):
    usuario = await auth(email=login_data.username, senha=login_data.password, db=db)
    
    if not usuario:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Dados de acesso incorretos')
    
    return JSONResponse(
        content={
            "access_token": generate_token_access(sub=usuario.id_usuario),
            "token_type": "bearer",
            "name": usuario.nome_completo,
        },
        status_code=status.HTTP_200_OK
    )


@router.post('/reset-password/{token}')
async def reset_password(token: str, 
                         schema: ResetPasswordRequest, 
                         db: AsyncSession = Depends(get_session)):

    try:
        decoded_data = decoded_token(token)
    except jwt.ExpiredSignatureError:
        print("Erro: Token expirado")
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={'message': "Expired Token!"})
    except jwt.InvalidTokenError:
        print("Erro: Token inválido")
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={'message': 'Invalid token'})

    async with db as session:
        try:
            user_id = int(decoded_data['sub']) 

            result = await session.execute(select(UsuarioModel).where(UsuarioModel.id_usuario == user_id))
            user_data = result.scalars().first()
        except Exception as e:
            print(f"Erro ao consultar o banco de dados: {e}")
            raise HTTPException(status_code=500, detail="Database query failed")

        if user_data:
            user_data.senha = generate_hash(schema.password)
            await session.commit()
            return JSONResponse(status_code=status.HTTP_200_OK, content={"message": f"Password for user ID {user_data.id_usuario} updated successfully"})
        else:
            print("Erro: Usuário não encontrado.")
    
    return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={'message': 'Error while validating token'})

@router.post("/recover-password", status_code=status.HTTP_202_ACCEPTED)
async def recover_password(schema: RecoverPasswordRequest, 
                           request: Request, 
                           background_tasks: BackgroundTasks,
                           db: AsyncSession = Depends(get_session), 
):
    
    async with db as session:
        try:
            query = await session.execute(select(UsuarioModel).filter(UsuarioModel.email == schema.email))
            user_data = query.scalars().first()

            if user_data:
                token = generate_token_access(user_data.id_usuario)
                background_tasks.add_task(send_email_to_reset_password, request, user_data, token)           
            else:
                return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={'message': 'e-mail not found in database'})

        except Exception as e:
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={'message': 'erro ao enviar'})

@router.put('/editar', status_code=status.HTTP_200_OK)
async def update_usuario(
    usuario_update: UpdateUsuarioSchema, 
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):

    async with db as session:
        usuario = await session.get(UsuarioModel, usuario_logado.id_usuario)
        
        if not usuario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
        
        usuario.nome_completo = usuario_update.nome_completo
        usuario.data_nascimento = usuario_update.data_nascimento
        
        query = await session.execute(select(ParenteModel).filter(
            ParenteModel.id_usuario == usuario_logado.id_usuario,
            ParenteModel.nome == usuario_logado.nome_completo
        ))
        parente = query.scalars().one_or_none()
        
        if parente:
            parente.nome = usuario_update.nome_completo
        
        try:
            await session.commit()
            return usuario
        except IntegrityError:
            raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail='Erro ao atualizar os dados do usuário')

@router.delete('/deletar', status_code=status.HTTP_204_NO_CONTENT)
async def delete_usuario(
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):

    async with db as session:

        try:
            await session.delete(usuario_logado)
            await session.commit()
            return {"message": "Deletando usuário com sucesso com sucesso."}
        
        
        except Exception as e:
            await handle_db_exceptions(session, e)

        finally:
            await session.close()
        

@router.get('/listar_usuario', status_code=status.HTTP_200_OK)
async def get_usuario(
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db as session:
        usuario = {
            "nome_completo": usuario_logado.nome_completo,
            "data_nascimento": usuario_logado.data_nascimento
        }
        return usuario


