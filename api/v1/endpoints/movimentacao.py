
from decimal import ROUND_HALF_UP, Decimal
from fastapi import APIRouter, Depends , status, HTTPException
from sqlalchemy import and_, extract, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from api.v1.endpoints.fatura import create_fatura_ano
from core.utils import handle_db_exceptions
from models.cartao_credito_model import CartaoCreditoModel
from models.divide_model import DivideModel
from models.movimentacao_model import MovimentacaoModel
from models.parente_model import ParenteModel
from schemas.fatura_schema import FaturaSchemaInfo
from schemas.movimentacao_schema import (MovimentacaoFaturaSchemaList, MovimentacaoRequestFilterSchema,
    MovimentacaoSchemaConsolida, MovimentacaoSchemaId, MovimentacaoSchemaList, MovimentacaoSchemaReceitaDespesa,
    MovimentacaoSchemaTransferencia, MovimentacaoSchemaUpdate, ParenteResponse)
from core.deps import get_session, get_current_user
from models.usuario_model import UsuarioModel
from models.conta_model import ContaModel
from models.categoria_model import CategoriaModel
from models.fatura_model import FaturaModel
from typing import List
from models.repeticao_model import RepeticaoModel
from models.enums import CondicaoPagamento, FormaPagamento, TipoMovimentacao, TipoRecorrencia
from datetime import date, datetime, timedelta
from sqlalchemy.orm import joinedload, selectinload
from calendar import monthrange
from dateutil.relativedelta import relativedelta


router = APIRouter()



async def find_fatura(id_cartao_credito: int, data_pagamento: date, db: AsyncSession):
    

    # Consulta para pegar a fatura no mês atual
    query_mes_atual = select(FaturaModel).filter(
        FaturaModel.id_cartao_credito == id_cartao_credito,
        extract('month', FaturaModel.data_fechamento) == data_pagamento.month,
        extract('year', FaturaModel.data_fechamento) == data_pagamento.year
    )

    # Consulta para pegar a fatura do mês seguinte
    query_mes_seguinte = select(FaturaModel).filter(
        FaturaModel.id_cartao_credito == id_cartao_credito,
        extract('month', FaturaModel.data_fechamento) == (data_pagamento.month % 12) + 1,  # Incrementa o mês
        extract('year', FaturaModel.data_fechamento) == (data_pagamento.year if data_pagamento.month < 12 else data_pagamento.year + 1)  # Ajusta o ano se for Dezembro
    )
    
    # Executa as consultas
    result_mes_atual = await db.execute(query_mes_atual)
    fatura_mes_atual =  result_mes_atual.scalars().first()

    result_mes_seguinte = await db.execute(query_mes_seguinte)
    fatura_mes_seguinte =  result_mes_seguinte.scalars().first()
    

    # Verifica qual fatura escolher
    if fatura_mes_atual:
        # Se tiver uma fatura no mês atual, verifica se ela já é a fatura seguinte
        print("mes atual fatura", fatura_mes_atual.data_fechamento, data_pagamento)
        if fatura_mes_atual.data_fechamento > data_pagamento:
            return fatura_mes_atual
    
    if fatura_mes_seguinte:
        print("mes seguinte fatura", fatura_mes_seguinte.data_fechamento, data_pagamento)

        if fatura_mes_seguinte.data_fechamento > data_pagamento and fatura_mes_atual:
            return fatura_mes_seguinte

    return None


async def get_or_create_fatura(session: AsyncSession, usuario_logado: UsuarioModel, id_financeiro:int, data_pagamento: date):
    fatura = await find_fatura(id_financeiro, data_pagamento, session)
    cartao_credito = None 

    if not fatura:

        if data_pagamento.month == 12:  
            cartao_credito = await create_fatura_ano(session, usuario_logado, id_financeiro, data_pagamento.year +1, None, None)
        else:
            cartao_credito = await create_fatura_ano(session, usuario_logado, id_financeiro, data_pagamento.year, None, None)
        
        fatura = await find_fatura(id_financeiro, data_pagamento, session)
        
        if not fatura:

            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao adicionar fatura")
    else:
        query_cartao_credito = select(CartaoCreditoModel).where(
            CartaoCreditoModel.id_cartao_credito == id_financeiro,
            CartaoCreditoModel.id_usuario == usuario_logado.id_usuario
        )
        result_cartao_credito = await session.execute(query_cartao_credito)
        cartao_credito = result_cartao_credito.scalars().one_or_none()

        if not cartao_credito:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para acessar esse cartão"
            )
    
    return fatura, cartao_credito

async def validar_categoria(session: AsyncSession, usuario_logado: UsuarioModel, id_categoria:int):
    query_categoria = select(CategoriaModel).where(CategoriaModel.id_categoria == id_categoria, CategoriaModel.id_usuario == usuario_logado.id_usuario)
    result_categoria = await session.execute(query_categoria)
    categoria = result_categoria.scalars().first()
    if not categoria:
        print(f"Categoria {id_categoria} não encontrada ou não pertence ao usuário {usuario_logado.id_usuario}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada ou não pertence ao usuário.")
    return categoria

async def validar_conta(session, usuario_logado, id_conta):
    query_conta = select(ContaModel).where(ContaModel.id_conta == id_conta, ContaModel.id_usuario == usuario_logado.id_usuario)
    result_conta = await session.execute(query_conta)
    conta =  result_conta.scalars().first()
    if not conta:
        print(f"Conta {id_conta} não encontrada ou não pertence ao usuário {usuario_logado.id_usuario}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada ou não pertence ao usuário.")
    return conta

async def criar_repeticao(movimentacao: MovimentacaoSchemaReceitaDespesa, usuario_logado: UsuarioModel, db: AsyncSession):
    if movimentacao.condicao_pagamento in [CondicaoPagamento.PARCELADO, CondicaoPagamento.RECORRENTE]:
        if movimentacao.condicao_pagamento == CondicaoPagamento.RECORRENTE: 
            if movimentacao.tipo_recorrencia == TipoRecorrencia.ANUAL:
                movimentacao.quantidade_parcelas = 4
            else: 
                movimentacao.quantidade_parcelas = 24

        nova_repeticao = RepeticaoModel(
            quantidade_parcelas=movimentacao.quantidade_parcelas,
            tipo_recorrencia=movimentacao.tipo_recorrencia,
            valor_total=movimentacao.valor,
            data_inicio=movimentacao.data_pagamento,
            id_usuario=usuario_logado.id_usuario
        )
        
        print(f"Nova repetição criada: {nova_repeticao}")

        
        db.add(nova_repeticao)
        await db.flush()
        await db.refresh(nova_repeticao)
        
        print(f"ID da repetição: {nova_repeticao.id_repeticao}")

        
        return nova_repeticao.id_repeticao
    return None

def ajustar_data_pagamento(movimentacao: MovimentacaoSchemaReceitaDespesa, data_pagamento: date):
    if movimentacao.condicao_pagamento == CondicaoPagamento.RECORRENTE:
        if movimentacao.tipo_recorrencia == TipoRecorrencia.ANUAL:
            data_pagamento = data_pagamento.replace(year=data_pagamento.year + 1)
        elif movimentacao.tipo_recorrencia == TipoRecorrencia.QUINZENAL:
            data_pagamento += timedelta(days=15)
        elif movimentacao.tipo_recorrencia == TipoRecorrencia.SEMANAL:
            data_pagamento += timedelta(weeks=1)
        elif movimentacao.tipo_recorrencia == TipoRecorrencia.MENSAL:
            data_pagamento += relativedelta(months=1)
    else:
        data_pagamento += relativedelta(months=1)
    
    return data_pagamento

def calcular_parcelas_precisas(valor_total, quantidade_parcelas):
    valor_total = Decimal(str(valor_total))
    quantidade_parcelas = Decimal(str(quantidade_parcelas))
    
    valor_parcela = (valor_total / quantidade_parcelas).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    valor_primeira_parcela = valor_total - (valor_parcela * (quantidade_parcelas - 1))
    
    return valor_primeira_parcela, valor_parcela

@router.post('/cadastro/despesa', status_code=status.HTTP_201_CREATED)
async def create_movimentacao_despesa(
    movimentacao: MovimentacaoSchemaReceitaDespesa,
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db as session:
        try:
            today = date.today()
            categoria = await validar_categoria(session, usuario_logado, movimentacao.id_categoria)

            # Validação da soma dos valores de parentes
            soma = sum(divide.valor_parente for divide in movimentacao.divide_parente)
            if soma != movimentacao.valor:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Valor total de parentes não pode ser diferente do valor.")
            
            if movimentacao.condicao_pagamento != CondicaoPagamento.PARCELADO:
                movimentacao.quantidade_parcelas = 1

            # Ajuste da conta ou criação de fatura
            if movimentacao.forma_pagamento in [FormaPagamento.DEBITO, FormaPagamento.DINHEIRO]:
                movimentacao.id_conta = movimentacao.id_financeiro
            else:
                movimentacao.consolidado = False
                fatura, cartao_credito = await get_or_create_fatura(session, usuario_logado, movimentacao.id_financeiro, movimentacao.data_pagamento)
                if cartao_credito:
                    print(f"Cartão de Crédito {cartao_credito}")

            if movimentacao.id_conta is not None:
                conta = await validar_conta(session, usuario_logado, movimentacao.id_conta)

                
            # Preparação para criar movimentações parceladas
            valor_primeira_parcela, valor_parcela = calcular_parcelas_precisas(
                movimentacao.valor, 
                movimentacao.quantidade_parcelas
            )

            data_pagamento = movimentacao.data_pagamento

            id_repeticao = await criar_repeticao(movimentacao, usuario_logado, db)

            # Criação das movimentações parceladas
            for parcela_atual in range(1, movimentacao.quantidade_parcelas + 1):
                nova_movimentacao = MovimentacaoModel(
                    valor=valor_primeira_parcela if parcela_atual == 1 else valor_parcela,
                    descricao=movimentacao.descricao,
                    tipoMovimentacao=TipoMovimentacao.DESPESA,
                    forma_pagamento=movimentacao.forma_pagamento,
                    condicao_pagamento=movimentacao.condicao_pagamento,
                    datatime=movimentacao.datatime,
                    consolidado=movimentacao.consolidado,
                    parcela_atual= str(parcela_atual),
                    data_pagamento=data_pagamento,
                    id_conta=movimentacao.id_conta,
                    id_categoria=movimentacao.id_categoria,
                    id_fatura= fatura.id_fatura if movimentacao.forma_pagamento == FormaPagamento.CREDITO else None,
                    id_repeticao= id_repeticao if movimentacao.condicao_pagamento != CondicaoPagamento.A_VISTA  else None,
                    id_usuario=usuario_logado.id_usuario
                )
                
                
                nova_movimentacao.divisoes = []

                db.add(nova_movimentacao)
                
                if movimentacao.consolidado and parcela_atual == 1:
                    conta.saldo = conta.saldo - Decimal(valor_primeira_parcela)
        
                        
                if movimentacao.forma_pagamento == FormaPagamento.CREDITO:

                    if parcela_atual == 1 :
                        cartao_credito.limite_disponivel = cartao_credito.limite_disponivel - valor_primeira_parcela
                        fatura.fatura_gastos += valor_primeira_parcela
                        nova_movimentacao.participa_limite_fatura_gastos = True

                    elif movimentacao.condicao_pagamento == CondicaoPagamento.PARCELADO:
                        cartao_credito.limite_disponivel = cartao_credito.limite_disponivel - valor_parcela
                        fatura.fatura_gastos +=valor_parcela
                        nova_movimentacao.participa_limite_fatura_gastos = True

                    elif parcela_atual > 1: 
                        if(data_pagamento.month <= today.month and data_pagamento.year <= today.year):
                            cartao_credito.limite_disponivel = cartao_credito.limite_disponivel - valor_parcela 
                            fatura.fatura_gastos +=valor_parcela
                            nova_movimentacao.participa_limite_fatura_gastos = True
                    else: 
                        nova_movimentacao.participa_limite_fatura_gastos = False if movimentacao.forma_pagamento == FormaPagamento.CREDITO else None

                # Criação dos relacionamentos com parentes
                for divide in movimentacao.divide_parente:
                    if movimentacao.condicao_pagamento == CondicaoPagamento.PARCELADO:
                        valor_parente = divide.valor_parente / movimentacao.quantidade_parcelas
                        valor_parente_ajustado = round(valor_parente, 2)
                        valor_parente_restante = round(divide.valor_parente - (valor_parente_ajustado * movimentacao.quantidade_parcelas), 2)
                        
                        valor = valor_parente_ajustado + valor_parente_restante if parcela_atual == 1 else valor_parente_ajustado
                        # print(valor_parente, valor_parente_ajustado, valor_parente_restante )

                    else:
                        valor = divide.valor_parente
                        

                    novo_divide_parente = DivideModel(
                        id_parente= divide.id_parente,
                        valor= valor
                    )
                    nova_movimentacao.divisoes.append(novo_divide_parente)


                movimentacao.consolidado = False
                
                data_pagamento = ajustar_data_pagamento(movimentacao, data_pagamento)

                if movimentacao.forma_pagamento == FormaPagamento.CREDITO:       
                    fatura, cartao = await get_or_create_fatura(session, usuario_logado, movimentacao.id_financeiro, data_pagamento)
            await db.commit()
            return {"message": "Despesa cadastrada com sucesso."}
        
        except Exception as e:
            await handle_db_exceptions(session, e)
        finally:
            await session.close()
            
@router.post('/cadastro/receita', status_code=status.HTTP_201_CREATED)
async def create_movimentacao_receita(
    movimentacao: MovimentacaoSchemaReceitaDespesa,
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db as session:
        try:
            categoria = await validar_categoria(session, usuario_logado, movimentacao.id_categoria)

            if movimentacao.condicao_pagamento != CondicaoPagamento.PARCELADO:
                movimentacao.quantidade_parcelas = 1
            else:
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Não existe receita parcelada")

            
            if movimentacao.forma_pagamento in [FormaPagamento.DEBITO, FormaPagamento.DINHEIRO]:
                movimentacao.id_conta = movimentacao.id_financeiro
            else:
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Só é aceito dinheiro ou débito para receita")

            if len(movimentacao.divide_parente) > 1:
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Só é um parente (o usuário) para receitas")
            else: 
                parente_query = await session.execute(
                    select(ParenteModel).where(ParenteModel.id_parente == movimentacao.divide_parente[0].id_parente)
                )
                parente = parente_query.scalars().first()
                if parente.nome != usuario_logado.nome_completo:
                    raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Só é aceito o próprio usuário para dividir uma receita")


            if movimentacao.id_conta is not None:
                conta = await validar_conta(session, usuario_logado, movimentacao.id_conta)

            data_pagamento = movimentacao.data_pagamento

            id_repeticao = await criar_repeticao(movimentacao, usuario_logado, db)

            # Criação das movimentações parceladas
            for parcela_atual in range(1, movimentacao.quantidade_parcelas + 1):
                nova_movimentacao = MovimentacaoModel(
                    valor= movimentacao.valor,
                    descricao=movimentacao.descricao,
                    tipoMovimentacao=TipoMovimentacao.RECEITA,
                    forma_pagamento=movimentacao.forma_pagamento,
                    condicao_pagamento=movimentacao.condicao_pagamento,
                    datatime=movimentacao.datatime,
                    consolidado=movimentacao.consolidado,
                    parcela_atual= str(parcela_atual),
                    data_pagamento=data_pagamento,
                    id_conta=movimentacao.id_conta,
                    id_categoria=movimentacao.id_categoria,
                    id_fatura= None,
                    id_repeticao= id_repeticao if movimentacao.condicao_pagamento != CondicaoPagamento.A_VISTA  else None,
                    id_usuario=usuario_logado.id_usuario,
                    participa_limite_fatura_gastos = None

                )
                
                nova_movimentacao.divisoes = []

                db.add(nova_movimentacao)

                if movimentacao.consolidado and parcela_atual == 1:
                    conta.saldo = conta.saldo + Decimal(movimentacao.valor)
        

                # Criação dos relacionamentos com parentes
                for divide in movimentacao.divide_parente:
                    
                    valor = divide.valor_parente
                        
                    novo_divide_parente = DivideModel(
                        id_parente= divide.id_parente,
                        valor= valor
                    )
                    nova_movimentacao.divisoes.append(novo_divide_parente)


                movimentacao.consolidado = False
                
                data_pagamento = ajustar_data_pagamento(movimentacao, data_pagamento)

            await db.commit()
            return {"message": "Receita cadastrada com sucesso."}
        
        
        except Exception as e:
            await handle_db_exceptions(session, e)

        finally:
            await session.close()

@router.post('/cadastro/transferencia', status_code=status.HTTP_201_CREATED)
async def create_movimentacao(
    movimentacao: MovimentacaoSchemaTransferencia,
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db as session:
        try:
            print(f"Usuário autenticado: {usuario_logado}")

            if movimentacao.id_conta_transferencia == movimentacao.id_conta_atual:
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="As contas devem ter IDs diferentes")
            
            contas_a_verificar = [movimentacao.id_conta_atual, movimentacao.id_conta_transferencia]
            
            query = select(ContaModel).where(
                ContaModel.id_usuario == usuario_logado.id_usuario,
                ContaModel.id_conta.in_(contas_a_verificar)
            )
            result = await session.execute(query)
            contas_encontradas = result.scalars().all()
            
            if len(contas_encontradas) < 2:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contas não encontradas ou não pertencem ao usuário.")

            for conta in contas_encontradas:
                if conta.id_conta == movimentacao.id_conta_atual:
                    conta.saldo = conta.saldo - Decimal(movimentacao.valor)
                elif conta.id_conta == movimentacao.id_conta_transferencia:
                    conta.saldo = conta.saldo + Decimal(movimentacao.valor)
            
            nova_movimentacao = MovimentacaoModel(
                valor=Decimal(movimentacao.valor),
                descricao=movimentacao.descricao,
                id_conta=movimentacao.id_conta_atual,
                id_conta_destino=movimentacao.id_conta_transferencia,
                tipoMovimentacao="Transferencia",  
                forma_pagamento="Débito",           
                consolidado=True,                   
                condicao_pagamento="À vista",       
                datatime=datetime.now(),            
                data_pagamento=datetime.now().date(), 
                id_usuario=usuario_logado.id_usuario,
                participa_limite_fatura_gastos = None
            )
            
            session.add(nova_movimentacao)
            await session.commit()
            return {nova_movimentacao.id_movimentacao}
        
        except Exception as e:
            await handle_db_exceptions(session, e)
        
        finally:
            await session.close()

@router.post('/editar/{id_movimentacao}', status_code=status.HTTP_202_ACCEPTED)
async def update_movimentacao(
    id_movimentacao: int,
    movimentacao_update: MovimentacaoSchemaUpdate,
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db as session:
        # Verificar se a movimentação existe
        query_movimentacao = select(MovimentacaoModel).options(
            joinedload(MovimentacaoModel.divisoes).joinedload(DivideModel.parentes),
            joinedload(MovimentacaoModel.fatura, innerjoin=False).joinedload(FaturaModel.cartao_credito)

        ).filter(
                MovimentacaoModel.id_movimentacao == id_movimentacao,
                MovimentacaoModel.id_usuario == usuario_logado.id_usuario)
        
        result = await session.execute(query_movimentacao)
        movimentacao: MovimentacaoModel = result.scalars().unique().one_or_none()

        if not movimentacao:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimentação não encontrada")

         # Verificar se a conta pertence ao usuário logado (se fornecida)
        if movimentacao_update.id_financeiro:
            if(movimentacao_update.forma_pagamento != FormaPagamento.CREDITO):
                query_conta = select(ContaModel).where(
                    ContaModel.id_conta == movimentacao_update.id_financeiro,
                    ContaModel.id_usuario == usuario_logado.id_usuario)
                result_conta = await session.execute(query_conta)
                conta = result_conta.scalars().first()

                if not conta:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada ou não pertence ao usuário.")
            else:
                query_credito = select(CartaoCreditoModel).where(
                    CartaoCreditoModel.id_cartao_credito == movimentacao_update.id_financeiro,
                    CartaoCreditoModel.id_usuario == usuario_logado.id_usuario)
                result_credito = await session.execute(query_credito)
                credito = result_credito.scalars().first()

                if not credito:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cartão de credito não encontrado ou não pertence ao usuário.")
                

        # Verificar se a categoria pertence ao usuário logado (se fornecida)
        if movimentacao_update.id_categoria:
            query_categoria = select(CategoriaModel).where(
                CategoriaModel.id_categoria == movimentacao_update.id_categoria,
                CategoriaModel.id_usuario == usuario_logado.id_usuario)
            
            result_categoria = await session.execute(query_categoria)
            categoria = result_categoria.scalars().first()

            if not categoria:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada ou não pertence ao usuário.")

            
        if(movimentacao.consolidado and movimentacao.id_fatura):
            raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Não pode editar fatura consolidada")
        

        movimentacao.descricao = movimentacao_update.descricao
        movimentacao.datatime = movimentacao_update.datatime
        
        
    
        today = date.today()
        
        
        if(movimentacao.tipoMovimentacao != TipoMovimentacao.TRANSFERENCIA): #movimentacao receita ou despesa
            if(movimentacao.data_pagamento != movimentacao_update.data_pagamento ):
                    movimentacao.data_pagamento = movimentacao_update.data_pagamento
            movimentacao.id_categoria = movimentacao_update.id_categoria
            
            query_conta_antiga = select(ContaModel).where(
                            ContaModel.id_conta == movimentacao.id_conta,
                            ContaModel.id_usuario == usuario_logado.id_usuario)
                            
            result_conta_antiga = await session.execute(query_conta_antiga)
            conta_antiga = result_conta_antiga.scalars().first()

            
            if(movimentacao.forma_pagamento != FormaPagamento.CREDITO):#movimentacao dinheiro ou debito
                
                if(movimentacao_update.valor != movimentacao.valor
                   or movimentacao_update.forma_pagamento == FormaPagamento.CREDITO):
                
                    if(movimentacao.consolidado):
                        movimentacao.consolidado = False
                        
                        if(movimentacao_update.forma_pagamento == FormaPagamento.CREDITO 
                            ):
                            ajustar_saldo_conta(conta_antiga, movimentacao, False)
                        else:    
                            ajustar_saldo_conta(conta, movimentacao, False)

                    
                if(movimentacao_update.forma_pagamento != FormaPagamento.CREDITO):#tipo dinheiro ou conta
                   
                    if (movimentacao.id_conta != movimentacao_update.id_financeiro ):
                        ajustar_saldo_conta(conta_antiga, movimentacao, False)

                    # print("teste", movimentacao.id_conta, movimentacao_update.id_financeiro, movimentacao_update.consolidado )
                    if(movimentacao_update.consolidado 
                       and ( (movimentacao.consolidado is False or movimentacao_update.valor != movimentacao.valor) 
                            or (movimentacao.id_conta != movimentacao_update.id_financeiro))):
                        movimentacao.consolidado = True
                        movimentacao.valor = movimentacao_update.valor
                        # print("Entrou true")
                        ajustar_saldo_conta(conta, movimentacao, True)
                    elif (movimentacao_update.consolidado is False and (movimentacao_update.valor == movimentacao.valor and movimentacao.consolidado is True)):
                        movimentacao.consolidado = False
                        movimentacao.valor = movimentacao_update.valor
                        # print("Entrou false", movimentacao_update.consolidado,movimentacao_update.valor, movimentacao.valor)
                        ajustar_saldo_conta(conta, movimentacao, False)
                        
                    movimentacao.id_conta = movimentacao_update.id_financeiro

                else: #tipo credito
                    movimentacao.id_conta = None
            
                    fatura, cartao = await get_or_create_fatura(session, usuario_logado, movimentacao_update.id_financeiro, movimentacao_update.data_pagamento)
                    
                    movimentacao.id_fatura = fatura.id_fatura
                    print(cartao, cartao.limite_disponivel, fatura)
                    
                    if(movimentacao.data_pagamento.month <= today.month and movimentacao.data_pagamento.year <= today.year
                       or movimentacao.condicao_pagamento == CondicaoPagamento.PARCELADO):
                        ajustar_limite_fatura_gastos(cartao, fatura, movimentacao, True)
                    else:
                        movimentacao.participa_limite_fatura_gastos = False
            else: #movimentacao antiga era do tipo credito
                
                if(movimentacao.participa_limite_fatura_gastos == True):
                        ajustar_limite_fatura_gastos(movimentacao.fatura.cartao_credito, movimentacao.fatura, movimentacao, False)

                        # alterar_limite_fatura_gastos(movimentacao.id_movimentacao, False, db, usuario_logado) # mais barato usar a função do endpoint pois nao precisa consultar o cartao de credito antigo
                movimentacao.valor = movimentacao_update.valor
        
                if(movimentacao_update.forma_pagamento != FormaPagamento.CREDITO): #movimentacao_update é do do tipo conta 
                    movimentacao.id_conta = movimentacao_update.id_financeiro
                    movimentacao.data_pagamento = movimentacao_update.data_pagamento
                    movimentacao.participa_limite_fatura_gastos = None
                    movimentacao.id_fatura = None
                    if(movimentacao_update.consolidado):
                        movimentacao.consolidado = True
                        ajustar_saldo_conta(conta, movimentacao, True)
                    else:
                        movimentacao.consolidado = False # como nao estava na conta (era credito), só colocar como false e nao atualiza o saldo
                else: #movimentacao_update é do do tipo credito 
                    
                    #como eu nao sei se o cartao de credito foi alterado (para isso precisaria pegar o id do cartao),
                    # vou sempre atualizar a fatura
                    movimentacao.consolidado = False

                    fatura, cartao = await get_or_create_fatura(session, usuario_logado, movimentacao_update.id_financeiro, movimentacao_update.data_pagamento)

                    movimentacao.id_fatura = fatura.id_fatura
                    
                    if(movimentacao.data_pagamento.month <= today.month and movimentacao.data_pagamento.year <= today.year 
                       or movimentacao.condicao_pagamento == CondicaoPagamento.PARCELADO):
                        ajustar_limite_fatura_gastos(cartao, fatura, movimentacao, True)
                    else:
                        movimentacao.participa_limite_fatura_gastos = False
                    
            movimentacao.forma_pagamento = movimentacao_update.forma_pagamento
            movimentacao.valor = movimentacao_update.valor # caso nao tenha passado por nenhum if em !=credito
            
            if(movimentacao.tipoMovimentacao == TipoMovimentacao.DESPESA):
                
                if(len(movimentacao_update.divide_parente) > 0):
                    soma = sum(divide.valor_parente for divide in movimentacao_update.divide_parente)
                    if soma != movimentacao_update.valor:
                        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Valor total de parentes não pode ser diferente do valor.")
                
                
                for divisao in movimentacao.divisoes:
                    for membro in movimentacao_update.divide_parente:
                        if(membro.id_parente == divisao.id_parente):
                            divisao.valor = membro.valor_parente
        else: #movimentacao tipo transferencia
            
            if(movimentacao_update.id_conta_atual == movimentacao_update.id_conta_transferencia):
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="As contas devem ter IDs diferentes")
            
            if(movimentacao_update.valor != movimentacao.valor or
               movimentacao_update.id_conta_atual != movimentacao.id_conta or
               movimentacao_update.id_conta_transferencia != movimentacao.id_conta_destino ):
                
                contas_a_verificar = [movimentacao.id_conta, movimentacao.id_conta_destino]
            
                contas_encontradas_antigas = await buscar_contas_usuario(
                    session=session,
                    id_usuario=usuario_logado.id_usuario,
                    contas_ids=contas_a_verificar
                )
                                
                if len(contas_encontradas_antigas) < 2:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contas não encontradas ou não pertencem ao usuário.")
                
                for conta in contas_encontradas_antigas:
                    # print("conta antiga primeiro for", conta.saldo, conta.id_conta, movimentacao.valor, movimentacao_update.valor)

                    if conta.id_conta == movimentacao.id_conta:
                        conta.saldo = conta.saldo + Decimal(movimentacao.valor)
                    elif conta.id_conta == movimentacao.id_conta_destino:
                        conta.saldo = conta.saldo - Decimal(movimentacao.valor)
                        
                    # print("conta antiga segundo for", conta.saldo, conta.id_conta)
                        
                if (
                    (movimentacao_update.id_conta_atual != movimentacao.id_conta 
                    or movimentacao_update.id_conta_transferencia != movimentacao.id_conta_destino)
                    and not (
                        movimentacao_update.id_conta_atual == movimentacao.id_conta_destino 
                        and movimentacao_update.id_conta_transferencia == movimentacao.id_conta
                    )
                ):
                    # print("if transferencia")

                    contas_novas = [movimentacao_update.id_conta_atual, movimentacao_update.id_conta_transferencia]
                    
                    contas_encontradas_novas = await buscar_contas_usuario(
                        session=session,
                        id_usuario=usuario_logado.id_usuario,
                        contas_ids=contas_novas
                    )
                    
                    if len(contas_encontradas_novas) < 2:
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contas não encontradas ou não pertencem ao usuário.")
                    
                    for conta in contas_encontradas_novas:
                        # print("conta nova primeiro for", conta.saldo, conta.id_conta, movimentacao.valor, movimentacao_update.valor)
                        if conta.id_conta == movimentacao_update.id_conta_atual:
                            conta.saldo = conta.saldo - Decimal(movimentacao_update.valor)
                            movimentacao.id_conta = conta.id_conta
                        elif conta.id_conta == movimentacao_update.id_conta_transferencia:
                            conta.saldo = conta.saldo + Decimal(movimentacao_update.valor)
                            movimentacao.id_conta_destino = conta.id_conta
                        # print("conta nova segundo for", conta.saldo, conta.id_conta, movimentacao.valor, movimentacao_update.valor)

                else:
                    # print("else transferencia")
                    for conta in contas_encontradas_antigas:
                        if conta.id_conta == movimentacao_update.id_conta_atual:
                            conta.saldo = conta.saldo - Decimal(movimentacao_update.valor)
                            movimentacao.id_conta =  conta.id_conta
                        elif conta.id_conta == movimentacao_update.id_conta_transferencia:
                            conta.saldo = conta.saldo + Decimal(movimentacao_update.valor)
                            movimentacao.id_conta_destino = conta.id_conta
                        # print("conta antiga else", conta.saldo, conta.id_conta)


                            
                movimentacao.valor = movimentacao_update.valor

        try:
            await session.commit()
            #isso deve commitar, conta, fatura e movimentacao
            return {"message": "Edição feita com sucesso."}
        except Exception as e:
            await handle_db_exceptions(session, e)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Erro ao atualizar movimentação")

        finally:
            await session.close()

        
        
async def buscar_contas_usuario(
    session: AsyncSession,
    id_usuario: int,
    contas_ids: List[int]
) -> List[ContaModel]:

    query = select(ContaModel).where(
        ContaModel.id_usuario == id_usuario,
        ContaModel.id_conta.in_(contas_ids)
    )
    result = await session.execute(query)
    return result.scalars().all()
    
@router.get('/listar', response_model=List[MovimentacaoSchemaId])
async def listar_movimentacoes(
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db:  
        query = (
            select(MovimentacaoModel)
            .options(joinedload(MovimentacaoModel.conta), 
                      joinedload(MovimentacaoModel.repeticao)) 
            .join(MovimentacaoModel.conta)
            .filter(ContaModel.id_usuario == usuario_logado.id_usuario)
        )
        result = await db.execute(query)
        movimentacoes = result.scalars().all()
        

        if not movimentacoes:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhuma movimentação encontrada")

        # Mapeando as movimentações para o schema
        response = [
            MovimentacaoSchemaId(
                id_movimentacao=mov.id_movimentacao,
                valor=mov.valor,
                descricao=mov.descricao,
                tipoMovimentacao=mov.tipoMovimentacao,
                forma_pagamento=mov.forma_pagamento,
                condicao_pagamento=mov.condicao_pagamento,
                datatime=mov.datatime,
                quantidade_parcelas=mov.repeticao.quantidade_parcelas if mov.repeticao else None,
                consolidado=mov.consolidado,
                tipo_recorrencia=mov.repeticao.tipo_recorrencia if mov.repeticao else None,
                parcela_atual=mov.parcela_atual,
                data_pagamento=mov.data_pagamento,
                id_conta=mov.id_conta,
                id_categoria=mov.id_categoria,
                id_fatura=mov.id_fatura,
                id_repeticao=mov.id_repeticao
            )
            for mov in movimentacoes
        ]

        return response

@router.post('/listar/filtro', response_model=List[MovimentacaoSchemaList])
async def listar_movimentacoes(
    requestFilter: MovimentacaoRequestFilterSchema,
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db: 
        
        mes_anterior = requestFilter.mes - 1 if requestFilter.mes > 1 else 12
        ano_anterior = requestFilter.ano if requestFilter.mes > 1 else requestFilter.ano - 1

        
        if requestFilter.id_cartao_credito is None:
        
            condicoes = [
                MovimentacaoModel.id_usuario == usuario_logado.id_usuario,
                extract('month', MovimentacaoModel.data_pagamento) == requestFilter.mes,
                extract('year', MovimentacaoModel.data_pagamento) == requestFilter.ano
            ] 
        else:
            condicoes = [
                MovimentacaoModel.id_usuario == usuario_logado.id_usuario,
                  or_(
                    # Condição para o mês atual
                    and_(
                        extract('month', MovimentacaoModel.data_pagamento) == requestFilter.mes,
                        extract('year', MovimentacaoModel.data_pagamento) == requestFilter.ano
                    ),
                    # Condição para o mês anterior
                    and_(
                        extract('month', MovimentacaoModel.data_pagamento) == mes_anterior,
                        extract('year', MovimentacaoModel.data_pagamento) == ano_anterior
                    )
                )
            ]
  
        if requestFilter.forma_pagamento is not None: 
            condicoes.append(MovimentacaoModel.forma_pagamento == requestFilter.forma_pagamento)
                
        if requestFilter.tipo_movimentacao is not None: 
            condicoes.append(MovimentacaoModel.tipoMovimentacao == requestFilter.tipo_movimentacao)        

        if requestFilter.consolidado is not None: 
            condicoes.append(MovimentacaoModel.consolidado == requestFilter.consolidado)
            
        if requestFilter.id_categoria is not None: 
            condicoes.append(MovimentacaoModel.id_categoria == requestFilter.id_categoria)
            
        if requestFilter.id_conta is not None: 
            condicoes.append(
                    (MovimentacaoModel.id_conta == requestFilter.id_conta) | 
                    (MovimentacaoModel.id_conta_destino == requestFilter.id_conta)
                )        
            
        query = construir_query_movimentacao(condicoes)

        if requestFilter.id_parente is not None:
            query = query.join(DivideModel, MovimentacaoModel.divisoes).where(DivideModel.id_parente == requestFilter.id_parente)
            
        if requestFilter.id_cartao_credito is not None:
            
            data, data_anterior = await get_data(
                db=db,
                requestFilter = requestFilter,
                mes_anterior = mes_anterior,
                ano_anterior = ano_anterior
            )            
            
            query = query.join(
                FaturaModel, MovimentacaoModel.fatura
            ).join(
                CartaoCreditoModel, FaturaModel.cartao_credito
            ).where(
                CartaoCreditoModel.id_cartao_credito == requestFilter.id_cartao_credito,
                and_(
                    FaturaModel.data_fechamento > data_anterior,
                    FaturaModel.data_fechamento <= data
                )
            )
            
    
        
        result = await db.execute(query)
        movimentacoes = result.scalars().all()
        

 
        if not movimentacoes:
            response = []
        else:
            response = construir_response(movimentacoes, requestFilter)

        return response

async def get_data(
    db: AsyncSession,
    requestFilter: MovimentacaoRequestFilterSchema,
    mes_anterior: int,
    ano_anterior: int
):
    # query_mes_anterior = select(FaturaModel).filter(
    #     FaturaModel.id_cartao_credito == requestFilter.id_cartao_credito,
    #     extract('month', FaturaModel.data_fechamento) == mes_anterior,
    #     extract('year', FaturaModel.data_fechamento) == ano_anterior
    # )
    
            
    # query_mes_atual = select(FaturaModel).filter(
    #     FaturaModel.id_cartao_credito == requestFilter.id_cartao_credito,
    #     extract('month', FaturaModel.data_fechamento) == requestFilter.mes,
    #     extract('year', FaturaModel.data_fechamento) == requestFilter.ano
    # )
    
    # result_mes_anterior = await db.execute(query_mes_anterior)
    # fatura_mes_anterior = result_mes_anterior.scalars().first()
    
    # result_mes_atual = await db.execute(query_mes_atual)
    # fatura_mes_atual = result_mes_atual.scalars().first()     
    
    # print(f"Data de fechamento da fatura mes atual: {fatura_mes_atual.id_fatura, fatura_mes_atual.data_fechamento}")
    # print(f"Data de fechamento da fatura mes anterior: {fatura_mes_anterior.id_fatura, fatura_mes_anterior.data_fechamento}")
    
    # data = fatura_mes_atual.data_fechamento if fatura_mes_atual else date(requestFilter.ano, requestFilter.mes, requestFilter.dia_fechamento)

    # data_anterior = fatura_mes_anterior.data_fechamento if fatura_mes_anterior else  data - relativedelta(months=1)
    
    
    # print(f"Datas 1: {data, data_anterior}")

    
    query_combined = select(FaturaModel).filter(
        FaturaModel.id_cartao_credito == requestFilter.id_cartao_credito,
        or_(
            and_(
                extract('month', FaturaModel.data_fechamento) == mes_anterior,
                extract('year', FaturaModel.data_fechamento) == ano_anterior
            ),
            and_(
                extract('month', FaturaModel.data_fechamento) == requestFilter.mes,
                extract('year', FaturaModel.data_fechamento) == requestFilter.ano
            )
        )
    )

    result_combined = await db.execute(query_combined)
    faturas_combined = result_combined.scalars().all()

    # for fatura in faturas_combined:
    #     print(f"Data de fechamento da fatura : {fatura.id_fatura, fatura.data_fechamento}")

    fatura_mes_anterior = next((
            fatura for fatura in faturas_combined
            if fatura.data_fechamento.month == mes_anterior and fatura.data_fechamento.year == ano_anterior),None
    )

    fatura_mes_atual = next((
        fatura for fatura in faturas_combined
        if fatura.data_fechamento.month == requestFilter.mes and fatura.data_fechamento.year == requestFilter.ano),None
    )
  
            
    data = fatura_mes_atual.data_fechamento if fatura_mes_atual else date(requestFilter.ano, requestFilter.mes, requestFilter.dia_fechamento)

    data_anterior = fatura_mes_anterior.data_fechamento if fatura_mes_anterior else  data - relativedelta(months=1)
    

    return data, data_anterior
    
def construir_query_movimentacao(condicoes):
    query = (
            select(MovimentacaoModel)
            .options(
                selectinload(MovimentacaoModel.categoria),
                selectinload(MovimentacaoModel.conta),
                selectinload(MovimentacaoModel.conta_destino),  
                selectinload(MovimentacaoModel.repeticao),
                selectinload(MovimentacaoModel.divisoes),
                selectinload(MovimentacaoModel.divisoes, DivideModel.parentes),
                selectinload(MovimentacaoModel.fatura),
                selectinload(MovimentacaoModel.fatura, FaturaModel.cartao_credito),
                selectinload(MovimentacaoModel.fatura, FaturaModel.conta)

            )
            .where(*condicoes)  
            .order_by(
                    MovimentacaoModel.data_pagamento,
                    MovimentacaoModel.datatime 
                )
        )
    return query

def construir_response(movimentacoes: List, requestFilter: MovimentacaoRequestFilterSchema) -> List[MovimentacaoSchemaList]:
    response = [
        MovimentacaoSchemaList(
            id_movimentacao=mov.id_movimentacao,
            valor=mov.valor,
            descricao=mov.descricao,
            tipoMovimentacao=mov.tipoMovimentacao,
            forma_pagamento=mov.forma_pagamento,
            condicao_pagamento=mov.condicao_pagamento,
            datatime=mov.datatime,
            quantidade_parcelas= mov.repeticao.quantidade_parcelas if mov.repeticao else None , 
            consolidado=mov.consolidado,
            tipo_recorrencia= mov.repeticao.tipo_recorrencia if mov.repeticao else None , 
            parcela_atual=mov.parcela_atual,
            data_pagamento=mov.data_pagamento,
            id_conta=mov.id_conta,
            id_conta_destino= mov.id_conta_destino,
            nome_conta_destino= mov.conta_destino.nome if mov.conta_destino else None,
            id_categoria=mov.id_categoria if mov.categoria else None,
            nome_icone_categoria=mov.categoria.nome_icone if mov.categoria else None,
            nome_conta = mov.conta.nome if mov.conta else None,
            nome_cartao_credito = mov.fatura.cartao_credito.nome if mov.fatura else None,
            id_cartao_credito= mov.fatura.id_cartao_credito if mov.fatura else None,
            id_fatura=mov.id_fatura,
            id_repeticao=mov.id_repeticao,
            participa_limite_fatura_gastos = mov.participa_limite_fatura_gastos,

            divide_parente=[
                ParenteResponse(
                    id_parente=divide.id_parente,
                    valor_parente=divide.valor, 
                    nome_parente= divide.parentes.nome
                )
                for divide in mov.divisoes 
            ],
            fatura_info = 
                FaturaSchemaInfo(
                    data_vencimento= mov.fatura.data_vencimento,
                    data_fechamento = mov.fatura.data_fechamento,
                    data_pagamento = mov.fatura.data_pagamento or None,
                    id_cartao_credito = mov.fatura.id_cartao_credito,
                    id_conta = mov.fatura.id_conta,
                    nome_conta = mov.fatura.conta.nome if mov.fatura.conta else None,
                    fatura_gastos= mov.fatura.fatura_gastos
                ) if requestFilter and  requestFilter.id_cartao_credito is not None else None
        )
        for mov in movimentacoes
    ]
    return response

    
    
@router.get("/movimentacoes_vencidas/{tipo_receita}", response_model=MovimentacaoFaturaSchemaList)
async def get_movimentacoes_vencidas(
    tipo_receita: bool,
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    try:
        dataHoje = datetime.now()

        condicoes = [
            MovimentacaoModel.id_usuario == usuario_logado.id_usuario,
            MovimentacaoModel.consolidado == False,
            MovimentacaoModel.data_pagamento <= dataHoje,
            MovimentacaoModel.id_fatura == None,
            MovimentacaoModel.forma_pagamento != FormaPagamento.CREDITO
        ]

        if tipo_receita:
            condicoes.append(MovimentacaoModel.tipoMovimentacao == TipoMovimentacao.RECEITA)
            faturas = []
        else:
            condicoes.append(MovimentacaoModel.tipoMovimentacao == TipoMovimentacao.DESPESA)

                        
            query_fatura = (select(FaturaModel)
                .options(joinedload(FaturaModel.cartao_credito))
                .join(FaturaModel.cartao_credito) 
                .where(
                    FaturaModel.data_fechamento <= dataHoje,
                    FaturaModel.fatura_gastos > 0,
                    CartaoCreditoModel.id_usuario == usuario_logado.id_usuario  
                )
            )
          

            result_fatura = await db.execute(query_fatura)
            faturas_result = result_fatura.scalars().all()

            faturas = [
                FaturaSchemaInfo(
                    data_vencimento=fat.data_vencimento,
                    data_fechamento=fat.data_fechamento,
                    data_pagamento=fat.data_pagamento or None,
                    id_cartao_credito=fat.id_cartao_credito,
                    id_conta=fat.id_conta,
                    nome_conta= None,
                    nome_cartao = fat.cartao_credito.nome,
                    fatura_gastos = fat.fatura_gastos
                )
                for fat in faturas_result
            ]
            # print('dataaaaaaas', dataHoje, faturas)


        query = construir_query_movimentacao(condicoes)
        result = await db.execute(query)
        movimentacoes = result.scalars().all()

        response = MovimentacaoFaturaSchemaList(
            movimentacoes=construir_response(movimentacoes, None) if movimentacoes else [],
            faturas=faturas
        )

        return response

    except Exception as e:
        await handle_db_exceptions(db, e)
   


@router.post("/consolidar")
async def consolidar_movimentacao(
    movimentacoesConsolida: MovimentacaoSchemaConsolida, 
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)):

    movimentacao_query = (
        select(MovimentacaoModel)
        .options(joinedload(MovimentacaoModel.conta))
        .where(
            MovimentacaoModel.id_movimentacao == movimentacoesConsolida.id_movimentacao,
            MovimentacaoModel.id_usuario == usuario_logado.id_usuario
        )
    )
    movimentacao_result = await db.execute(movimentacao_query)
    movimentacao = movimentacao_result.scalar_one_or_none()

    if not movimentacao:
        raise HTTPException(status_code=404, detail="Movimentação não encontrada")

    if movimentacao.id_fatura is not None:
        raise HTTPException(status_code=400, detail="Não é possível consolidar uma movimentação com fatura relacionada")

    movimentacao.consolidado = movimentacoesConsolida.consolidado

    conta = movimentacao.conta
    ajustar_saldo_conta(conta, movimentacao, movimentacoesConsolida.consolidado)

    await db.commit()

    return {"detail": "Movimentação consolidada com sucesso", "movimentacao": movimentacao}

def ajustar_saldo_conta(
    conta: ContaModel,
    movimentacao: MovimentacaoModel,
    consolidado: bool,
):
    if movimentacao.tipoMovimentacao == TipoMovimentacao.DESPESA:
        if consolidado:
            conta.saldo -= movimentacao.valor
        else:
            conta.saldo += movimentacao.valor
    elif movimentacao.tipoMovimentacao == TipoMovimentacao.RECEITA:
        if consolidado:
            conta.saldo += movimentacao.valor
        else:
            conta.saldo -= movimentacao.valor
            

    

@router.post("/participa_limite_faturas_gastos")
async def alterar_limite_fatura_gastos(
    id_movimentacao: int,
    participa_limite_fatura_gastos: bool,
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    movimentacao_query = (
        select(MovimentacaoModel)
        .options(
            joinedload(MovimentacaoModel.fatura).joinedload(FaturaModel.cartao_credito)
        )
        .where(
            MovimentacaoModel.id_movimentacao == id_movimentacao,
            MovimentacaoModel.id_usuario == usuario_logado.id_usuario
        )
    )
    movimentacao_result = await db.execute(movimentacao_query)
    movimentacao = movimentacao_result.scalar_one_or_none()

    if not movimentacao:
        raise HTTPException(status_code=404, detail="Movimentação não encontrada")

    if movimentacao.id_fatura is None:
        raise HTTPException(status_code=400, detail="Não é possível alterar limite e gastos de uma movimentação que não tem id_fatura")

    fatura = movimentacao.fatura
    if not fatura:
        raise HTTPException(status_code=404, detail="Fatura não encontrada")

    cartao_credito = fatura.cartao_credito
    if not cartao_credito:
        raise HTTPException(status_code=404, detail="Cartão de crédito não encontrado")

    ajustar_limite_fatura_gastos(cartao_credito, fatura, movimentacao, participa_limite_fatura_gastos) 
    await db.commit()

    return {"detail": "Limite de fatura e gastos atualizados com sucesso"}

def ajustar_limite_fatura_gastos(
    cartao_credito: CartaoCreditoModel,
    fatura: FaturaModel,
    movimentacao: MovimentacaoModel,
    participa_limite_fatura_gastos: bool
):
    if participa_limite_fatura_gastos is False:
        cartao_credito.limite_disponivel += movimentacao.valor
        fatura.fatura_gastos -= movimentacao.valor
        movimentacao.participa_limite_fatura_gastos = False
    elif participa_limite_fatura_gastos is True:
        cartao_credito.limite_disponivel -= movimentacao.valor
        fatura.fatura_gastos += movimentacao.valor
        movimentacao.participa_limite_fatura_gastos = True   


@router.delete('/deletar/{id_movimentacao}', status_code=status.HTTP_204_NO_CONTENT)
async def deletar_movimentacao(
    id_movimentacao: int,
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    async with db as session:
        query = select(MovimentacaoModel).where(
            MovimentacaoModel.id_movimentacao == id_movimentacao,
            MovimentacaoModel.id_usuario == usuario_logado.id_usuario
        )
        
        result = await session.execute(query)
        movimentacao = result.scalars().first() 

        if not movimentacao:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimentação não encontrada.")

        # Verificar se a movimentação tem id_fatura e está consolidada
        if movimentacao.id_fatura is not None and movimentacao.consolidado:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Movimentação consolidada em fatura não pode ser deletada.")
        
        if movimentacao.id_repeticao is not None:
            repetidas_query = select(MovimentacaoModel).where(
                MovimentacaoModel.id_repeticao == movimentacao.id_repeticao,
                MovimentacaoModel.id_usuario == usuario_logado.id_usuario
            ).order_by(MovimentacaoModel.data_pagamento)  

            repetidas_result = await session.execute(repetidas_query)
            movimentacoes_repetidas = repetidas_result.scalars().all()

            repeticao_query = select(RepeticaoModel).where(
                RepeticaoModel.id_repeticao == movimentacao.id_repeticao
            )

            repeticao_result = await session.execute(repeticao_query)
            repeticao = repeticao_result.scalars().first()

            if movimentacoes_repetidas and movimentacoes_repetidas[0].id_movimentacao == id_movimentacao:
                for mov_repetida in movimentacoes_repetidas:
                    await processar_delecao_movimentacao(mov_repetida, session, usuario_logado)

                if repeticao:
                    await session.delete(repeticao)
            else:
                subsequentes = [
                    mov for mov in movimentacoes_repetidas 
                    if mov.data_pagamento >= movimentacao.data_pagamento
                ]
                for mov_subsequente in subsequentes:
                    await processar_delecao_movimentacao(mov_subsequente, session, usuario_logado)
                    repeticao.valor_total -= movimentacao.valor

                repeticao.quantidade_parcelas -= len(subsequentes)

        else:
            await processar_delecao_movimentacao(movimentacao, session, usuario_logado)

        await session.commit()

        return {"message": "Deletado com sucesso."}

async def processar_delecao_movimentacao(movimentacao: MovimentacaoModel, session: AsyncSession, usuario_logado: UsuarioModel):
    if movimentacao.consolidado and movimentacao.id_conta is not None:
        conta_query = select(ContaModel).where(
            ContaModel.id_conta == movimentacao.id_conta,
            ContaModel.id_usuario == usuario_logado.id_usuario
        )
        conta_result = await session.execute(conta_query)
        conta = conta_result.scalars().one_or_none()

        if conta:
            if movimentacao.tipoMovimentacao == TipoMovimentacao.DESPESA:
                conta.saldo += Decimal(movimentacao.valor)
            elif movimentacao.tipoMovimentacao == TipoMovimentacao.RECEITA:
                conta.saldo -= Decimal(movimentacao.valor)
            elif movimentacao.tipoMovimentacao == TipoMovimentacao.TRANSFERENCIA:
                conta_destino = await session.get(ContaModel, movimentacao.id_conta_destino)
                
                if conta_destino:
                    conta.saldo += Decimal(movimentacao.valor)
                    conta_destino.saldo -= Decimal(movimentacao.valor)
                    session.add(conta_destino)

            session.add(conta)     
                                                                                                                                                                                                                                                                                                                                                                                                                                                         
    if movimentacao.participa_limite_fatura_gastos:

        fatura_query = select(FaturaModel).where(
            FaturaModel.id_fatura == movimentacao.id_fatura
        )
        fatura_result = await session.execute(fatura_query)
        fatura = fatura_result.scalars().one_or_none()

        if fatura:
            fatura.fatura_gastos -= Decimal(movimentacao.valor)

        cartao_query = select(CartaoCreditoModel).where(
            CartaoCreditoModel.id_cartao_credito == fatura.id_cartao_credito,
        )
        cartao_result = await session.execute(cartao_query)
        cartao = cartao_result.scalars().one_or_none()

        if cartao:
            cartao.limite_disponivel += Decimal(movimentacao.valor)

    await session.delete(movimentacao)



@router.get("/orcamento-mensal", status_code=status.HTTP_200_OK)
async def calcular_orcamento_mensal(
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    hoje = date.today()
    primeiro_dia = hoje.replace(day=1)
    ultimo_dia = hoje.replace(day=monthrange(hoje.year, hoje.month)[1])
    
    async with db as session:
        query_orcamento = select(func.sum(CategoriaModel.valor_categoria).label("orcamento_total")).filter(
            CategoriaModel.modelo_categoria == TipoMovimentacao.DESPESA,
            CategoriaModel.id_usuario == usuario_logado.id_usuario
        )
        orcamento_total_result = await session.execute(query_orcamento)
        orcamento_total = orcamento_total_result.scalar() or Decimal(0)
        
        query_categorias = select(
            CategoriaModel.id_categoria,
            CategoriaModel.valor_categoria,
            CategoriaModel.nome,
            CategoriaModel.nome_icone
        ).filter(
            CategoriaModel.modelo_categoria == TipoMovimentacao.DESPESA,
            CategoriaModel.id_usuario == usuario_logado.id_usuario
        )
        categorias_result = await session.execute(query_categorias)
        categorias = categorias_result.fetchall()
        
        query_despesas_total = select(
            CategoriaModel.id_categoria,
            func.coalesce(func.sum(DivideModel.valor), Decimal(0)).label("valor_despesa")
        ).join(
            MovimentacaoModel, MovimentacaoModel.id_categoria == CategoriaModel.id_categoria, isouter=True
        ).join(
            DivideModel, MovimentacaoModel.id_movimentacao == DivideModel.id_movimentacao, isouter=True
        ).join(
            ParenteModel, DivideModel.id_parente == ParenteModel.id_parente, isouter=True
        ).filter(
            MovimentacaoModel.tipoMovimentacao == TipoMovimentacao.DESPESA,
            MovimentacaoModel.data_pagamento >= primeiro_dia,
            MovimentacaoModel.data_pagamento <= ultimo_dia,
            ParenteModel.nome == usuario_logado.nome_completo,
            ParenteModel.id_usuario == usuario_logado.id_usuario
            

        ).group_by(CategoriaModel.id_categoria)
        
        despesas_result = await session.execute(query_despesas_total)
        despesas = {row.id_categoria: row.valor_despesa for row in despesas_result.fetchall()}
        
        resultado = []
        soma_despesas_totais = Decimal(0)
        
        for categoria in categorias:
            valor_despesa = despesas.get(categoria.id_categoria, Decimal(0))
            soma_despesas_totais += valor_despesa
            resultado.append({
                "nome_categoria": categoria.nome,
                "nome_icone_categoria": categoria.nome_icone,
                "valor_categoria": categoria.valor_categoria,
                "valor_despesa": valor_despesa
            })
        
        return {
            "orcamento_total": str(orcamento_total),
            "despesas_totais": str(soma_despesas_totais),
            "detalhes_categorias": resultado
        }


@router.get("/gastos-receitas-por-categoria", status_code=status.HTTP_200_OK)
async def calcular_gastos_receitas_por_categoria(
    tipo_receita: bool,  
    somente_usuario: bool,  
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    hoje = date.today()
    primeiro_dia = hoje.replace(day=1)
    ultimo_dia = hoje.replace(day=monthrange(hoje.year, hoje.month)[1])
    
    print("primeiro dia", primeiro_dia)

    async with db as session:
        categorias_query = select(
            CategoriaModel.id_categoria,
            CategoriaModel.nome.label("nome_categoria"),
            CategoriaModel.nome_icone.label("nome_icone_categoria")
        ).filter(
            CategoriaModel.modelo_categoria == ('DESPESA' if not tipo_receita else 'RECEITA'),
            CategoriaModel.id_usuario == usuario_logado.id_usuario
        )

        categorias_result = await session.execute(categorias_query)
        categorias = categorias_result.fetchall()

        query_soma = select(
            CategoriaModel.id_categoria,
            func.coalesce(func.sum(DivideModel.valor), Decimal(0)).label("valor_categoria")
        ).join(
            MovimentacaoModel, MovimentacaoModel.id_categoria == CategoriaModel.id_categoria, isouter=True
        ).join(
            DivideModel, MovimentacaoModel.id_movimentacao == DivideModel.id_movimentacao, isouter=True
        ).join(
            ParenteModel, DivideModel.id_parente == ParenteModel.id_parente, isouter=True
        ).filter(
            MovimentacaoModel.data_pagamento >= primeiro_dia,
            MovimentacaoModel.data_pagamento <= ultimo_dia,
            MovimentacaoModel.tipoMovimentacao == ('RECEITA' if tipo_receita else 'DESPESA')
        )

        if somente_usuario:
            query_soma = query_soma.filter(
                ParenteModel.nome == usuario_logado.nome_completo,
                ParenteModel.id_usuario == usuario_logado.id_usuario

            )
        else:
            query_soma = query_soma.filter(
                ParenteModel.id_usuario == usuario_logado.id_usuario
            )

        query_soma = query_soma.group_by(CategoriaModel.id_categoria)

        soma_result = await session.execute(query_soma)
        soma_despesas_receitas = soma_result.fetchall()

        categoria_despesas_receitas = {categoria.id_categoria: {
            "valor": Decimal(0),  
            "nome_categoria": categoria.nome_categoria,
            "nome_icone_categoria": categoria.nome_icone_categoria
        } for categoria in categorias}

        for row in soma_despesas_receitas:
            categoria_id = row.id_categoria
            # Verifica se a chave existe, se não, inicializa com um dicionário vazio
            if categoria_id not in categoria_despesas_receitas:
                categoria_despesas_receitas[categoria_id] = {"valor": 0}
                
            categoria_despesas_receitas[categoria_id]["valor"] = row.valor_categoria


        valor_total = sum(categoria["valor"] for categoria in categoria_despesas_receitas.values())
        
        

        categorias_resposta = [
            {
                "valor": categoria["valor"],
                "nome_categoria": categoria["nome_categoria"],
                "nome_icone_categoria": categoria["nome_icone_categoria"]
            }
            for categoria in categoria_despesas_receitas.values()
        ]

    return {
        "valor_total": valor_total,
        "valor_categoria": categorias_resposta
    }

@router.get("/economia-meses-anteriores", status_code=status.HTTP_200_OK)
async def economia_meses_anteriores(
    somente_usuario: bool,  
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    hoje = date.today()
    ano_atual = hoje.year
    mes_atual = hoje.month

    print(f"[DEBUG] Ano atual: {ano_atual}, Mês atual: {mes_atual}")

    async with db as session:
        despesas_por_mes = []

        for mes_offset in range(0, 12):
            mes = mes_atual - mes_offset
            ano = ano_atual

            
            if mes <= 0:
                mes = 12 + mes
                ano -= 1

            primeiro_dia_mes = datetime(ano, mes, 1)
            ultimo_dia_mes = datetime(ano, mes, monthrange(ano, mes)[1])  

           
            query_despesas = select(
                func.coalesce(func.sum(DivideModel.valor), Decimal(0)).label("valor_despesa"),
                func.extract('month', MovimentacaoModel.data_pagamento).label("mes"),
                func.extract('year', MovimentacaoModel.data_pagamento).label("ano")
            ).join(
                MovimentacaoModel, MovimentacaoModel.id_movimentacao == DivideModel.id_movimentacao
            ).join(
                ParenteModel, DivideModel.id_parente == ParenteModel.id_parente, isouter=True
            ).filter(
                MovimentacaoModel.tipoMovimentacao == 'DESPESA',
                MovimentacaoModel.data_pagamento >= primeiro_dia_mes,
                MovimentacaoModel.data_pagamento <= ultimo_dia_mes
            )

            if somente_usuario:
                query_despesas = query_despesas.filter(
                    ParenteModel.nome == usuario_logado.nome_completo,
                    ParenteModel.id_usuario == usuario_logado.id_usuario

                )
            else:
                query_despesas = query_despesas.filter(ParenteModel.id_usuario == usuario_logado.id_usuario)

            query_despesas = query_despesas.group_by(func.extract('month', MovimentacaoModel.data_pagamento), 
                                                     func.extract('year', MovimentacaoModel.data_pagamento))

            resultado_despesas = await session.execute(query_despesas)
            despesas_mes = resultado_despesas.fetchall()

            if not despesas_mes:
                despesas_por_mes.append({
                    "mes": mes,
                    "ano": ano,
                    "valor_despesa": "0"  
                })
            else:
                for resultado in despesas_mes:
                    despesas_por_mes.append({
                        "mes": int(resultado.mes),  
                        "ano": int(resultado.ano), 
                        "valor_despesa": str(resultado.valor_despesa)
                    })

    if len(despesas_por_mes) < 12:
        for i in range(len(despesas_por_mes), 12):
            mes_faltando = mes_atual - (i - len(despesas_por_mes))
            ano_faltando = ano_atual

            if mes_faltando <= 0:
                mes_faltando = 12 + mes_faltando
                ano_faltando -= 1

            despesas_por_mes.append({
                "mes": mes_faltando,
                "ano": ano_faltando,
                "valor_despesa": "0" 
            })

    return despesas_por_mes
