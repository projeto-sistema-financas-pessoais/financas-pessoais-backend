from sqlalchemy import Column, String, BigInteger, DECIMAL, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship

from core.configs import settings


class CartaoCreditoModel(settings.DBBaseModel):
    __tablename__ = "CARTAO_CREDITO"

    id_cartao_credito = Column(BigInteger, primary_key=True)
    nome = Column(String(60), nullable=False)
    limite = Column(DECIMAL(10, 2), nullable=False)
    id_usuario = Column(BigInteger, ForeignKey("USUARIO.id_usuario"), nullable=False)
    nome_icone = Column(String(100))
    ativo = Column(Boolean, default=True)  # Adicionando a coluna ativo
    limite_disponivel = Column(DECIMAL(10,2))

    usuario = relationship("UsuarioModel", back_populates="cartoes_credito")
    faturas = relationship("FaturaModel", back_populates="cartao_credito", cascade= "all, delete-orphan")
    
    __table_args__ = (
    UniqueConstraint('nome', 'id_usuario', name='unique_nome_cartao'),
    )