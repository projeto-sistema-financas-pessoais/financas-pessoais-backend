from decimal import Decimal
from fastapi import HTTPException
import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

from sqlalchemy import Result
from api.v1.endpoints.movimentacao import (
    ajustar_saldo_conta,
    TipoMovimentacao,
    ajustar_data_pagamento,
    MovimentacaoSchemaReceitaDespesa,
    CondicaoPagamento,
    TipoRecorrencia,
    calcular_parcelas_precisas,
    create_movimentacao_despesa,
    criar_repeticao,
    ajustar_limite_fatura_gastos,
    processar_delecao_movimentacao,
    validar_categoria,
    validar_conta
)
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from models.cartao_credito_model import CartaoCreditoModel
from models.conta_model import ContaModel
from models.enums import FormaPagamento
from sqlalchemy.ext.asyncio import AsyncSession

from models.fatura_model import FaturaModel
from models.movimentacao_model import MovimentacaoModel
from models.repeticao_model import RepeticaoModel
from models.usuario_model import UsuarioModel
from schemas.movimentacao_schema import MovimentacaoSchemaTransferencia


class TestAjustarSaldoConta:
    def test_despesa_consolidada(self):
        # Arrange
        conta = MagicMock()
        conta.saldo = 100.0
        
        movimentacao = MagicMock()
        movimentacao.tipoMovimentacao = TipoMovimentacao.DESPESA
        movimentacao.valor = 50.0

        consolidado = True

        # Act
        ajustar_saldo_conta(conta, movimentacao, consolidado)

        # Assert
        tolerance = 1e-9
        assert abs(conta.saldo - 50.0) < tolerance, f"Expected saldo to be 50.0, but got {conta.saldo}"


    def test_despesa_nao_consolidada(self):
        # Arrange
        conta = MagicMock()
        conta.saldo = 100.0

        movimentacao = MagicMock()
        movimentacao.tipoMovimentacao = TipoMovimentacao.DESPESA
        movimentacao.valor = 50.0

        consolidado = False

        # Act
        ajustar_saldo_conta(conta, movimentacao, consolidado)

        # Assert
        tolerance = 1e-9 
        assert abs(conta.saldo - 150.0) < tolerance, f"Expected saldo to be 50.0, but got {conta.saldo}"

    def test_receita_consolidada(self):
        # Arrange
        conta = MagicMock()
        conta.saldo = 100.0

        movimentacao = MagicMock()
        movimentacao.tipoMovimentacao = TipoMovimentacao.RECEITA
        movimentacao.valor = 50.0

        consolidado = True

        # Act
        ajustar_saldo_conta(conta, movimentacao, consolidado)

        # Assert
        tolerance = 1e-9 
        assert abs(conta.saldo - 150.0) < tolerance, f"Expected saldo to be 50.0, but got {conta.saldo}"

    def test_receita_nao_consolidada(self):
        # Arrange
        conta = MagicMock()
        conta.saldo = 100.0

        movimentacao = MagicMock()
        movimentacao.tipoMovimentacao = TipoMovimentacao.RECEITA
        movimentacao.valor = 50.0

        consolidado = False

        # Act
        ajustar_saldo_conta(conta, movimentacao, consolidado)

        # Assert
        tolerance = 1e-9 
        assert abs(conta.saldo - 50.0) < tolerance, f"Expected saldo to be 50.0, but got {conta.saldo}"


# Valores padrão
default_data = {
    "valor": Decimal('100.00'),
    "id_categoria": 1,
    "id_conta": 1,
    "condicao_pagamento": CondicaoPagamento.RECORRENTE,
    "tipo_recorrencia": TipoRecorrencia.ANUAL,
    "datatime": datetime(2024, 11, 23, 12, 0),
    "data_pagamento": date(2024, 11, 23),
    "consolidado": True,
    "forma_pagamento": FormaPagamento.CREDITO,
    "id_financeiro": 12345,
    "quantidade_parcelas": 1,
    "divide_parente": []
}

# Função para criar o objeto Movimentacao com valores padrão
def criar_movimentacao(**kwargs):
    return MovimentacaoSchemaReceitaDespesa(
        **{**default_data, **kwargs}
    )

class TestAjustarDataPagamento:
    
    # Teste para uma movimentação com condição de pagamento RECORRENTE e tipo de recorrência ANUAL
    def test_ajustar_data_pagamento_anual(self):
        movimentacao = criar_movimentacao(tipo_recorrencia=TipoRecorrencia.ANUAL)
        data_pagamento = date(2024, 11, 23)
        nova_data = ajustar_data_pagamento(movimentacao, data_pagamento)
        assert nova_data == date(2025, 11, 23)

    # Teste para uma movimentação com condição de pagamento RECORRENTE e tipo de recorrência QUINZENAL
    def test_ajustar_data_pagamento_quinzenal(self):
        movimentacao = criar_movimentacao(tipo_recorrencia=TipoRecorrencia.QUINZENAL)
        data_pagamento = date(2024, 11, 23)
        nova_data = ajustar_data_pagamento(movimentacao, data_pagamento)
        assert nova_data == date(2024, 12, 8)

    # Teste para uma movimentação com condição de pagamento RECORRENTE e tipo de recorrência SEMANAL
    def test_ajustar_data_pagamento_semanal(self):
        movimentacao = criar_movimentacao(tipo_recorrencia=TipoRecorrencia.SEMANAL)
        data_pagamento = date(2024, 11, 23)
        nova_data = ajustar_data_pagamento(movimentacao, data_pagamento)
        assert nova_data == date(2024, 11, 30)

    # Teste para uma movimentação com condição de pagamento RECORRENTE e tipo de recorrência MENSAL
    def test_ajustar_data_pagamento_mensal(self):
        movimentacao = criar_movimentacao(tipo_recorrencia=TipoRecorrencia.MENSAL)
        data_pagamento = date(2024, 11, 23)
        nova_data = ajustar_data_pagamento(movimentacao, data_pagamento)
        assert nova_data == date(2024, 12, 23)

    # Teste para uma movimentação com condição de pagamento NÃO RECORRENTE
    def test_ajustar_data_pagamento_nao_recorrente(self):
        movimentacao = criar_movimentacao(condicao_pagamento=CondicaoPagamento.PARCELADO, tipo_recorrencia= TipoRecorrencia.MENSAL)
        data_pagamento = date(2024, 11, 23)
        nova_data = ajustar_data_pagamento(movimentacao, data_pagamento)
        assert nova_data == date(2024, 12, 23)
        

@pytest.fixture
def db_mock_repeticao():
    db = MagicMock(AsyncSession)
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    
    # Configurando o mock de refresh para modificar a instância corretamente
    async def mock_refresh(instance):
        if isinstance(instance, RepeticaoModel):
            instance.id_repeticao = 1
    
    db.refresh.side_effect = mock_refresh
    return db

@pytest.fixture
def usuario_logado():
    return UsuarioModel(id_usuario=1)

@pytest.mark.asyncio
class TestCriarRepeticao:

    async def test_criar_repeticao_recorrente(self, db_mock_repeticao, usuario_logado):
        movimentacao = criar_movimentacao(
            condicao_pagamento=CondicaoPagamento.RECORRENTE,
            tipo_recorrencia=TipoRecorrencia.ANUAL
        )

        resultado = await criar_repeticao(movimentacao, usuario_logado, db_mock_repeticao)

        assert movimentacao.quantidade_parcelas == 4
        db_mock_repeticao.add.assert_called_once()
        
        called_obj = db_mock_repeticao.add.call_args[0][0]
        assert isinstance(called_obj, RepeticaoModel)
        
        assert resultado == 1

        repeticao = db_mock_repeticao.add.call_args[0][0]
        assert repeticao.quantidade_parcelas == 4
        assert repeticao.tipo_recorrencia == TipoRecorrencia.ANUAL
        assert repeticao.valor_total == movimentacao.valor
        assert repeticao.id_usuario == usuario_logado.id_usuario
        
    async def test_criar_repeticao_recorrente_nao_anual(self, db_mock_repeticao, usuario_logado):
        movimentacao = criar_movimentacao(condicao_pagamento=CondicaoPagamento.RECORRENTE, tipo_recorrencia=TipoRecorrencia.MENSAL)

        db_mock_repeticao.add = MagicMock()
        db_mock_repeticao.flush = AsyncMock()
        db_mock_repeticao.refresh = AsyncMock()

        result = await criar_repeticao(movimentacao, usuario_logado, db_mock_repeticao)

        assert movimentacao.quantidade_parcelas == 24

    async def test_criar_repeticao_parcelado(self, db_mock_repeticao, usuario_logado):
        movimentacao = criar_movimentacao(condicao_pagamento=CondicaoPagamento.PARCELADO, tipo_recorrencia=TipoRecorrencia.MENSAL)

        db_mock_repeticao.add = MagicMock()
        db_mock_repeticao.flush = AsyncMock()
        db_mock_repeticao.refresh = AsyncMock()

        result= await criar_repeticao(movimentacao, usuario_logado, db_mock_repeticao)

        assert movimentacao.quantidade_parcelas == 1


    async def test_criar_repeticao_sem_repeticao(self, db_mock_repeticao, usuario_logado):
        movimentacao = criar_movimentacao(condicao_pagamento=CondicaoPagamento.A_VISTA, tipo_recorrencia=TipoRecorrencia.MENSAL)

        db_mock_repeticao.add = MagicMock()
        db_mock_repeticao.flush = AsyncMock()
        db_mock_repeticao.refresh = AsyncMock()

        resultado = await criar_repeticao(movimentacao, usuario_logado, db_mock_repeticao)

        assert resultado is None
        db_mock_repeticao.add.assert_not_called()  


class TestAjustarLimiteFaturaGastos:

    @pytest.fixture
    def cartao_credito(self):
        cartao_credito = MagicMock(spec=CartaoCreditoModel)
        cartao_credito.limite_disponivel = Decimal('1000.00')
        return cartao_credito

    @pytest.fixture
    def fatura(self):
        fatura = MagicMock(spec=FaturaModel)
        fatura.fatura_gastos = Decimal('200.00')
        return fatura

    @pytest.fixture
    def movimentacao(self):
        movimentacao = MagicMock(spec=MovimentacaoModel)
        movimentacao.valor = Decimal('150.00')
        movimentacao.participa_limite_fatura_gastos = None
        return movimentacao

    def test_ajustar_limite_fatura_gastos_false(self, cartao_credito, fatura, movimentacao):
        ajustar_limite_fatura_gastos(cartao_credito, fatura, movimentacao, False)

        assert cartao_credito.limite_disponivel == Decimal('1150.00')  # 1000 + 150
        assert fatura.fatura_gastos == Decimal('50.00')  # 200 - 150
        assert movimentacao.participa_limite_fatura_gastos is False

    def test_ajustar_limite_fatura_gastos_true(self, cartao_credito, fatura, movimentacao):
        ajustar_limite_fatura_gastos(cartao_credito, fatura, movimentacao, True)

        assert cartao_credito.limite_disponivel == Decimal('850.00')  # 1000 - 150
        assert fatura.fatura_gastos == Decimal('350.00')  # 200 + 150
        assert movimentacao.participa_limite_fatura_gastos is True
        


@pytest.fixture
def session_mock():
    session = MagicMock(AsyncSession)
    session.execute = AsyncMock()
    session.delete = AsyncMock()
    session.get = AsyncMock()
    session.add = MagicMock()
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.one_or_none.return_value = None
    session.execute.return_value = mock_result
    
    return session

@pytest.mark.asyncio
class TestProcessarDelecaoMovimentacao:
    async def test_delecao_com_fatura_despesa(self, session_mock, usuario_logado):
        movimentacao = MovimentacaoModel(
            id_movimentacao=1,
            consolidado=True,
            id_conta=1,
            tipoMovimentacao=TipoMovimentacao.DESPESA,
            valor=Decimal('100.00'),
            participa_limite_fatura_gastos=True,
            id_fatura=1
        )

        conta = ContaModel(id_conta=1, saldo=Decimal('500.00'))
        fatura = FaturaModel(
            id_fatura=1,
            fatura_gastos=Decimal('200.00'),
            id_cartao_credito=1
        )
        cartao = CartaoCreditoModel(
            id_cartao_credito=1,
            limite_disponivel=Decimal('1000.00')
        )

        mock_results = []
        
        conta_result = MagicMock()
        conta_result.scalars.return_value.one_or_none.return_value = conta
        mock_results.append(conta_result)
        
        fatura_result = MagicMock()
        fatura_result.scalars.return_value.one_or_none.return_value = fatura
        mock_results.append(fatura_result)
        
        cartao_result = MagicMock()
        cartao_result.scalars.return_value.one_or_none.return_value = cartao
        mock_results.append(cartao_result)
        
        session_mock.execute.side_effect = mock_results

        await processar_delecao_movimentacao(movimentacao, session_mock, usuario_logado)

        assert conta.saldo == Decimal('600.00')  # 500 + 100
        assert fatura.fatura_gastos == Decimal('100.00')  # 200 - 100
        assert cartao.limite_disponivel == Decimal('1100.00')  # 1000 + 100
        
        session_mock.delete.assert_called_once_with(movimentacao)
        
    async def test_delecao_com_receita(self, session_mock, usuario_logado):
        movimentacao = MovimentacaoModel(
            id_movimentacao=2,
            consolidado=True,
            id_conta=1,
            tipoMovimentacao=TipoMovimentacao.RECEITA,
            valor=Decimal('150.00')
        )

        conta = ContaModel(id_conta=1, saldo=Decimal('500.00'))

        conta_result = MagicMock()
        conta_result.scalars.return_value.one_or_none.return_value = conta
        session_mock.execute.return_value = conta_result

        await processar_delecao_movimentacao(movimentacao, session_mock, usuario_logado)

        assert conta.saldo == Decimal('350.00')  # 500 - 150
        
        session_mock.delete.assert_called_once_with(movimentacao)

    async def test_delecao_com_transferencia(self, session_mock, usuario_logado):
        movimentacao = MovimentacaoModel(
            id_movimentacao=3,
            consolidado=True,
            id_conta=1,
            id_conta_destino=2,
            tipoMovimentacao=TipoMovimentacao.TRANSFERENCIA,
            valor=Decimal('200.00')
        )

        conta_origem = ContaModel(id_conta=1, saldo=Decimal('500.00'))
        conta_destino = ContaModel(id_conta=2, saldo=Decimal('1000.00'))

        conta_origem_result = MagicMock()
        conta_origem_result.scalars.return_value.one_or_none.return_value = conta_origem

        session_mock.get.return_value = conta_destino

        session_mock.execute.return_value = conta_origem_result

        await processar_delecao_movimentacao(movimentacao, session_mock, usuario_logado)

        assert conta_origem.saldo == Decimal('700.00')  # 500 + 200
        assert conta_destino.saldo == Decimal('800.00')  # 1000 - 200


class TestValidacoes:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.fixture
    def mock_usuario_logado(self):
        usuario = Mock()
        usuario.id_usuario = 1
        usuario.nome_completo = "Usuário Teste"
        return usuario

    @pytest.mark.asyncio
    async def test_validar_conta_erro_banco(self, mock_session, mock_usuario_logado):
        """Testa erro na consulta ao banco de dados para conta"""
        mock_session.execute.side_effect = Exception("Erro de banco de dados")

        with pytest.raises(Exception) as exc_info:
            await validar_conta(
                session=mock_session,
                usuario_logado=mock_usuario_logado,
                id_conta=1
            )

        assert "Erro de banco de dados" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validar_categoria_erro_banco(self, mock_session, mock_usuario_logado):
        """Testa erro na consulta ao banco de dados para categoria"""
        mock_session.execute.side_effect = Exception("Erro de banco de dados")

        with pytest.raises(Exception) as exc_info:
            await validar_categoria(
                session=mock_session,
                usuario_logado=mock_usuario_logado,
                id_categoria=1
            )

        assert "Erro de banco de dados" in str(exc_info.value)
        

@pytest.mark.asyncio
class TestCreateDespesa:

    async def test_create_movimentacao_despesa(self):
        mock_session = AsyncMock(spec=AsyncSession)
        mock_usuario = UsuarioModel(id_usuario=1)
        
        movimentacao_data = MovimentacaoSchemaReceitaDespesa(
            valor=100.00,
            descricao="Teste de Despesa",
            datatime=datetime.now(),
            data_pagamento=date.today(),
            forma_pagamento=FormaPagamento.DEBITO,
            condicao_pagamento=CondicaoPagamento.A_VISTA,
            id_categoria=1,
            id_conta=1,
            id_financeiro=1,
            quantidade_parcelas=1,
            consolidado=True,
            divide_parente = [
                {"id_parente": 1, "valor_parente": 100.00}
            ],
                    tipo_recorrencia = TipoRecorrencia.MENSAL

        )

        with patch('api.v1.endpoints.movimentacao.validar_categoria', return_value=AsyncMock()) as mock_validar_categoria, \
            patch('api.v1.endpoints.movimentacao.validar_conta', return_value=AsyncMock()) as mock_validar_conta, \
            patch('api.v1.endpoints.movimentacao.criar_repeticao', return_value=1) as mock_criar_repeticao, \
            patch('api.v1.endpoints.movimentacao.get_or_create_fatura', return_value=(AsyncMock(), AsyncMock())) as mock_get_fatura:
            
            result = await create_movimentacao_despesa(
                movimentacao=movimentacao_data, 
                db=mock_session, 
                usuario_logado=mock_usuario
            )

            assert result == {"message": "Despesa cadastrada com sucesso."}
            mock_session.commit.assert_called_once()
            mock_validar_categoria.assert_called_once()
            mock_validar_conta.assert_called_once()
            mock_criar_repeticao.assert_called_once()

    async def test_create_movimentacao_despesa_parcelada(self):
        mock_session = AsyncMock(spec=AsyncSession)
        mock_usuario = UsuarioModel(id_usuario=1)
        
        movimentacao_data = MovimentacaoSchemaReceitaDespesa(
            valor=100.00,
            descricao="Despesa Parcelada",
            datatime=datetime.now(),
            data_pagamento=date.today(),
            forma_pagamento=FormaPagamento.CREDITO,
            condicao_pagamento=CondicaoPagamento.PARCELADO,
            id_categoria=1,
            id_conta=1,
            id_financeiro=1,
            quantidade_parcelas=3,
            consolidado=False,
            divide_parente = [
                {"id_parente": 1, "valor_parente": 100.00}
            ],

            tipo_recorrencia = TipoRecorrencia.MENSAL
            
        )

        with patch('api.v1.endpoints.movimentacao.validar_categoria', return_value=AsyncMock()) as mock_validar_categoria, \
            patch('api.v1.endpoints.movimentacao.validar_conta', return_value=AsyncMock()) as mock_validar_conta, \
            patch('api.v1.endpoints.movimentacao.criar_repeticao', return_value=1) as mock_criar_repeticao, \
            patch('api.v1.endpoints.movimentacao.get_or_create_fatura', return_value=(AsyncMock(), AsyncMock())) as mock_get_fatura:
            
            result = await create_movimentacao_despesa(
                movimentacao=movimentacao_data, 
                db=mock_session, 
                usuario_logado=mock_usuario
            )

            assert result == {"message": "Despesa cadastrada com sucesso."}
            mock_session.commit.assert_called_once()
            
    
import unittest
from decimal import Decimal

class TestCalcularParcelasPrecisas(unittest.TestCase):

    def test_calcular_parcelas_precisas(self):
        valor_total = 100.00
        quantidade_parcelas = 3
        valor_primeira_parcela, valor_parcela = calcular_parcelas_precisas(valor_total, quantidade_parcelas)
        
        valor_esperado_primeira_parcela = Decimal('33.34')
        valor_esperado_parcela = Decimal('33.33')

        self.assertEqual(valor_primeira_parcela, valor_esperado_primeira_parcela)
        self.assertEqual(valor_parcela, valor_esperado_parcela)

    def test_calcular_parcelas_precisas_valores_decimal(self):
        valor_total = Decimal('100.55')
        quantidade_parcelas = 4
        valor_primeira_parcela, valor_parcela = calcular_parcelas_precisas(valor_total, quantidade_parcelas)
        
        valor_esperado_primeira_parcela = Decimal('25.13')
        valor_esperado_parcela = Decimal('25.14')

        self.assertEqual(valor_primeira_parcela, valor_esperado_primeira_parcela)
        self.assertEqual(valor_parcela, valor_esperado_parcela)

    def test_calcular_parcelas_precisas_um_real(self):
        valor_total = Decimal('1.00')
        quantidade_parcelas = 2
        valor_primeira_parcela, valor_parcela = calcular_parcelas_precisas(valor_total, quantidade_parcelas)
        
        valor_esperado_primeira_parcela = Decimal('0.50')
        valor_esperado_parcela = Decimal('0.50')

        self.assertEqual(valor_primeira_parcela, valor_esperado_primeira_parcela)
        self.assertEqual(valor_parcela, valor_esperado_parcela)

if __name__ == '__main__':
    unittest.main()
