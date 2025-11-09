from sqlalchemy import Boolean, Column, String, BigInteger, ForeignKey, DECIMAL, Enum as SqlEnum, Date, TIMESTAMP
from core.configs import settings
from sqlalchemy.orm import relationship

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
    consolidado = Column(Boolean(), nullable=False)
    parcela_atual = Column(String(30), nullable=True)
    data_pagamento = Column(Date, nullable=False)
    participa_limite_fatura_gastos = Column(Boolean(), nullable=True)
    id_conta = Column(BigInteger, ForeignKey("CONTA.id_conta"))
    id_categoria = Column(BigInteger, ForeignKey("CATEGORIA.id_categoria"))
    id_fatura = Column(BigInteger, ForeignKey("FATURA.id_fatura"))
    id_repeticao = Column(BigInteger, ForeignKey("REPETICAO.id_repeticao"))
    id_usuario = Column(BigInteger, ForeignKey("USUARIO.id_usuario"), nullable=False)
    id_conta_destino = Column(BigInteger, ForeignKey("CONTA.id_conta"), nullable=True)

    # Especificar foreign_keys para evitar ambiguidade
    conta = relationship("ContaModel", back_populates="movimentacoes", foreign_keys=[id_conta])
    conta_destino = relationship("ContaModel", back_populates="movimentacoes", foreign_keys=[id_conta_destino])
    categoria = relationship("CategoriaModel", back_populates="movimentacoes")
    fatura = relationship("FaturaModel", back_populates="movimentacoes")
    divisoes = relationship("DivideModel", back_populates="movimentacoes", cascade="all, delete-orphan")
    repeticao = relationship("RepeticaoModel", back_populates="movimentacoes")
    usuario = relationship("UsuarioModel", back_populates="movimentacoes")
