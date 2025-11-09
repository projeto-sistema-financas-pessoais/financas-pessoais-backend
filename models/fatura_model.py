

from sqlalchemy import Column, String, BigInteger, ForeignKey, DECIMAL, Enum as SqlEnum, Date, DateTime
from core.configs import settings
from sqlalchemy.orm import relationship

class FaturaModel(settings.DBBaseModel):
    __tablename__ = "FATURA"

    id_fatura = Column(BigInteger, primary_key=True)
    data_vencimento = Column(Date)
    data_fechamento = Column(Date)
    data_pagamento = Column(Date)
    fatura_gastos = Column(DECIMAL(10,2))
    id_conta = Column(BigInteger, ForeignKey("CONTA.id_conta"))
    id_cartao_credito = Column(BigInteger, ForeignKey("CARTAO_CREDITO.id_cartao_credito"))
    

    conta = relationship("ContaModel", back_populates="faturas")
    cartao_credito = relationship("CartaoCreditoModel", back_populates="faturas")
    movimentacoes = relationship("MovimentacaoModel", back_populates="fatura")