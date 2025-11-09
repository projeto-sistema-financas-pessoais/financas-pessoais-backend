from sqlalchemy import Column , BigInteger, ForeignKey, DECIMAL, Enum 
from core.configs import settings
from sqlalchemy.orm import relationship

class DivideModel(settings.DBBaseModel):
    __tablename__ = "divide"

    id_parente = Column(BigInteger, ForeignKey("PARENTE.id_parente"), primary_key=True)
    id_movimentacao = Column(BigInteger, ForeignKey("MOVIMENTACAO.id_movimentacao"), primary_key=True)
    valor = Column(DECIMAL(10, 2), nullable=False)

    parentes = relationship("ParenteModel", back_populates="divisoes")
    movimentacoes = relationship("MovimentacaoModel", back_populates="divisoes")