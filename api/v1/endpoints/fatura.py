from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import extract
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from core.utils import handle_db_exceptions
from models.divide_model import DivideModel
from models.fatura_model import FaturaModel
from models.parente_model import ParenteModel
from models.usuario_model import UsuarioModel
from models.cartao_credito_model import CartaoCreditoModel
from models.movimentacao_model import MovimentacaoModel
from models.conta_model import ContaModel
from schemas.fatura_schema import FaturaSchema, FaturaSchemaUpdate, FaturaSchemaId
from core.deps import get_session, get_current_user
from sqlalchemy.future import select
from typing import List, Optional
from sqlalchemy.orm import joinedload


router = APIRouter()

from datetime import timedelta


async def verificar_fatura_existente(db: AsyncSession, id_cartao_credito: int, mes: int, ano: int) -> Optional[FaturaModel]:
    # Verificar se já existe uma fatura para o mesmo mês e ano

    result = await db.execute(
        select(FaturaModel).where(
            FaturaModel.id_cartao_credito == id_cartao_credito,
            extract('month', FaturaModel.data_vencimento) == mes,
            extract('year', FaturaModel.data_vencimento) == ano,
            extract('month', FaturaModel.data_fechamento) == mes,
            extract('year', FaturaModel.data_fechamento) == ano
        )
    )
    return result.scalars().first()
    
    
async def create_fatura_ano(
    db: AsyncSession,
    usuario_logado: UsuarioModel,
    id_cartao_credito: int,
    ano: int,
    dia_vencimento_usuario: Optional[int],
    dia_fechamento_usuario: Optional[int]
):
    # Consulta para verificar se o cartão de crédito pertence ao usuário
    query_cartao_credito = select(CartaoCreditoModel).where(
        CartaoCreditoModel.id_cartao_credito == id_cartao_credito,
        CartaoCreditoModel.id_usuario == usuario_logado.id_usuario
    )
    result_cartao_credito = await db.execute(query_cartao_credito)
    cartao_credito = result_cartao_credito.scalars().one_or_none()

    if not cartao_credito:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Você não tem permissão para criar essa fatura"
        )
    
    if dia_vencimento_usuario is None or dia_fechamento_usuario is None:
        # Buscar a última fatura do cartão de crédito
        fatura_anterior = await db.execute(
            select(FaturaModel)
            .where(FaturaModel.id_cartao_credito == id_cartao_credito)
            .order_by(FaturaModel.data_vencimento.desc())  
        )
        fatura_anterior = fatura_anterior.scalars().first()  
        
        if fatura_anterior:
            dia_vencimento = fatura_anterior.data_vencimento.day
            dia_fechamento = fatura_anterior.data_fechamento.day

            for mes in range(1, 13):  
                try:
                    data_vencimento = date(ano, mes, dia_vencimento)
                    data_fechamento = date(ano, mes, dia_fechamento)
                except ValueError:
                    data_vencimento = adjust_to_valid_date(ano, mes, dia_vencimento)
                    data_fechamento = adjust_to_valid_date(ano, mes, dia_fechamento)

                existing_fatura = await verificar_fatura_existente(
                    db, id_cartao_credito, mes, ano
                )

                if not existing_fatura:  # Se não houver fatura para esse mês e ano
                    nova_fatura = FaturaModel(
                        data_vencimento=data_vencimento,
                        data_fechamento=data_fechamento,
                        id_conta=fatura_anterior.id_conta,
                        id_cartao_credito=id_cartao_credito,
                        fatura_gastos=0
                    )
                    db.add(nova_fatura)

    else:
        dia_fechamento = dia_fechamento_usuario
        dia_vencimento = dia_vencimento_usuario

        mes_atual = date.today().month

        for mes in range(mes_atual, 13):  
            try:
                data_vencimento = date(ano, mes, dia_vencimento)
                data_fechamento = date(ano, mes, dia_fechamento)
            except ValueError:
                data_vencimento = adjust_to_valid_date(ano, mes, dia_vencimento)
                data_fechamento = adjust_to_valid_date(ano, mes, dia_fechamento)

            existing_fatura = await verificar_fatura_existente(
                db, id_cartao_credito, mes, ano
            )

            if not existing_fatura:  # Se não houver fatura para esse mês e ano
                nova_fatura = FaturaModel(
                    data_vencimento=data_vencimento,
                    data_fechamento=data_fechamento,
                    id_conta=None,
                    id_cartao_credito=id_cartao_credito,
                    fatura_gastos=0
                )
                db.add(nova_fatura)

    try:
        await db.commit()
        return cartao_credito
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail='Erro ao criar as faturas. Verifique os dados fornecidos.')


import calendar

def adjust_to_valid_date(ano: int, mes: int, dia: int) -> date:
    """
    Ajusta para o próximo dia válido no mês, caso o dia especificado não exista.
    Se o dia estiver fora do limite para o mês, ajusta para o último dia do mês.
    """
    ultimo_dia_mes = calendar.monthrange(ano, mes)[1]
    
    if dia > ultimo_dia_mes:
        dia = ultimo_dia_mes

    return date(ano, mes, dia)

@router.post("/fechar")
async def fechar_fatura(
    faturas: FaturaSchemaId,
    usuario_logado: UsuarioModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    
    async with db as session:
        try:
            query = (
                select(FaturaModel)
                .options(joinedload(FaturaModel.cartao_credito))
                .where(
                    FaturaModel.id_fatura == faturas.id_fatura,
                    FaturaModel.cartao_credito.has(id_usuario=usuario_logado.id_usuario)
                )
            )
            result = await session.execute(query)
            fatura: FaturaModel = result.scalar_one_or_none()
            
            if not fatura:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Fatura não encontrada"
                )

            data_hoje = date.today()
            fatura.data_pagamento = data_hoje
            fatura.id_conta = faturas.id_conta

            movimentacoes = await session.execute(
                select(MovimentacaoModel).where(
                    MovimentacaoModel.id_fatura == faturas.id_fatura,
                    MovimentacaoModel.participa_limite_fatura_gastos == True
                )
            )
            movimentacoes = movimentacoes.scalars().all()
            
            if not movimentacoes:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Nenhuma movimentação confirmada para esta fatura"
                )

            for movimentacao in movimentacoes:
                movimentacao.consolidado = True

            conta = await session.execute(
                select(ContaModel).where(
                    ContaModel.id_conta == faturas.id_conta,
                    ContaModel.id_usuario == usuario_logado.id_usuario  
                )
            )
            conta = conta.scalar_one_or_none()
            
            if not conta:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conta associada à fatura não encontrada"
                )

            mes_ano_fatura = data_hoje.strftime("%m/%Y")

            descricao = f"Pagamento de fatura - Referente a {mes_ano_fatura}"

            nova_movimentacao = MovimentacaoModel(
                valor=Decimal(fatura.fatura_gastos),  
                descricao="Pagamento de fatura ",
                id_categoria=None,
                id_conta=fatura.id_conta,
                condicao_pagamento="À vista",
                datatime=datetime.now(),
                data_pagamento=data_hoje,
                consolidado=True,
                forma_pagamento="Débito",
                id_usuario = usuario_logado.id_usuario,
                tipoMovimentacao="Fatura",
            )

            parente_query = (
                select(ParenteModel)
                .where(ParenteModel.nome == usuario_logado.nome_completo,
                       ParenteModel.id_usuario == usuario_logado.id_usuario,
                       )
            )
            parente_result = await session.execute(parente_query)
            parente = parente_result.scalar_one_or_none()

            if parente:
                novo_divide_parente = DivideModel(
                    id_parente=parente.id_parente,
                    valor=nova_movimentacao.valor
                )
                nova_movimentacao.divisoes.append(novo_divide_parente)

            session.add(nova_movimentacao)

            conta.saldo -= fatura.fatura_gastos  
            cartao = fatura.cartao_credito
            cartao.limite_disponivel += fatura.fatura_gastos
            fatura.fatura_gastos = 0

            await session.commit()

            return {"message": "Fatura fechada com sucesso"}

        except Exception as e:
            await handle_db_exceptions(session, e)
        
        finally:
            await session.close()

@router.put('/editar/{id_fatura}', response_model=FaturaSchemaId,status_code=status.HTTP_200_OK)
async def put_fatura(
    id_fatura: int,
    fatura_update: FaturaSchemaUpdate,
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db as session:
        query = select(FaturaModel).where(FaturaModel.id_fatura == id_fatura)
        result = await session.execute(query)
        fatura: FaturaModel = result.scalars().unique().one_or_none()

        if not fatura:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura não encontrada")

        query_cartao_credito = select(CartaoCreditoModel).where(
            CartaoCreditoModel.id_cartao_credito == fatura.id_cartao_credito,
            CartaoCreditoModel.id_usuario == usuario_logado.id_usuario
        )
        result_cartao_credito = await session.execute(query_cartao_credito)
        cartao_credito = result_cartao_credito.scalars().one_or_none()

        if not cartao_credito:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Você não tem permissão para editar essa fatura"
            )

        if fatura_update.data_vencimento:
            fatura.data_vencimento = fatura_update.data_vencimento
        if fatura_update.data_fechamento:
            fatura.data_fechamento = fatura_update.data_fechamento
        if fatura_update.data_pagamento:
            fatura.data_pagamento = fatura_update.data_pagamento
        if fatura_update.id_conta:
            fatura.id_conta = fatura_update.id_conta
        if fatura_update.id_cartao_credito:
            fatura.id_cartao_credito = fatura_update.id_cartao_credito

        try:
            await session.commit()
            return fatura
        except IntegrityError:
            await session.rollback()  # Garantir rollback em caso de erro
            raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail='Erro ao atualizar a fatura. Verifique os dados fornecidos.')

    
@router.delete('/deletar/{id_fatura}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_fatura(id_fatura: int, db: AsyncSession = Depends(get_session), usuario_logado: UsuarioModel = Depends(get_current_user)):
    async with db as session:
        query = select(FaturaModel).join(CartaoCreditoModel).where(
            FaturaModel.id_fatura == id_fatura,
            CartaoCreditoModel.id_usuario == usuario_logado.id_usuario
        )
        result = await session.execute(query)
        fatura = result.scalars().unique().one_or_none()

        if not fatura:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="fatura não encontrada ou não pertence ao usuário logado")
        
        await session.delete(fatura)
        await session.commit()

        return Response(status_code=status.HTTP_204_NO_CONTENT)
