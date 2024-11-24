from models.usuario_model import UsuarioModel
from models.conta_model import ContaModel
from models.parente_model import ParenteModel
from models.cartao_credito_model import CartaoCreditoModel
from models.categoria_model import CategoriaModel
from models.fatura_model import FaturaModel
from models.movimentacao_model import MovimentacaoModel
from models.repeticao_model import RepeticaoModel
from models.divide_model import DivideModel


from core.configs import settings

# Coletar metadatas
metadata = settings.DBBaseModel.metadata

__all__ = [
    "CartaoCreditoModel", "CategoriaModel", "ContaModel", "UsuarioModel",
    "FaturaModel", "MovimentacaoModel", "ParenteModel", "RepeticaoModel", "DivideModel"
]
