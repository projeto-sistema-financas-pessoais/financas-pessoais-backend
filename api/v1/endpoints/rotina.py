
from collections import defaultdict
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import logging
import smtplib
from fastapi import logger
import pdfkit
from sqlalchemy import select
from core.auth import send_email
from core.deps import get_session
from models.enums import TipoMovimentacao
from models.movimentacao_model import MovimentacaoModel
from models.usuario_model import UsuarioModel
from models.fatura_model import FaturaModel
from models.cartao_credito_model import CartaoCreditoModel
from decouple import config
import io

from api.v1.endpoints.parente import formatar_valor_brasileiro


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_email(email_data: dict, user_email: str) -> None:
    try:
        # Verifique se os dados de e-mail foram lidos corretamente
        sender_email = config("EMAIL_ADDRESS")
        sender_password = config("EMAIL_PASSWORD")

        print("Endereço de e-mail do remetente será usado")

        # Configura a mensagem
        msg = MIMEMultipart()
        msg["Subject"] = email_data["email_subject"]
        msg["From"] = sender_email
        msg["To"] = user_email
        msg["Date"] = formatdate(localtime=True)

        # Adicionar o corpo do e-mail
        body = MIMEText(email_data["email_body"], "html", "utf-8")
        msg.attach(body)

        pdf_buffer = io.BytesIO()
        pdf_data = pdfkit.from_string(email_data["email_body"], False, options={"encoding": "UTF-8"})
        pdf_buffer.write(pdf_data)
        pdf_buffer.seek(0)

        # Anexar o PDF
        attachment = MIMEBase("application", "pdf")
        attachment.set_payload(pdf_buffer.read())
        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            "attachment; filename=financas.pdf"
        )
        msg.attach(attachment)

        # Conectar ao servidor SMTP do Gmail
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)  # Usa as credenciais
            server.send_message(msg)

    except Exception as e:
        raise Exception(f"Error occurred while sending email: {e}")


async def check_and_send_email():
    try:
        async for session in get_session():
            query_movimentacoes = (
                select(MovimentacaoModel, UsuarioModel.email)
                .join(UsuarioModel, MovimentacaoModel.id_usuario == UsuarioModel.id_usuario)
                .where(
                    MovimentacaoModel.data_pagamento < datetime.now(),
                    MovimentacaoModel.consolidado == False,
                    MovimentacaoModel.id_fatura == None,
                    MovimentacaoModel.tipoMovimentacao == TipoMovimentacao.DESPESA
                )
            )
            
            query_faturas = (
                select(FaturaModel, UsuarioModel.email, CartaoCreditoModel)
                .join(CartaoCreditoModel, FaturaModel.id_cartao_credito == CartaoCreditoModel.id_cartao_credito)
                .join(UsuarioModel, CartaoCreditoModel.id_usuario == UsuarioModel.id_usuario)
                .where(
                    FaturaModel.data_pagamento == None,
                    FaturaModel.data_vencimento < datetime.now(),
                    FaturaModel.fatura_gastos > 0
                )
            )
            
            result_movimentacoes = await session.execute(query_movimentacoes)
            result_faturas = await session.execute(query_faturas)
            contas_vencidas = result_movimentacoes.all()
            faturas_vencidas = result_faturas.all()
            
            usuarios_contas = defaultdict(list)
            usuarios_faturas = defaultdict(list)
            for conta, user_email in contas_vencidas:
                if user_email:
                    usuarios_contas[user_email].append(conta)
                else:
                    logger.warning(f"Movimentação '{conta.descricao}' não possui e-mail de usuário.")
            for fatura, user_email, cartao in faturas_vencidas:
                if user_email:
                    usuarios_faturas[user_email].append((fatura, cartao))
                else:
                    logger.warning(f"Fatura com ID '{fatura.id_fatura}' não possui e-mail de usuário.")
            if usuarios_contas or usuarios_faturas:
                resultados =  processar_usuarios_em_atraso(usuarios_contas, usuarios_faturas)
                for email_data, user_email in resultados:
                    try:
                        logger.info(f"Enviando e-mail para {user_email}...")
                        send_email(email_data, user_email)
                        logger.info(f"E-mail enviado com sucesso para {user_email}.")
                    except Exception as e:
                        logger.error(f"Erro ao enviar e-mail para {user_email}: {e}")
                        continue
            else:
                logger.info("Nenhuma conta ou fatura vencida foi encontrada.")
            
    except Exception as e:
        logger.error(f"Erro na execução de check_and_send_email: {e}")
        
def processar_usuarios_em_atraso(usuarios_contas, usuarios_faturas):
    resultados = []
    all_user_emails = set(usuarios_contas.keys()) | set(usuarios_faturas.keys())
    
    for user_email in all_user_emails:
        email_body = ""
        total_atraso = 0
        
        if user_email in usuarios_contas:
            contas = usuarios_contas[user_email]
            email_body += (
                f"<h4>Contas em atraso:</h4>"
                f"<table style='border-collapse: collapse; width: 100%;'>"
                f"<thead>"
                f"<tr style='background-color: #f2f2f2;'>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Descrição</th>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Data de Vencimento</th>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Valor</th>"
                f"</tr>"
                f"</thead>"
                f"<tbody>"
            )
            for conta in contas:
                conta.descricao = f"{conta.descricao or 'Outros'}"
                email_body += (
                    f"<tr>"
                    f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{conta.descricao}</td>"
                    f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{conta.data_pagamento.strftime('%d/%m/%Y')}</td>"
                    f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{formatar_valor_brasileiro(conta.valor)}</td>"
                    f"</tr>"
                )
                total_atraso += conta.valor
            email_body += "</tbody></table>"
        
        if user_email in usuarios_faturas:
            faturas_info = usuarios_faturas[user_email]
            if email_body:
                email_body += "<br>"
            email_body += (
                f"<h4>Faturas em atraso:</h4>"
                f"<table style='border-collapse: collapse; width: 100%;'>"
                f"<thead>"
                f"<tr style='background-color: #f2f2f2;'>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Cartão</th>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Data de Vencimento</th>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Valor</th>"
                f"</tr>"
                f"</thead>"
                f"<tbody>"
            )
            for fatura, cartao in faturas_info:
                email_body += (
                    f"<tr>"
                    f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Fatura - {cartao.nome}</td>"
                    f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{fatura.data_vencimento.strftime('%d/%m/%Y')}</td>"
                    f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{formatar_valor_brasileiro(fatura.fatura_gastos)}</td>"
                    f"</tr>"
                )
                total_atraso += fatura.fatura_gastos
            email_body += "</tbody></table>"
        
        # Adiciona o resumo
        email_body += (
            f"<br><h4>Resumo das Pendências:</h4>"
            f"<table style='border-collapse: collapse; width: 100%;'>"
            f"<tr style='background-color: #f2f2f2;'>"
            f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Total a Pagar</th>"
            f"</tr>"
            f"<tr>"
            f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{formatar_valor_brasileiro(total_atraso)}</td>"
            f"</tr>"
            f"</table><br>"
            f"Por favor, tome as devidas providências.<br><br>"
            f"Atenciosamente,<br>Equipe Finanças Pessoais!"
        )
        
        email_data = {
            "email_subject": "Alerta: Contas e Faturas em Atraso",
            "email_body": email_body
        }
        resultados.append((email_data, user_email))
    
    return resultados
