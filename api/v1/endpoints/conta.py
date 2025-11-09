from typing import List
from fastapi import APIRouter, status, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from core.deps import get_current_user, get_session
from models.conta_model import ContaModel
from models.movimentacao_model import MovimentacaoModel
from models.usuario_model import UsuarioModel
from schemas.conta_schema import ContaSchema, ContaSchemaId, ContaSchemaUpdate

from sqlalchemy.future import select

router = APIRouter()

@router.post('/cadastro', status_code=status.HTTP_201_CREATED)
async def post_conta(
    conta: ContaSchema, 
    db: AsyncSession = Depends(get_session),  
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    nova_conta: ContaModel = ContaModel(
        descricao=conta.descricao,
        tipo_conta=str (conta.tipo_conta.value),
        id_usuario = usuario_logado.id_usuario,
        nome=conta.nome,
        nome_icone=conta.nome_icone,
        ativo=conta.ativo if conta.ativo is not None else True,  # Garantindo o valor padrão
        saldo=0
    )
    
    async with db as session:
        try:
            session.add(nova_conta)
            await session.commit()
            return nova_conta
        except IntegrityError:
            await session.rollback()  # Garantir rollback em caso de erro
            raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail='Já existe uma conta com este nome')
        
@router.put('/editar/{conta_id}', response_model=ContaSchemaId, status_code=status.HTTP_202_ACCEPTED)
async def put_conta (conta_id: int, 
                     conta: ContaSchemaUpdate, 
                     db: AsyncSession = Depends(get_session), 
                     usuario_logado: UsuarioModel = Depends(get_current_user)):
    async with db as session:

       
        query = select(ContaModel).filter(ContaModel.id_conta == conta_id)
        result = await session.execute(query)
        conta_up: ContaModel = result.scalars().unique().one_or_none()
        
        
        if conta_up.nome == 'Carteira':
            raise HTTPException(
                detail='Não é possível atualizar a conta Carteira.',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if conta_up:
            
            if conta_up.id_usuario != usuario_logado.id_usuario:
                raise HTTPException(
                    detail="Você não tem permissão para editar esta conta.",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            if conta.descricao:
                conta_up.descricao = conta.descricao
            if conta.tipo_conta:
                conta_up.tipo_conta = conta.tipo_conta.value
            if conta.nome:
                conta_up.nome = conta.nome
            if conta.nome_icone:
                conta_up.nome_icone = conta.nome_icone
            if conta.ativo is not None:
                conta_up.ativo = bool(conta.ativo)
            
            try:
                await session.commit()
                return conta_up
            except IntegrityError:
                await session.rollback()  # Garantir rollback em caso de erro
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail='Já existe uma conta com este nome')
        else:
            raise HTTPException (detail= 'Conta não encontrada.', status_code=status.HTTP_404_NOT_FOUND)


@router.get('/listar/{somente_ativo}', response_model=List[ContaSchemaId])
async def get_contas (somente_ativo: bool, db: AsyncSession = Depends(get_session),
                      usuario_logado: UsuarioModel = Depends(get_current_user)):
    async with db as session:
        query = select(ContaModel).where(
            ContaModel.id_usuario == usuario_logado.id_usuario,
            ContaModel.ativo if somente_ativo else True

        ).order_by(ContaModel.nome)

        result = await session.execute(query)
        contas: List[ContaSchemaId] = result.scalars().unique().all()
      
        return contas
    

    
@router.get('/visualizar/{conta_id}', response_model=ContaSchemaId, status_code= status.HTTP_200_OK)
async def get_conta (conta_id: int,  db: AsyncSession = Depends(get_session),
                       usuario_logado: UsuarioModel = Depends(get_current_user)):
    async with db as session:
        query = select(ContaModel).where(ContaModel.id_conta == conta_id, ContaModel.id_usuario == usuario_logado.id_usuario)
        result = await session.execute(query)
        conta: ContaSchemaId = result.scalars().unique().one_or_none()
        
        
        if conta:
            return conta
        else:
            raise HTTPException (detail= 'Conta não encontrado.', status_code=status.HTTP_404_NOT_FOUND)
        
@router.delete('/deletar/{conta_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_conta (
    conta_id: int, 
    db: AsyncSession = Depends(get_session), 
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db as session:
        query = select(ContaModel).where(
            ContaModel.id_conta == conta_id, 
                        ContaModel.id_usuario == usuario_logado.id_usuario)
        result = await session.execute(query)
        conta_del: ContaModel = result.scalars().unique().one_or_none()
        
     
        if not conta_del:
            raise HTTPException(detail='Conta não encontrada.', status_code=status.HTTP_404_NOT_FOUND)
        
        if conta_del.nome == 'Carteira':
            raise HTTPException(detail='Não é possível deletar a conta ""Carteira""', status_code=status.HTTP_406_NOT_ACCEPTABLE)
        
        
        # Verificar se existem movimentações associadas à conta
        movimentacao_query = select(MovimentacaoModel).where(
            MovimentacaoModel.id_conta == conta_id
        )
        movimentacao_result = await session.execute(movimentacao_query)
        movimentacoes = movimentacao_result.scalars().unique().all()
        
        
        if movimentacoes:
            raise HTTPException(detail='Não é possível excluir a conta. Existem movimentações associadas.', status_code=status.HTTP_400_BAD_REQUEST)
        
        
           
        await session.delete(conta_del)
        
        await session.commit()
            
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
        

#GET / all Teste pra todas as contas de todos os usuários
@router.get('/teste/', response_model=List[ContaSchemaId])
async def get_contas_teste ( db: AsyncSession = Depends(get_session),
                      usuario_logado: UsuarioModel = Depends(get_current_user)):
    async with db as session:
        query = select(ContaModel)
        result = await session.execute(query)
        contas: List[ContaSchemaId] = result.scalars().unique().all()
      
        return contas
