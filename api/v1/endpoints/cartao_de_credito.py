import calendar
import core.utils
from sqlalchemy import extract
import api.v1.endpoints
import datetime
import api.v1.endpoints.fatura
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from typing import List
from core.deps import get_session, get_current_user
from models.cartao_credito_model import CartaoCreditoModel
from models.movimentacao_model import MovimentacaoModel
from schemas.cartao_de_credito_schema import CartaoCreditoSchema, CartaoCreditoSchemaId, CartaoCreditoSchemaUpdate, CartaoCreditoSchemaFatura
from models.usuario_model import UsuarioModel
from models.fatura_model import FaturaModel
from api.v1.endpoints.fatura import create_fatura_ano
from datetime import date, datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

router = APIRouter()

@router.post('/cadastro', status_code=status.HTTP_201_CREATED)
async def post_cartao_credito(
    cartao_credito: CartaoCreditoSchemaFatura, 
    db: AsyncSession = Depends(get_session), 
    usuario_logado: UsuarioModel = Depends(get_current_user)
):

    if cartao_credito.dia_fechamento == cartao_credito.dia_vencimento:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A data de venciomento deve ser diferente da data de fechamento")
            
    novo_cartao: CartaoCreditoModel = CartaoCreditoModel(
        nome=cartao_credito.nome,
        limite=cartao_credito.limite,
        id_usuario=usuario_logado.id_usuario,
        nome_icone=cartao_credito.nome_icone,
        ativo=cartao_credito.ativo if cartao_credito.ativo is not None else True,
        limite_disponivel=cartao_credito.limite
    )

    async with db as session:
        try:
            session.add(novo_cartao)
            await session.commit()
            await session.refresh(novo_cartao)

           
            await create_fatura_ano(
                db, 
                usuario_logado, 
                novo_cartao.id_cartao_credito, 
                date.today().year, 
                cartao_credito.dia_vencimento, 
                cartao_credito.dia_fechamento
            )
            
            if date.today().month == 12:
                await create_fatura_ano(
                    db, 
                    usuario_logado, 
                    novo_cartao.id_cartao_credito, 
                    date.today().year +1, 
                    cartao_credito.dia_vencimento, 
                    cartao_credito.dia_fechamento
                )

            return novo_cartao
        except IntegrityError:
            await session.rollback()  
            raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, 
                                detail="Já existe um cartão de crédito com este nome para este usuário")
        


@router.put('/editar/{id_cartao_credito}', response_model=CartaoCreditoSchemaId, status_code=status.HTTP_202_ACCEPTED)
async def update_cartao_credito(
    id_cartao_credito: int, 
    cartao_credito_update: CartaoCreditoSchemaUpdate, 
    db: AsyncSession = Depends(get_session), 
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db as session:
        query = select(CartaoCreditoModel).where(
            CartaoCreditoModel.id_cartao_credito == id_cartao_credito,
            CartaoCreditoModel.id_usuario == usuario_logado.id_usuario
        )
        result = await session.execute(query)
        cartao_credito = result.scalars().unique().one_or_none()

        if not cartao_credito:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cartão de crédito não encontrado ou você não tem permissão para editá-lo")

        if cartao_credito_update.nome:
            cartao_credito.nome = cartao_credito_update.nome
        if cartao_credito_update.limite:
            aux = cartao_credito.limite - cartao_credito.limite_disponivel
            cartao_credito.limite = cartao_credito_update.limite
            cartao_credito.limite_disponivel = cartao_credito.limite - aux
        if cartao_credito_update.nome_icone:
            cartao_credito.nome_icone = cartao_credito_update.nome_icone
        if cartao_credito_update.ativo is not None:
            cartao_credito.ativo = cartao_credito_update.ativo

        if cartao_credito_update.dia_fechamento or cartao_credito_update.dia_vencimento:
            hoje = datetime.now()
            dia_fechamento = cartao_credito_update.dia_fechamento 
            dia_vencimento = cartao_credito_update.dia_vencimento 


            fatura_query = select(FaturaModel).where(
                FaturaModel.id_cartao_credito == id_cartao_credito,
                FaturaModel.data_fechamento >= hoje
            ).order_by(FaturaModel.data_fechamento)
            fatura_result = await session.execute(fatura_query)
            faturas = fatura_result.scalars().all()

            for fatura in faturas:
                print("faturas print", fatura.id_fatura, fatura.data_fechamento, fatura.data_vencimento)
                novo_mes_fechamento = fatura.data_fechamento.month
                novo_ano_fechamento = fatura.data_fechamento.year
                
                ultimo_dia_mes_fechamento = calendar.monthrange(novo_ano_fechamento, novo_mes_fechamento)[1]

                print("novo mes ano fechamento", novo_mes_fechamento, novo_ano_fechamento,  "dia  ", dia_fechamento, "", fatura.data_fechamento.day)
                
                dia_fechamento_ajustado = min(dia_fechamento, ultimo_dia_mes_fechamento)            


                fatura.data_fechamento = date(
                    novo_ano_fechamento, novo_mes_fechamento, dia_fechamento_ajustado
                )

                novo_mes_vencimento = novo_mes_fechamento
                novo_ano_vencimento = novo_ano_fechamento

                if dia_vencimento < dia_fechamento:
                    novo_mes_vencimento += 1
                    if novo_mes_vencimento > 12:
                        novo_mes_vencimento = 1
                        novo_ano_vencimento += 1
                        
    
                ultimo_dia_mes_vencimento = calendar.monthrange(novo_ano_vencimento, novo_mes_vencimento)[1]

                dia_vencimento_ajustado = min(dia_vencimento, ultimo_dia_mes_vencimento)            

                fatura.data_vencimento = date(
                    novo_ano_vencimento, novo_mes_vencimento, dia_vencimento_ajustado
                )

                movimentacoes_query = select(MovimentacaoModel).where(
                    MovimentacaoModel.id_fatura == fatura.id_fatura
                )
                
                movimentacoes_result = await session.execute(movimentacoes_query)
                movimentacoes = movimentacoes_result.scalars().all()

                for movimentacao in movimentacoes:
                    data_movimentacao = movimentacao.data_pagamento
   
                    nova_fatura = next(
                        (f for f in faturas if f.data_fechamento > data_movimentacao), None
                    )
                    if nova_fatura:
                        fatura.fatura_gastos -= movimentacao.valor
                        nova_fatura.fatura_gastos += movimentacao.valor
                        movimentacao.id_fatura = nova_fatura.id_fatura

        await session.commit()
        await session.refresh(cartao_credito)
        return cartao_credito

@router.get('/listar/{somente_ativo}', response_model=list[CartaoCreditoSchemaId], status_code=status.HTTP_200_OK)
async def listar_cartoes_credito(somente_ativo: bool, db: AsyncSession = Depends(get_session), usuario_logado: UsuarioModel = Depends(get_current_user)):
    try:
        async with db as session:
            query = (
                select(CartaoCreditoModel)
                .options(joinedload(CartaoCreditoModel.faturas))
                .where(CartaoCreditoModel.id_usuario == usuario_logado.id_usuario,
                       CartaoCreditoModel.ativo if somente_ativo else True)
            ).order_by(CartaoCreditoModel.nome)

            result = await session.execute(query)
            cartoes_credito: List[CartaoCreditoModel] = result.scalars().unique().all()

            cartoes_credito_response = []
            for cartao in cartoes_credito:

                proximas_faturas = sorted(
                    [f for f in cartao.faturas if f.data_fechamento >= datetime.now().date()],
                    key=lambda f: f.data_fechamento
                )

                proxima_fatura = proximas_faturas[0] if proximas_faturas else None
                

                cartao_data = {
                    "id_cartao_credito": cartao.id_cartao_credito,
                    "nome": cartao.nome,
                    "limite_disponivel": cartao.limite_disponivel,
                    "data_fechamento": proxima_fatura.data_fechamento if proxima_fatura else None,
                    "dia_fechamento": proxima_fatura.data_fechamento.day if proxima_fatura else None,
                    "dia_vencimento": proxima_fatura.data_vencimento.day if proxima_fatura else None,
                    "nome_icone": cartao.nome_icone,
                    "ativo": cartao.ativo,
                    "id_usuario": cartao.id_usuario,
                    "limite": cartao.limite,
                    "fatura_gastos": proxima_fatura.fatura_gastos if proxima_fatura else None,
                }
                cartoes_credito_response.append(cartao_data)

            return cartoes_credito_response

    except Exception as e:
        await core.utils.handle_db_exceptions(session, e)
        raise HTTPException(status_code=500, detail="Internal server error while fetching credit cards")
    
@router.get('/visualizar/{id_cartao_credito}', response_model=CartaoCreditoSchemaId, status_code=status.HTTP_200_OK)
async def listar_cartao_credito(
    id_cartao_credito: int, 
    db: AsyncSession = Depends(get_session), 
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db as session:
        query = (
            select(CartaoCreditoModel)
            .options(joinedload(CartaoCreditoModel.faturas))  
            .where(
                CartaoCreditoModel.id_cartao_credito == id_cartao_credito,
                CartaoCreditoModel.id_usuario == usuario_logado.id_usuario
            )
        )
        result = (await session.execute(query)).unique()
        cartao_credito = result.scalars().one_or_none()

        if not cartao_credito:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cartão de crédito não encontrado ou você não tem permissão para visualizá-lo")

        proxima_fatura = (
            sorted (
                [f for f in cartao_credito.faturas if f.data_fechamento >= datetime.now().date()], 
                key=lambda f: f.data_fechamento)[0] if cartao_credito.faturas else None
        )

        return {
            "id_cartao_credito": cartao_credito.id_cartao_credito,
            "nome": cartao_credito.nome,
            "limite_disponivel": cartao_credito.limite_disponivel,
            "dia_fechamento": proxima_fatura.data_fechamento.day if proxima_fatura else None,
            "data_fechamento": proxima_fatura.data_fechamento if proxima_fatura else None,
            "dia_vencimento": proxima_fatura.data_vencimento.day if proxima_fatura else None,
            "nome_icone": cartao_credito.nome_icone,
            "ativo": cartao_credito.ativo,
            "id_usuario": cartao_credito.id_usuario,
            "limite": cartao_credito.limite,
            "fatura_gastos": None # não usar pois seria só do mês atual, pegar do listar movimentacao
        }

    
@router.delete('/deletar/{id_cartao_credito}', status_code=status.HTTP_204_NO_CONTENT)
async def deletar_cartao_credito(
    id_cartao_credito: int, 
    db: AsyncSession = Depends(get_session), 
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db as session:
        query = select(CartaoCreditoModel).where(
            CartaoCreditoModel.id_cartao_credito == id_cartao_credito,
            CartaoCreditoModel.id_usuario == usuario_logado.id_usuario
        )
        result = await session.execute(query)
        cartao_credito = result.scalars().unique().one_or_none()

        if not cartao_credito:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cartão de crédito não encontrado ou você não tem permissão para deletá-lo")

    # Verificar se existem faturas associadas ao cartão de crédito
        fatura_query = select(FaturaModel).where(
            FaturaModel.id_cartao_credito == id_cartao_credito,
            FaturaModel.fatura_gastos > 0
        )
        Fatura_result = await session.execute(fatura_query)
        faturas = Fatura_result.scalars().unique().all()
        
        
        if faturas:
            raise HTTPException(detail='Não é possível excluir o cartão de crédito. Existem faturas associadas.', status_code=status.HTTP_400_BAD_REQUEST)
        
        await session.delete(cartao_credito)
        await session.commit()

        return Response(status_code=status.HTTP_204_NO_CONTENT)
