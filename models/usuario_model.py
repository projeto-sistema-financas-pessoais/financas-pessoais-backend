from sqlalchemy import Column, String, BigInteger, Date
from sqlalchemy.orm import relationship
from core.configs import settings
from models.repeticao_model import RepeticaoModel
class UsuarioModel(settings.DBBaseModel):
    __tablename__ = "USUARIO"

    id_usuario = Column(BigInteger, primary_key=True)
    nome_completo = Column(String(50), nullable=False)
    data_nascimento = Column(Date, nullable=False)
    email = Column(String(50), nullable=False, unique=True)
    senha = Column(String(500), nullable=False)

    contas = relationship("ContaModel", cascade= "all, delete-orphan", back_populates="usuario")
    parentes = relationship("ParenteModel", cascade= "all, delete-orphan",back_populates="usuario")
    cartoes_credito = relationship("CartaoCreditoModel", cascade= "all, delete-orphan", back_populates="usuario")
    categorias = relationship("CategoriaModel", cascade= "all, delete-orphan", back_populates="usuarios")
    movimentacoes = relationship("MovimentacaoModel", cascade= "all, delete-orphan", back_populates="usuario")

    repeticao = relationship("RepeticaoModel", cascade= "all, delete-orphan", back_populates="usuario")
