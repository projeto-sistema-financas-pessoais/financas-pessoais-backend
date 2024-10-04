

from sqlalchemy import Column, String, BigInteger, ForeignKey, DECIMAL, Enum as SqlEnum, Date, TIMESTAMP
from core.configs import settings
from sqlalchemy.orm import relationship
from models.associations_model import divide_table

from models.enums import CondicaoPagamento, FormaPagamento, TipoMovimentacao


class MovimentacaoModel(settings.DBBaseModel):
    __tablename__ = "MOVIMENTACAO"

    id_movimentacao = Column(BigInteger, primary_key=True)
    valor = Column(DECIMAL(10, 2), nullable=False)
    descricao = Column(String(500))
    tipoMovimentacao = Column(SqlEnum(TipoMovimentacao), nullable=False)
    forma_pagamento = Column(SqlEnum(FormaPagamento), nullable=False)
    condicao_pagamento = Column(SqlEnum(CondicaoPagamento), nullable=False)
    datatime = Column(TIMESTAMP(timezone=True), nullable=True)
    quantidade_parcelas = Column(BigInteger)
    consolidado = Column(String(100), nullable=False)
    tipo_recorrencia = Column(String(100))
    recorrencia = Column(String(100))
    data_pagamento = Column(Date, nullable=False)
    id_conta = Column(BigInteger, ForeignKey("CONTA.id_conta"))
    id_categoria = Column(BigInteger, ForeignKey("CATEGORIA.id_categoria"))
    id_fatura = Column(BigInteger, ForeignKey("FATURA.id_fatura"))

    conta = relationship("ContaModel", back_populates="movimentacoes")
    categoria = relationship("CategoriaModel", back_populates="movimentacoes")
    fatura = relationship("FaturaModel", back_populates="movimentacoes")
    parentes = relationship("ParenteModel", secondary=divide_table, back_populates="movimentacoes")
