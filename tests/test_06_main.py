

import unittest
from unittest.mock import patch, MagicMock
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from main import executar_funcao_assincrona, agendar_execucao, scheduler

async def mock_check_and_send_email():
    print("Função executada")

# Teste
class TestFuncoesAgendamento(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        patch('api.v1.endpoints.rotina.check_and_send_email', new=mock_check_and_send_email).start()
        patch('apscheduler.schedulers.background.BackgroundScheduler.add_job').start()

    @patch('apscheduler.schedulers.background.BackgroundScheduler.add_job')
    def test_agendar_execucao(self, mock_add_job):
        agendar_execucao(2, 54, self.loop)

        mock_add_job.assert_called_once()
        args = mock_add_job.call_args[1]['args']
        
        self.assertEqual(args[0], executar_funcao_assincrona)
    
    @patch('api.v1.endpoints.rotina.check_and_send_email')
    def test_executar_funcao_assincrona(self, mock_check_and_send_email):
        mock_check_and_send_email.return_value = None  # Simula a função sem retorno

        executar_funcao_assincrona(self.loop)

        mock_check_and_send_email.assert_called_once()

if __name__ == "__main__":
    unittest.main()
