from sqlalchemy import Column, String, DECIMAL, BigInteger, ForeignKey, UniqueConstraint, Boolean
from core.configs import settings
from sqlalchemy.orm import relationship

from models.enums import TipoConta

class ContaModel(settings.DBBaseModel):
    __tablename__ = "CONTA"

    id_conta = Column(BigInteger, primary_key=True) 
    descricao = Column(String(500), nullable=True)
    tipo_conta = Column(String(100), nullable=False)
    id_usuario = Column(BigInteger, ForeignKey("USUARIO.id_usuario"), nullable=False)
    nome = Column(String(500), nullable=False)
    nome_icone = Column(String(100))
    ativo = Column(Boolean, default=True)  # Adicionando a coluna ativo
    saldo = Column(DECIMAL(10, 2))

    usuario = relationship("UsuarioModel", back_populates="contas")
    movimentacoes = relationship("MovimentacaoModel", back_populates="conta", foreign_keys="[MovimentacaoModel.id_conta]")
    movimentacoes_destino = relationship("MovimentacaoModel", back_populates="conta_destino", foreign_keys="[MovimentacaoModel.id_conta_destino]")
    faturas = relationship("FaturaModel", back_populates="conta")

    __table_args__ = (
        UniqueConstraint('nome', 'id_usuario', name='unique_nome_conta'),
    )
