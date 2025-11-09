from fastapi import APIRouter, status, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from typing import List
from core.deps import get_current_user, get_session
from models.categoria_model import CategoriaModel
from models.usuario_model import UsuarioModel
from models.movimentacao_model import MovimentacaoModel
from schemas.categoria_schema import CategoriaSchema, CategoriaSchemaUpdate, CategoriaSchemaId
from sqlalchemy.future import select
from models.enums import TipoMovimentacao


router = APIRouter()

@router.post('/cadastro', status_code=status.HTTP_201_CREATED)
async def post_categoria(
    categoria: CategoriaSchema, 
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    nova_categoria: CategoriaModel = CategoriaModel(
        nome=categoria.nome,
        tipo_categoria=categoria.tipo_categoria,
        modelo_categoria=categoria.modelo_categoria,
        id_usuario=usuario_logado.id_usuario,
        valor_categoria=categoria.valor_categoria,
        nome_icone=categoria.nome_icone,
        ativo=categoria.ativo
    )
    
    async with db as session:
        try:
            session.add(nova_categoria)
            await session.commit()
            return nova_categoria
        except IntegrityError:
            raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Categoria já cadastrada para este usuário")

@router.put('/editar/{categoria_id}', response_model=CategoriaSchemaId, status_code=status.HTTP_202_ACCEPTED)
async def put_categoria(
    categoria_id: int, 
    categoria: CategoriaSchemaUpdate, 
    db: AsyncSession = Depends(get_session), 
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db as session:
        query = select(CategoriaModel).filter(CategoriaModel.id_categoria == categoria_id)
        result = await session.execute(query)
        categoria_up: CategoriaModel = result.scalars().unique().one_or_none()

        if not categoria_up:
            raise HTTPException(
                detail="Categoria não encontrada.",
                status_code=status.HTTP_404_NOT_FOUND
            )

        if categoria_up.id_usuario != usuario_logado.id_usuario:
            raise HTTPException(
                detail="Você não tem permissão para editar esta categoria.",
                status_code=status.HTTP_403_FORBIDDEN
            )


        categoria_up.valor_categoria = categoria.valor_categoria

        if categoria.nome:
            categoria_up.nome = categoria.nome
        if categoria.tipo_categoria:
            categoria_up.tipo_categoria = categoria.tipo_categoria
        if categoria.modelo_categoria:
            categoria_up.modelo_categoria = categoria.modelo_categoria
        if categoria.nome_icone:
            categoria_up.nome_icone = categoria.nome_icone
        if categoria.ativo is not None:
                categoria_up.ativo = bool(categoria.ativo)

        try:
            await session.commit()
            return categoria_up
        except IntegrityError:
            await session.rollback()  
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE, 
                detail='Já existe uma categoria com este nome para o usuário.'
            )

@router.get('/listar/{somente_ativo}', response_model=List[CategoriaSchemaId])
async def get_categorias ( somente_ativo: bool, db: AsyncSession = Depends(get_session),
                      usuario_logado: UsuarioModel = Depends(get_current_user)):
    async with db as session:
        query = select(CategoriaModel).where(
            CategoriaModel.id_usuario == usuario_logado.id_usuario,
            CategoriaModel.ativo if somente_ativo else True
        )
        result = await session.execute(query)
        categorias: List[CategoriaSchemaId] = result.scalars().unique().all()
      
        return categorias

@router.get('/listar/receita/{somente_ativo}', response_model=List[CategoriaSchemaId], status_code=status.HTTP_200_OK)
async def get_categorias_receita(somente_ativo: bool,db: AsyncSession = Depends(get_session), 
                                 usuario_logado: UsuarioModel = Depends(get_current_user)):
    async with db as session:
        query = select(CategoriaModel).where(
            CategoriaModel.id_usuario == usuario_logado.id_usuario,
            CategoriaModel.modelo_categoria == TipoMovimentacao.RECEITA,
                        CategoriaModel.ativo if somente_ativo else True

        ).order_by(CategoriaModel.nome)
        result = await session.execute(query)
        categorias_receita: List[CategoriaSchemaId] = result.scalars().unique().all()

        return categorias_receita

# Listar categorias onde modelo_categoria é igual a Despesa
@router.get('/listar/despesa/{somente_ativo}', response_model=List[CategoriaSchemaId], status_code=status.HTTP_200_OK)
async def get_categorias_despesa(somente_ativo: bool,db: AsyncSession = Depends(get_session), 
                                 usuario_logado: UsuarioModel = Depends(get_current_user)):
    async with db as session:
        query = select(CategoriaModel).where(
            CategoriaModel.id_usuario == usuario_logado.id_usuario,
            CategoriaModel.modelo_categoria == TipoMovimentacao.DESPESA,
            CategoriaModel.ativo if somente_ativo else True

        ).order_by(CategoriaModel.nome)
        result = await session.execute(query)
        categorias_despesa: List[CategoriaSchemaId] = result.scalars().unique().all()

        return categorias_despesa


@router.get('/visualizar/{id_categoria}', response_model=CategoriaSchema, status_code=status.HTTP_200_OK)
async def get_categoria(
    id_categoria: int, 
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)):
    async with db as session:
        query = select(CategoriaModel).where(CategoriaModel.id_categoria == id_categoria, CategoriaModel.id_usuario == usuario_logado.id_usuario)
        result = await session.execute(query)
        categoria : CategoriaSchemaId = result.scalars().unique().one_or_none()
        if categoria:
            return categoria
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")

@router.delete('/deletar/{id_categoria}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_categoria (
    id_categoria: int, 
    db: AsyncSession = Depends(get_session), 
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db as session:
        query = select(CategoriaModel).where(
            CategoriaModel.id_categoria == id_categoria, 
                        CategoriaModel.id_usuario == usuario_logado.id_usuario)
        result = await session.execute(query)
        categoria_del: CategoriaModel = result.scalars().unique().one_or_none()
        
     
        if not categoria_del:
            raise HTTPException(detail='Categoria não encontrada.', status_code=status.HTTP_404_NOT_FOUND)
        
              
        # Verificar se existem movimentações associadas à categoria
        movimentacao_query = select(MovimentacaoModel).where(
            MovimentacaoModel.id_categoria == id_categoria
        )
        movimentacao_result = await session.execute(movimentacao_query)
        movimentacoes = movimentacao_result.scalars().unique().all()
        
        
        if movimentacoes:
            raise HTTPException(detail='Não é possível excluir a categoria; Existem movimentações associadas.', status_code=status.HTTP_400_BAD_REQUEST)
        
        
           
        await session.delete(categoria_del)
        
        await session.commit()
            
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
        