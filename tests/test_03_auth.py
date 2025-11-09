import string
from fastapi import Request
import core.auth
import unittest
from unittest.mock import patch, MagicMock
import smtplib

class TestSendEmail(unittest.TestCase):
    @patch("core.auth.smtplib.SMTP")
    @patch("core.auth.config")
    def test_send_email_success(self, mock_config, mock_smtp):
        mock_config.side_effect = lambda key: "mock_value" if key in ["EMAIL_ADDRESS", "EMAIL_PASSWORD"] else None
        
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        email_data = {
            "email_subject": "Test Subject",
            "email_body": "<html><body><h1>Test Body</h1></body></html>"
        }
        user_email = "recipient@example.com"

        core.auth.send_email(email_data, user_email)

        mock_smtp.assert_called_once_with("smtp.gmail.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("mock_value", "mock_value")
        mock_server.send_message.assert_called_once()

    @patch("core.auth.smtplib.SMTP")
    @patch("core.auth.config")
    def test_send_email_exception(self, mock_config, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, "Authentication failed")

        mock_config.side_effect = lambda key: "mock_value" if key in ["EMAIL_ADDRESS", "EMAIL_PASSWORD"] else None

        email_data = {
            "email_subject": "Test Subject",
            "email_body": "<html><body><h1>Test Body</h1></body></html>"
        }
        user_email = "recipient@example.com"

        with self.assertRaises(Exception) as context:
            core.auth.send_email(email_data, user_email)

        self.assertTrue("Error occurred while sending email" in str(context.exception))


from jose import jwt, JWTError


class TestDecodedToken(unittest.TestCase):
    @patch("core.auth.jwt.decode")
    @patch("core.auth.settings.JWT_SECRET", new="secret")
    @patch("core.auth.settings.ALGORITHM", new="HS256")
    def test_decoded_token_success(self, mock_decode):
        mock_decode.return_value = {"user_id": 123, "username": "john_doe"}

        token = "valid_token"
        
        result = core.auth.decoded_token(token)
        
        mock_decode.assert_called_once_with(token, "secret", algorithms=["HS256"])
        self.assertEqual(result, {"user_id": 123, "username": "john_doe"})

    @patch("core.auth.jwt.decode")
    @patch("core.auth.settings.JWT_SECRET", new="secret")
    @patch("core.auth.settings.ALGORITHM", new="HS256")
    def test_decoded_token_invalid_token(self, mock_decode):
        # Simula uma exceção JWTError
        mock_decode.side_effect = JWTError("Token inválido ou expirado")
        
        token = "invalid_token"

        with self.assertRaises(Exception) as context:
            core.auth.decoded_token(token)

        self.assertTrue("Token inválido ou expirado" in str(context.exception))
        mock_decode.assert_called_once_with(token, "secret", algorithms=["HS256"])
        
        
class TestGeneratePassword(unittest.TestCase):
    @patch("core.auth.secrets.choice")
    def test_generate_password_default_length(self, mock_choice):
        mock_choice.side_effect = lambda characters: characters[0]  # Sempre retorna o primeiro caractere

        password = core.auth.generate_password()

        self.assertEqual(len(password), 8)

        self.assertTrue(all(char in string.ascii_letters + string.digits for char in password))

    @patch("core.auth.secrets.choice")
    def test_generate_password_custom_length(self, mock_choice):
        mock_choice.side_effect = lambda characters: characters[0]  # Sempre retorna o primeiro caractere

        custom_length = 12
        password = core.auth.generate_password(length=custom_length)

        self.assertEqual(len(password), custom_length)

        self.assertTrue(all(char in string.ascii_letters + string.digits for char in password))

    @patch("core.auth.secrets.choice")
    def test_generate_password_randomness(self, mock_choice):
        mock_choice.side_effect = lambda characters: characters[0] if len(characters) % 2 == 0 else characters[1]

        password = core.auth.generate_password()

        self.assertEqual(len(password), 8)

        self.assertTrue(all(char in string.ascii_letters + string.digits for char in password))

        self.assertNotEqual(password, string.ascii_letters + string.digits[0] * 8)

if __name__ == "__main__":
    unittest.main()
