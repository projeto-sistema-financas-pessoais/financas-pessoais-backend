# from sqlalchemy import Table, Column, BigInteger, ForeignKey,DECIMAL
# from core.configs import settings

# divide_table = Table(
#     "divide",
#     settings.DBBaseModel.metadata,
#     Column("id_parente", BigInteger, ForeignKey("PARENTE.id_parente"), primary_key=True),
#     Column("id_movimentacao", BigInteger, ForeignKey("MOVIMENTACAO.id_movimentacao"), primary_key=True),
#     Column("valor", DECIMAL(10, 2), nullable=False), # valor que o cliente divide com o parente
# )

# reune_table = Table(
#     "reune",
#     settings.DBBaseModel.metadata,
#     Column("id_categoria", BigInteger, ForeignKey("CATEGORIA.id_categoria"), primary_key=True),
#     Column("id_usuario", BigInteger, ForeignKey("USUARIO.id_usuario"), primary_key=True),
#     Column("valor_categoria", DECIMAL(10, 2), nullable=False), # gastots maxímos por categoria
# )