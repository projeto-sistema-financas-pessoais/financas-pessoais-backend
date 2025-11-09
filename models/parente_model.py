
from sqlalchemy import Column, String, BigInteger, ForeignKey,Boolean
from core.configs import settings
from sqlalchemy.orm import relationship


class ParenteModel(settings.DBBaseModel):
    __tablename__ = "PARENTE"

    id_parente = Column(BigInteger, primary_key=True)
    email = Column(String(50), nullable=True)    
    grau_parentesco = Column(String(100), nullable=False)
    nome = Column(String(60), nullable=False)
    id_usuario = Column(BigInteger, ForeignKey("USUARIO.id_usuario"), nullable=False)
    ativo = Column(Boolean(), default=True)

    usuario = relationship("UsuarioModel", back_populates="parentes")
    divisoes = relationship("DivideModel", back_populates="parentes")

