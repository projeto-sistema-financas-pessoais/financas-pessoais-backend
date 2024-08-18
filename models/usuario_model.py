from sqlalchemy import Column, String, BigInteger, TIMESTAMP
from sqlalchemy.orm import relationship

from core.configs import settings

from models.associations_model import reune_table

class UsuarioModel(settings.DBBaseModel):
    __tablename__ = "USUARIO"

    id_usuario = Column(BigInteger, primary_key=True)
    nome_completo = Column(String(50), nullable=False)
    data_nascimento = Column(TIMESTAMP(timezone=True), nullable=False)
    email = Column(String(50), nullable=False, unique=True)
    senha = Column(String(500), nullable=False)
    # nome = Column(String(60))


    contas = relationship("ContaModel", cascade= "all, delete-orphan", back_populates="usuario")
    parentes = relationship("ParenteModel", cascade= "all, delete-orphan",back_populates="usuario")
    cartoes_credito = relationship("CartaoCreditoModel", cascade= "all, delete-orphan", back_populates="usuario")
    categorias = relationship("CategoriaModel", secondary=reune_table, back_populates="usuarios")