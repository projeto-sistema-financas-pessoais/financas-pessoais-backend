import unittest
from unittest.mock import MagicMock, patch
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from api.v1.endpoints.rotina import processar_usuarios_em_atraso, send_email

class TestSendEmail(unittest.TestCase):
    @patch("api.v1.endpoints.rotina.smtplib.SMTP")
    @patch("api.v1.endpoints.rotina.config")
    @patch("api.v1.endpoints.rotina.pdfkit.from_string")
    def test_send_email(self, mock_pdfkit, mock_config, mock_smtp):
        mock_config.side_effect = lambda key: "dummy_value" if key in ["EMAIL_ADDRESS", "EMAIL_PASSWORD"] else None

        mock_pdfkit.return_value = b"PDF content"

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        email_data = {
            "email_subject": "Test Email Subject",
            "email_body": "<p>This is a test email body.</p>"
        }
        user_email = "user@example.com"

        send_email(email_data, user_email)

        mock_smtp.assert_called_once_with("smtp.gmail.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("dummy_value", "dummy_value")
        mock_server.send_message.assert_called_once()

        mock_pdfkit.assert_called_once_with(email_data["email_body"], False, options={"encoding": "UTF-8"})

        self.assertEqual(mock_server.send_message.call_args[0][0]["Subject"], email_data["email_subject"])
        self.assertEqual(mock_server.send_message.call_args[0][0]["To"], user_email)

    @patch("api.v1.endpoints.rotina.smtplib.SMTP")
    @patch("api.v1.endpoints.rotina.config")
    def test_send_email_exception(self, mock_config, mock_smtp):
        mock_config.side_effect = lambda key: "dummy_value" if key in ["EMAIL_ADDRESS", "EMAIL_PASSWORD"] else None

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        mock_server.send_message.side_effect = Exception("SMTP error")

        # Dados de teste
        email_data = {
            "email_subject": "Test Email Subject",
            "email_body": "<p>This is a test email body.</p>"
        }
        user_email = "user@example.com"

        with self.assertRaises(Exception) as context:
            send_email(email_data, user_email)
        
        self.assertTrue("Error occurred while sending email" in str(context.exception))

import unittest
from datetime import datetime
from typing import List, Dict, Tuple


class Conta:
    def __init__(self, descricao: str, data_pagamento: datetime, valor: float):
        self.descricao = descricao
        self.data_pagamento = data_pagamento
        self.valor = valor

class Fatura:
    def __init__(self, data_vencimento: datetime, fatura_gastos: float):
        self.data_vencimento = data_vencimento
        self.fatura_gastos = fatura_gastos

class Cartao:
    def __init__(self, nome: str):
        self.nome = nome

class TestProcessarUsuariosEmAtraso(unittest.TestCase):
    def setUp(self):
        # Configura dados de teste para usuários_contas e usuarios_faturas
        self.usuarios_contas = {
            "usuario1@example.com": [
                Conta("Conta de Água", datetime(2024, 11, 1), 150.00),
                Conta("Conta de Luz", datetime(2024, 11, 5), 200.00)
            ],
            "usuario2@example.com": [
                Conta("Conta de Internet", datetime(2024, 11, 10), 100.00)
            ]
        }
        
        self.usuarios_faturas = {
            "usuario1@example.com": [
                (Fatura(datetime(2024, 11, 12), 300.00), Cartao("Visa"))
            ],
            "usuario3@example.com": [
                (Fatura(datetime(2024, 11, 15), 400.00), Cartao("Mastercard"))
            ]
        }

    def test_processar_usuarios_em_atraso(self):
        resultados = processar_usuarios_em_atraso(self.usuarios_contas, self.usuarios_faturas)
        
        self.assertEqual(len(resultados), 3)
        
        usuario1_resultado = next(item for item in resultados if item[1] == "usuario1@example.com")
        self.assertIsNotNone(usuario1_resultado)
        self.assertIn("Contas em atraso:", usuario1_resultado[0]["email_body"])
        self.assertIn("Faturas em atraso:", usuario1_resultado[0]["email_body"])
        self.assertIn("Resumo das Pendências:", usuario1_resultado[0]["email_body"])
        self.assertIn("R$ 650.00", usuario1_resultado[0]["email_body"])  # Total a pagar
        
        usuario2_resultado = next(item for item in resultados if item[1] == "usuario2@example.com")
        self.assertIsNotNone(usuario2_resultado)
        self.assertIn("Contas em atraso:", usuario2_resultado[0]["email_body"])
        self.assertIn("Resumo das Pendências:", usuario2_resultado[0]["email_body"])
        self.assertIn("R$ 100.00", usuario2_resultado[0]["email_body"])  # Total a pagar
        
        usuario3_resultado = next(item for item in resultados if item[1] == "usuario3@example.com")
        self.assertIsNotNone(usuario3_resultado)
        self.assertIn("Faturas em atraso:", usuario3_resultado[0]["email_body"])
        self.assertIn("Resumo das Pendências:", usuario3_resultado[0]["email_body"])
        self.assertIn("R$ 400.00", usuario3_resultado[0]["email_body"])  # Total a pagar

if __name__ == "__main__":
    unittest.main()