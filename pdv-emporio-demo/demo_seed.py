"""Seed de dados ficticios para o ambiente de demonstracao publica do PDV Emporio.

IMPORTANTE: isso e SOMENTE para a demo publica. Nunca rode isso contra o banco
de producao real da Distribuidora Emporio -- os produtos abaixo sao ficticios,
nao tem nenhuma relacao com o catalogo real do cliente.
"""
from database import inicializar_banco, db_conectar, db_produto_cadastrar

PRODUTOS_DEMO = [
    ("7891000100103", "Refrigerante Cola 2L", 8.90, 5, 40),
    ("7891000100104", "Agua Mineral 500ml", 2.50, 10, 100),
    ("7891000100105", "Cerveja Pilsen Lata 350ml", 4.20, 10, 80),
    ("7891000100106", "Suco de Laranja 1L", 7.50, 5, 30),
    ("7891000100107", "Energetico 250ml", 9.90, 5, 25),
    ("7891000100108", "Agua com Gas 500ml", 3.00, 10, 60),
    ("7891000100109", "Refrigerante Guarana 2L", 8.50, 5, 35),
    ("7891000100110", "Cerveja Long Neck 355ml", 6.00, 10, 50),
    ("7891000100111", "Isotonico 500ml", 6.50, 5, 20),
    ("7891000100112", "Cha Gelado 1.5L", 7.00, 5, 15),
]

TABELAS_PARA_LIMPAR = [
    "itens_pagamento", "itens_venda", "vendas",
    "movimentacoes_estoque", "fluxo_caixa", "produtos",
]


def resetar_e_semear():
    """Recria o schema (se preciso) e repopula com produtos ficticios.
    Seguro rodar quantas vezes quiser -- e exatamente o objetivo."""
    inicializar_banco()
    conn = db_conectar()
    cur = conn.cursor()
    for tabela in TABELAS_PARA_LIMPAR:
        cur.execute(f"DELETE FROM {tabela}")
    conn.commit()
    conn.close()

    for codigo, descricao, preco, estoque_min, estoque_atual in PRODUTOS_DEMO:
        db_produto_cadastrar(codigo, descricao, preco, estoque_min, estoque_atual)

    print(f"[DEMO] Banco reiniciado com {len(PRODUTOS_DEMO)} produtos ficticios.")


if __name__ == "__main__":
    resetar_e_semear()
