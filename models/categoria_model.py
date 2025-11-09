from sqlalchemy import Column, String, BigInteger,  Enum as SqlEnum, ForeignKey, UniqueConstraint, DECIMAL, Boolean
from core.configs import settings
from sqlalchemy.orm import relationship
from models.enums import TipoMovimentacao, TipoCategoria



class CategoriaModel(settings.DBBaseModel):
    __tablename__ = "CATEGORIA"

    id_categoria = Column(BigInteger, primary_key=True)
    nome = Column(String(60), nullable=False)
    tipo_categoria = Column(SqlEnum(TipoCategoria), nullable=False)
    modelo_categoria = Column(SqlEnum(TipoMovimentacao), nullable=False)
    id_usuario = Column(BigInteger, ForeignKey("USUARIO.id_usuario"), nullable=False)
    valor_categoria = Column(DECIMAL(10, 2), nullable=True)
    nome_icone = Column(String(100))
    ativo = Column(Boolean, default=True, nullable=False)


    movimentacoes = relationship("MovimentacaoModel", back_populates="categoria")
    usuarios = relationship("UsuarioModel", back_populates="categorias")
    
    __table_args__ = (
        UniqueConstraint('nome', 'id_usuario', name='unique_nome_categoria'),
    )