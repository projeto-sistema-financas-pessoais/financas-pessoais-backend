import unittest
import pytest
import traceback
from httpx import AsyncClient, ASGITransport
from fastapi import status, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from unittest.mock import AsyncMock, patch

from main import app
from tests.config import getValidToken
from decouple import config


class TestPostUsuario(unittest.IsolatedAsyncioTestCase):


    @classmethod
    def setUpClass(cls):
        # Configura o patch do get_session compartilhado para todos os testes
        cls.mock_get_session = AsyncMock()
        cls.session_patch = patch(
            "api.v1.endpoints.usuario.get_session", new=AsyncMock(return_value=cls.mock_get_session)
        )
        cls.session_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.session_patch.stop()
            
    async def asyncSetUp(self):
        # Configuração antes de cada teste
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="https://testserver")
        self.token = getValidToken()


    async def asyncTearDown(self):
        # Limpeza após cada teste
        await self.client.aclose()


    @pytest.mark.asyncio
    @patch("api.v1.endpoints.usuario.handle_db_exceptions")
    async def test_post_usuario_duplicado(self, mock_handle_exceptions):
        # Configurar mock da sessão
        mock_session = AsyncMock()
        self.mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Simular IntegrityError para email duplicado
        mock_session.commit.side_effect = IntegrityError(
            statement=None, 
            params=None, 
            orig=Exception("Violação de constraint de email único")
        )
        
        # Configurar mock de handle_db_exceptions para lançar HTTPException esperada
        mock_handle_exceptions.side_effect = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Erro de integridade no banco de dados: Violação de constraint de email único"
        )
        
        # Simula os dados recebidos
        usuario_data = {
            "nome_completo": "Usuário Teste",
            "data_nascimento": "1990-01-01",
            "email": "teste5@example.com",
            "senha": config("TOKEN_TESTE")
        }
        
        # Fazer a requisição
        response = await self.client.post("/api/v1/usuarios/cadastro", json=usuario_data)
        
        # Verificações
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        


    @pytest.mark.asyncio
    @patch("api.v1.endpoints.usuario.handle_db_exceptions")
    async def test_post_usuario_erro_generico(self, mock_handle_exceptions):

        # Configurar mock da sessão
        mock_session = AsyncMock()
        self.mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Simular erro genérico do SQLAlchemy
        mock_session.commit.side_effect = SQLAlchemyError("Erro genérico de banco de dados")
        
        # Configurar mock de handle_db_exceptions para lançar HTTPException esperada
        mock_handle_exceptions.side_effect = HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro no banco de dados, tente novamente mais tarde."
        )
        
        # Simula os dados recebidos
        usuario_data = {
            "nome_completo": "Usuário Teste",
            "data_nascimento": "1990-01-01",
            "email": "teste@example.com",
            "senha": config("TOKEN_TESTE")
        }
        
        # Fazer a requisição
        response = await self.client.post("/api/v1/usuarios/cadastro", json=usuario_data)
        
        # Verificações
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @pytest.mark.asyncio
    @patch("api.v1.endpoints.usuario.auth")
    async def test_post_usuario_login(self, mock_auth):

        mock_session = AsyncMock()
        self.mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Simula o sucesso da autenticação
        mock_auth.return_value = AsyncMock(id_usuario=1, nome_completo="Usuário Teste")
        
        # Simula os dados de login
        login_data = {
            "username": "teste@example.com",
            "password":  config("TOKEN_TESTE")

        }
        
        # Fazer a requisição de login
        response = await self.client.post("/api/v1/usuarios/login", data=login_data)
        
        # Verificações
        self.assertIn("access_token", response.json())
        self.assertEqual(response.json()["name"], "Usuário Teste")
            # Imprimir o access_token
        # access_token = response.json().get("access_token")
        access_token = response.json().get("access_token")

        print("Access Token:", access_token)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
    

    @pytest.mark.asyncio
    @pytest.mark.order(1)
    @patch("api.v1.endpoints.usuario.get_current_user", new_callable=AsyncMock)
    async def test_get_usuario_success(self, mock_get_current_user):
        mock_session = AsyncMock()
        self.mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_usuario = AsyncMock(
            nome_completo="Usuário Teste",
            data_nascimento="1990-01-01"
        )
        mock_get_current_user.return_value = mock_usuario
        
        headers = {"Authorization": f"Bearer { self.token}"}

        response = await self.client.get("/api/v1/usuarios/listar_usuario", headers=headers)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        

