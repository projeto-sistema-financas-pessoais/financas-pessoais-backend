from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import io
import smtplib
from decouple import config
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status, Response
from fastapi.responses import JSONResponse
import pdfkit
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from sqlalchemy import and_
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from core.auth import send_email
from core.utils import handle_db_exceptions
from models.enums import TipoMovimentacao
from models.parente_model import ParenteModel
from models.divide_model import  DivideModel
from models.movimentacao_model import MovimentacaoModel
from schemas.parente_schema import ParenteSchema, ParenteSchemaCobranca, ParenteSchemaUpdate, ParenteSchemaId
from core.deps import get_session, get_current_user
from models.usuario_model import UsuarioModel
from sqlalchemy import case, extract, func, select

router = APIRouter()

@router.post('/cadastro', status_code=status.HTTP_201_CREATED)
async def post_parente(
    parente: ParenteSchema, 
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    if parente.nome.lower() == str(usuario_logado.nome_completo).lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido cadastrar um parente com o nome do usuário."
        )
    
    novo_parente: ParenteModel = ParenteModel(
        nome=parente.nome,
        email=parente.email,
        grau_parentesco=parente.grau_parentesco,
        id_usuario=usuario_logado.id_usuario,
        ativo=parente.ativo
    )
    
    async with db as session:
        try:
            session.add(novo_parente)
            await session.commit()
            return novo_parente
        except Exception as e:
            await handle_db_exceptions(session, e)
        finally:
            await session.close()

@router.put('/editar/{id_parente}', response_model=ParenteSchemaId, status_code=status.HTTP_202_ACCEPTED)
async def update_parente(id_parente: int, parente_update: ParenteSchemaUpdate, db: AsyncSession = Depends(get_session), usuario_logado: UsuarioModel = Depends(get_current_user)):
    async with db as session:
        query = select(ParenteModel).filter(ParenteModel.id_parente == id_parente)
        result = await session.execute(query)
        parente: ParenteModel = result.scalars().unique().one_or_none()

        if not parente:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parente não encontrado para edição.")

        if parente.id_usuario != usuario_logado.id_usuario:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não tem permissão para editar este parente.")

        if parente_update.nome:
            query_nome = select(ParenteModel).filter(ParenteModel.nome == parente_update.nome, ParenteModel.id_usuario == usuario_logado.id_usuario, ParenteModel.id_parente != id_parente)
            result_nome = await session.execute(query_nome)
            parente_existente = result_nome.scalars().first()

            if parente_existente:
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Já existe um parente com este nome.")

        if parente_update.grau_parentesco is not None:
            parente.grau_parentesco = parente_update.grau_parentesco

        if parente_update.nome is not None:
            parente.nome = parente_update.nome

        if parente_update.email is not None:
            parente.email = parente_update.email
            
        if parente_update.ativo is not None:
            parente.ativo = bool(parente_update.ativo)

        try:
            await session.commit()
            return parente
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Erro ao atualizar o parente. Verifique os dados e tente novamente.")
        
@router.get('/listar/{somente_ativo}', response_model=list[ParenteSchemaId], status_code=status.HTTP_200_OK)
async def get_parentes(somente_ativo: bool, db: AsyncSession = Depends(get_session), 
                       usuario_logado: UsuarioModel = Depends(get_current_user)):
    async with db as session:
        try:
            query = select(ParenteModel).where(
                ParenteModel.id_usuario == usuario_logado.id_usuario,
                ParenteModel.ativo if somente_ativo else True
            ).order_by(
                case((ParenteModel.nome == usuario_logado.nome_completo, 0), else_=1),  # Prioriza o nome igual ao de `usuario.nome`
                ParenteModel.nome 
            )

            result = await session.execute(query)
            
            parentes: List[ParenteSchemaId] = result.scalars().all()
            if not parentes:
                print("Nenhum parente encontrado.")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhum parente encontrado.")
            return parentes

        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao listar parentes.")


@router.get('/visualizar/{id_parente}', response_model=ParenteSchemaId, status_code=status.HTTP_200_OK)
async def get_parente(id_parente: int, db: AsyncSession = Depends(get_session), usuario_logado: UsuarioModel = Depends(get_current_user)):
    async with db as session:
        query = select(ParenteModel).filter(ParenteModel.id_parente == id_parente, ParenteModel.id_usuario == usuario_logado.id_usuario)
        result = await session.execute(query)
        parente = result.scalars().one_or_none()

        if not parente:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parente com esse id não foi encontrado .")

        return parente

@router.delete('/deletar/{id_parente}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_parente(id_parente: int, db: AsyncSession = Depends(get_session), usuario_logado: UsuarioModel = Depends(get_current_user)):
    async with db as session:
        query = select(ParenteModel).filter(ParenteModel.id_parente == id_parente, ParenteModel.id_usuario == usuario_logado.id_usuario)
        result = await session.execute(query)
        parente = result.scalars().one_or_none()

        if not parente:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não é possível deletar esse parente.")

        try:
            await session.delete(parente)
            await session.commit()
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Erro ao tentar deletar o parente.")
        
@router.post("/enviar-cobranca", status_code=status.HTTP_202_ACCEPTED)
async def send_invoice(
    cobranca: ParenteSchemaCobranca,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    
    async with db as session:
        try:
            query = select(ParenteModel).filter(
                ParenteModel.id_parente == cobranca.id_parente,
                ParenteModel.id_usuario == usuario_logado.id_usuario
            )
            result = await session.execute(query)
            parente = result.scalars().one_or_none()

            # Busca os dados e acessa a chave 'data'
            response = await send_invoice_pdf(cobranca, db, usuario_logado)
            movimentacoes_data = response['data']

            def formatar_data_brasileira(data_str):
                """Converte data do formato YYYY-MM-DD para DD/MM/YYYY"""
                return datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%Y')

            def formatar_valor_brasileiro(valor):
                """Formata o valor monetário no padrão brasileiro"""
                try:
                    valor_float = float(valor)
                    return f'R$ {valor_float:,.2f}'.replace('.', 'X').replace(',', '.').replace('X', ',')
                except ValueError:
                    return valor

             # Chama a função auxiliar para criar o email_data
            email_data = criar_email_data(parente, usuario_logado, cobranca, movimentacoes_data)

            # Envia o email em segundo plano
            background_tasks.add_task(send_email, email_data, parente.email)

            return {"message": "Cobrança enviada por email com sucesso."}

        except Exception as e:
            await handle_db_exceptions(session, e)
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={'message': 'Erro ao enviar cobrança'})
        
        
def formatar_valor_brasileiro(valor):
    """Formata o valor monetário no padrão brasileiro"""
    try:
        valor_float = float(valor)
        return f'R$ {valor_float:,.2f}'.replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.')
    except ValueError:
        return valor

def criar_email_data(parente, usuario_logado, cobranca, movimentacoes_data):
    """Cria os dados do email com base nas condições de parente e usuário logado."""
    
    def formatar_data_brasileira(data_str):
        """Converte data do formato YYYY-MM-DD para DD/MM/YYYY"""
        return datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%Y')

 

    if parente.nome == usuario_logado.nome_completo:
        return {
            "email_subject": "Lembrete de Movimentações não Consolidadas",
            "email_body": (
                f"Olá, {usuario_logado.nome_completo}!<br><br>"
                f"Seguem as informações referentes ao mês {cobranca.mes}/{cobranca.ano}:<br><br>"                        
                f"<table style='border-collapse: collapse; width: 100%;'>"
                f"<thead>"
                f"<tr style='background-color: #f2f2f2;'>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Descrição</th>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Data</th>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Valor</th>"
                f"</tr>"
                f"</thead>"
                f"<tbody>"
            ) + "".join(
                f"<tr>"
                f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{mov['descricao']}</td>"
                f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{formatar_data_brasileira(mov['data_pagamento'])}</td>"
                f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{formatar_valor_brasileiro(mov['valor'])}</td>"
                f"</tr>"
                for mov in movimentacoes_data['movimentacoes_nao_consolidadas']
            ) + (
                f"</tbody>"
                f"</table><br>"
                f"<h4>Resumo da Cobrança:</h4>"
                f"<table style='border-collapse: collapse; width: 100%;'>"
                f"<tr style='background-color: #f2f2f2;'>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Total das Movimentações</th>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Total a Pagar</th>"
                f"</tr>"
                f"<tr>"
                f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{formatar_valor_brasileiro(movimentacoes_data['fatura_geral']['total_geral_movimentacoes'])}</td>"
                f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{formatar_valor_brasileiro(movimentacoes_data['fatura_geral']['total_movimentacoes'])}</td>"
                f"</tr>"
                f"</table><br>"
                f"Por favor, acesse o sistema para mais informações."
            )
        }
    else:
        return {
            "email_subject": "Cobrança de Movimentações não Consolidadas",
            "email_body": (
                f"Olá, {parente.nome},<br><br>"
                f"Seguem as informações referentes às suas movimentações não consolidadas com {usuario_logado.nome_completo} no mês {cobranca.mes}/{cobranca.ano}:<br><br>"
                f"<table style='border-collapse: collapse; width: 100%;'>"
                f"<thead>"
                f"<tr style='background-color: #f2f2f2;'>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Descrição</th>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Data</th>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Valor</th>"
                f"</tr>"
                f"</thead>"
                f"<tbody>"
            ) + "".join(
                f"<tr>"
                f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{mov['descricao']}</td>"
                f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{formatar_data_brasileira(mov['data_pagamento'])}</td>"
                f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{formatar_valor_brasileiro(mov['valor'])}</td>"
                f"</tr>"
                for mov in movimentacoes_data['movimentacoes_nao_consolidadas']
            ) + (
                f"</tbody>"
                f"</table><br>"
                f"<h4>Resumo da Cobrança:</h4>"
                f"<table style='border-collapse: collapse; width: 100%;'>"
                f"<tr style='background-color: #f2f2f2;'>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Total das Movimentações</th>"
                f"<th style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>Total a Pagar</th>"
                f"</tr>"
                f"<tr>"
                f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{formatar_valor_brasileiro(movimentacoes_data['fatura_geral']['total_geral_movimentacoes'])}</td>"
                f"<td style='border: 1px solid #dddddd; text-align: left; padding: 8px;'>{formatar_valor_brasileiro(movimentacoes_data['fatura_geral']['total_movimentacoes'])}</td>"
                f"</tr>"
                f"</table><br>"
                f"Por favor, acesse o sistema para mais informações."
            )
        }



def send_email(email_data: dict, user_email: str) -> None:
    try:
        # Verifique se os dados de e-mail foram lidos corretamente
        sender_email = config("EMAIL_ADDRESS")
        sender_password = config("EMAIL_PASSWORD")

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


@router.post("/cobranca", status_code=status.HTTP_202_ACCEPTED)
async def send_invoice_pdf(
    cobranca: ParenteSchemaCobranca,
    db: AsyncSession = Depends(get_session),
    usuario_logado: UsuarioModel = Depends(get_current_user)
):
    
    async with db as session:
        try:
            query = select(ParenteModel).filter(
                ParenteModel.id_parente == cobranca.id_parente,
                ParenteModel.id_usuario == usuario_logado.id_usuario
            )
            result = await session.execute(query)
            parente = result.scalars().one_or_none()

            if not parente:
                return {"message": "Parente não encontrado."}
            
            query = select(
                DivideModel,
                MovimentacaoModel.descricao,
                MovimentacaoModel.data_pagamento,
                MovimentacaoModel.valor, 
            ).join(MovimentacaoModel).filter(
                DivideModel.id_parente == cobranca.id_parente,
                MovimentacaoModel.consolidado == False,
                MovimentacaoModel.tipoMovimentacao == TipoMovimentacao.DESPESA,
                ((extract("year", MovimentacaoModel.data_pagamento) == cobranca.ano) & 
                 (extract("month", MovimentacaoModel.data_pagamento) == cobranca.mes))
            )
            
            result = await session.execute(query)
            movimentacoes_nao_consolidadas = result.all()

            total_movimentacoes = sum(divide.valor for divide, _, _, _ in movimentacoes_nao_consolidadas)


            query_total = select(
                func.sum(DivideModel.valor)
            ).join(
                MovimentacaoModel
            ).filter(
                DivideModel.id_parente == cobranca.id_parente,
                MovimentacaoModel.consolidado == False,
                MovimentacaoModel.tipoMovimentacao == TipoMovimentacao.DESPESA,
                and_(
                    extract("year", MovimentacaoModel.data_pagamento) == cobranca.ano,
                    extract("month", MovimentacaoModel.data_pagamento) == cobranca.mes
                ),

            )
            total_geral_result = await session.execute(query_total)
            total_geral_movimentacoes = total_geral_result.scalar() or 0  

            response = {
                "movimentacoes_nao_consolidadas": [],
                "fatura_geral": {}
            }

            for divide, descricao, data_pagamento, valor in movimentacoes_nao_consolidadas:
                    descricao = f"{descricao or 'Outros'}"
                    response["movimentacoes_nao_consolidadas"].append({
                    "id_parente": divide.id_parente,
                    "descricao": descricao,
                    "data_pagamento": str(data_pagamento), 
                    "valor": float(divide.valor)  
                })

    

            response["fatura_geral"] = {
                "total_movimentacoes": float(total_movimentacoes),
                "total_geral_movimentacoes": float(total_geral_movimentacoes)
            }

            return {"data": response}

        except Exception as e:
            await handle_db_exceptions(session, e)
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={'message': 'Erro ao calcular cobrança'})