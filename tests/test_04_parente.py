import base64
import api.v1.endpoints
import unittest
from unittest import mock
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import smtplib
import io
import pdfkit

from api.v1.endpoints.parente import criar_email_data, send_email

class TestSendEmail(unittest.TestCase):
    @mock.patch('api.v1.endpoints.parente.smtplib.SMTP')
    @mock.patch('api.v1.endpoints.parente.config')
    @mock.patch('api.v1.endpoints.parente.pdfkit.from_string')
    def test_send_email_success(self, mock_pdfkit, mock_config, mock_smtp):
        # Configuração do mock
        mock_config.side_effect = lambda x: 'test_value' if x in ['EMAIL_ADDRESS', 'EMAIL_PASSWORD'] else None

        mock_server = mock.Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server  # Configura o __enter__ do mock para retornar o mock_server

        # Simulando a criação de um PDF
        mock_pdfkit.return_value = b'fake_pdf_data'

        email_data = {
            'email_subject': 'Test Subject',
            'email_body': '<p>Test Body</p>'
        }
        user_email = 'test_user@example.com'

        # Chama a função
        send_email(email_data, user_email)

        # Verifique se a função SMTP foi chamada corretamente
        mock_smtp.assert_called_once_with("smtp.gmail.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('test_value', 'test_value')
        mock_server.send_message.assert_called_once()

        # Verifique se o PDF foi anexado corretamente
        attachment = mock_server.send_message.call_args[0][0].get_payload()[1]
        attachment_data = attachment.get_payload()
        decoded_data = base64.b64decode(attachment_data)  # Decodifica o conteúdo base64

        self.assertEqual(decoded_data, b'fake_pdf_data')  # Compara com o valor esperado


    @mock.patch('api.v1.endpoints.parente.smtplib.SMTP')
    @mock.patch('api.v1.endpoints.parente.config')
    def test_send_email_exception(self, mock_config, mock_smtp):
        # Configuração do mock para lançar uma exceção
        mock_config.side_effect = lambda x: 'test_value' if x in ['EMAIL_ADDRESS', 'EMAIL_PASSWORD'] else None
        mock_server = mock.Mock()
        mock_smtp.return_value = mock_server
        mock_server.send_message.side_effect = Exception("SMTP error")

        email_data = {
            'email_subject': 'Test Subject',
            'email_body': '<p>Test Body</p>'
        }
        user_email = 'test_user@example.com'

        # Verifique se a exceção é lançada
        with self.assertRaises(Exception) as context:
            send_email(email_data, user_email)
        
        self.assertTrue('Error occurred while sending email' in str(context.exception))


class TestCriarEmailData(unittest.TestCase):

    def setUp(self):
        # Criando objetos simulados para 'parente', 'usuario_logado', 'cobranca' e 'movimentacoes_data'
        self.parente = type('Parente', (object,), {'nome': 'Maria'})()
        self.usuario_logado = type('Usuario', (object,), {'nome_completo': 'Maria'})()
        self.cobranca = type('Cobranca', (object,), {'mes': 11, 'ano': 2024})()
        self.movimentacoes_data = {
            'movimentacoes_nao_consolidadas': [
                {'descricao': 'Compra de supermercado', 'data_pagamento': '2024-11-10', 'valor': 150.50},
                {'descricao': 'Pagamento de energia', 'data_pagamento': '2024-11-15', 'valor': 80.75}
            ],
            'fatura_geral': {
                'total_geral_movimentacoes': 231.25,
                'total_movimentacoes': 231.25
            }
        }

    def test_criar_email_data_parente_e_usuario_logado_mesmo_nome(self):
        resultado = criar_email_data(self.parente, self.usuario_logado, self.cobranca, self.movimentacoes_data)
        
        self.assertEqual(resultado['email_subject'], "Lembrete de Movimentações não Consolidadas")
        self.assertIn('Olá, Maria!', resultado['email_body'])
        self.assertIn('Seguem as informações referentes ao mês 11/2024:', resultado['email_body'])
        self.assertIn('Por favor, acesse o sistema para mais informações.', resultado['email_body'])

    def test_criar_email_data_parente_e_usuario_logado_nomes_diferentes(self):
        self.usuario_logado.nome_completo = 'João'
        
        resultado = criar_email_data(self.parente, self.usuario_logado, self.cobranca, self.movimentacoes_data)
        
        self.assertEqual(resultado['email_subject'], "Cobrança de Movimentações não Consolidadas")
        self.assertIn('Olá, Maria,', resultado['email_body'])
        self.assertIn('Seguem as informações referentes às suas movimentações não consolidadas com João no mês 11/2024:', resultado['email_body'])
        self.assertIn('Por favor, acesse o sistema para mais informações.', resultado['email_body'])

if __name__ == '__main__':
    unittest.main()

    
    