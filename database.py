import sqlite3

DB_PATH = "emporio_pdv.db"


def db_conectar():
    """Função única de conexão para todo o sistema."""
    return sqlite3.connect(DB_PATH, timeout=10)


def db_executar_query(query, params=()):
    """Executa INSERT/UPDATE/DELETE, commita e fecha a conexão.
    Retorna o cursor (útil para pegar lastrowid, por exemplo)."""
    conn = db_conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def db_buscar_um(query, params=()):
    """Executa um SELECT e retorna uma única linha (ou None)."""
    conn = db_conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()
    finally:
        conn.close()


def db_buscar_todos(query, params=()):
    """Executa um SELECT e retorna todas as linhas."""
    conn = db_conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        conn.close()


def inicializar_banco():
    conn = db_conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            codigo_barras TEXT PRIMARY KEY,
            descricao TEXT NOT NULL,
            preco_venda REAL NOT NULL,
            estoque_minimo INTEGER DEFAULT 0,
            estoque_atual INTEGER DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)

    # Migração pra bancos já existentes, criados antes da coluna 'ativo' existir.
    try:
        cursor.execute("ALTER TABLE produtos ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1")
    except sqlite3.OperationalError:
        pass  # coluna já existe, nada a fazer

    # Migração pra bancos já existentes, criados antes da coluna de descrição normalizada existir.
    try:
        cursor.execute("ALTER TABLE produtos ADD COLUMN descricao_normalizada TEXT")
    except sqlite3.OperationalError:
        pass  # coluna já existe, nada a fazer

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fluxo_caixa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT DEFAULT (datetime('now', 'localtime')),
            tipo TEXT NOT NULL,
            valor REAL NOT NULL,
            operador TEXT NOT NULL,
            justificativa TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT DEFAULT (datetime('now', 'localtime')),
            total REAL NOT NULL,
            forma_pagamento TEXT NOT NULL,
            operador TEXT NOT NULL,
            estornada INTEGER NOT NULL DEFAULT 0,
            data_estorno TEXT,
            motivo_estorno TEXT
        )
    """)

    # Migração pra bancos já existentes, criados antes das colunas de estorno existirem.
    for coluna_sql in (
        "ALTER TABLE vendas ADD COLUMN estornada INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE vendas ADD COLUMN data_estorno TEXT",
        "ALTER TABLE vendas ADD COLUMN motivo_estorno TEXT",
    ):
        try:
            cursor.execute(coluna_sql)
        except sqlite3.OperationalError:
            pass  # coluna já existe, nada a fazer

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS itens_pagamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            forma_pagamento TEXT NOT NULL,
            valor REAL NOT NULL,
            FOREIGN KEY (venda_id) REFERENCES vendas(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS itens_venda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            codigo_barras TEXT NOT NULL,
            descricao TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            preco_unitario REAL NOT NULL,
            FOREIGN KEY (venda_id) REFERENCES vendas(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimentacoes_estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT DEFAULT (datetime('now', 'localtime')),
            codigo_barras TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            tipo_movimentacao TEXT NOT NULL,
            justificativa TEXT,
            FOREIGN KEY (codigo_barras) REFERENCES produtos(codigo_barras)
        )
    """)

    conn.commit()

    # Atualiza a coluna de descrição normalizada para todos os produtos já existentes.
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT codigo_barras, descricao FROM produtos")
        for codigo_barras, descricao in cursor.fetchall():
            cursor.execute(
                "UPDATE produtos SET descricao_normalizada = ? WHERE codigo_barras = ?",
                (_normalizar_texto(descricao), codigo_barras)
            )
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            cursor.close()
        except Exception:
            pass

    conn.close()
    print("Banco recriado com sucesso!")

    # Tenta criar a tabela FTS para busca textual (mais rápida e sem acentos)
    try:
        conn = db_conectar()
        cur = conn.cursor()
        # Cria a tabela virtual FTS5 se suportada pelo SQLite da plataforma.
        # Usamos tokenize unicode61 com remove_diacritics=2 para ignorar acentos.
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS produtos_fts
            USING fts5(descricao, codigo_barras UNINDEXED, tokenize='unicode61 remove_diacritics 2');
        """)
        # Popula a tabela FTS a partir dos produtos já existentes (versão inicial).
        cur.execute("DELETE FROM produtos_fts")
        cur.execute("INSERT INTO produtos_fts(descricao, codigo_barras) SELECT descricao, codigo_barras FROM produtos WHERE ativo = 1")
        conn.commit()
    except Exception:
        # Se o SQLite da plataforma não oferecer FTS5, ignoramos silenciosamente.
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# Helpers para manter índice FTS (quando disponível)
# ============================================================
def _fts_insert(codigo_barras, descricao):
    try:
        conn = db_conectar()
        cur = conn.cursor()
        cur.execute("INSERT INTO produtos_fts(descricao, codigo_barras) VALUES (?, ?)", (descricao, codigo_barras))
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _fts_update(codigo_barras, descricao):
    try:
        conn = db_conectar()
        cur = conn.cursor()
        cur.execute("DELETE FROM produtos_fts WHERE codigo_barras = ?", (codigo_barras,))
        cur.execute("INSERT INTO produtos_fts(descricao, codigo_barras) VALUES (?, ?)", (descricao, codigo_barras))
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _fts_delete(codigo_barras):
    try:
        conn = db_conectar()
        cur = conn.cursor()
        cur.execute("DELETE FROM produtos_fts WHERE codigo_barras = ?", (codigo_barras,))
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# PRODUTOS / ESTOQUE
# ============================================================

def db_produto_buscar(codigo):
    """Retorna um produto ATIVO (usado no PDV/vendas) ou None.
    Produto inativado não aparece aqui — não pode ser vendido nem recadastrado até ser reativado."""
    linha = db_buscar_um("""
        SELECT codigo_barras, descricao, preco_venda, estoque_atual
        FROM produtos
        WHERE codigo_barras = ? AND ativo = 1
    """, (codigo,))
    if not linha:
        return None
    return {
        "codigo_barras": linha[0],
        "descricao": linha[1],
        "preco_venda": linha[2],
        "estoque_atual": linha[3],
    }


def db_backup(pasta="backups", manter=100):
    """Copia o banco inteiro para backups/emporio_pdv_AAAA-MM-DD_HHMMSS.db.
    Usa a API de backup do próprio SQLite (segura mesmo com o sistema em uso, ao contrário
    de copiar o arquivo na mão). Mantém apenas os N backups mais recentes.
    'manter=100' são os 100 últimos FECHAMENTOS de caixa (não dias): com 2 turnos/dia
    isso dá ~50 dias de histórico. Cada backup é uma cópia integral do banco.
    Retorna (sucesso, caminho_ou_erro)."""
    import os
    import glob
    from datetime import datetime

    try:
        os.makedirs(pasta, exist_ok=True)
        carimbo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        destino = os.path.join(pasta, f"emporio_pdv_{carimbo}.db")

        origem = db_conectar()
        try:
            copia = sqlite3.connect(destino)
            try:
                origem.backup(copia)
            finally:
                copia.close()
        finally:
            origem.close()

        # Rotação: remove os backups mais antigos, mantendo os 'manter' últimos
        arquivos = sorted(glob.glob(os.path.join(pasta, "emporio_pdv_*.db")))
        for antigo in arquivos[:-manter]:
            try:
                os.remove(antigo)
            except OSError:
                pass

        return True, destino
    except Exception as e:
        print(f"ERRO NO BACKUP: {e}")
        return False, str(e)


def _normalizar_texto(texto):
    """Remove acentos e baixa pra minúsculas — permite que 'Agua' encontre 'Água'
    e 'ACUCAR' encontre 'Açúcar'. Essencial num catálogo em português."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def db_produto_buscar_por_texto(termo, limite=12):
    """Busca produtos ATIVOS por código de barras exato OU por trecho da descrição.
    Implementação otimizada: prioridade para código exato; caso contrário usa
    uma query SQL com `LIKE` e `LIMIT`, evitando trazer todo o catálogo para
    a filtragem em Python (melhora muito a performance em catálogos grandes).
    Observação: LIKE é sensível a acentos no SQLite por padrão; para suporte a
    busca sem acento, considere adicionar uma coluna normalizada ou usar FTS5.
    """
    def montar(l):
        return {
            "codigo_barras": l[0],
            "descricao": l[1],
            "preco_venda": l[2],
            "estoque_atual": l[3],
        }

    # 1) Código de barras exato tem prioridade absoluta (caso do leitor bipando)
    exato = db_buscar_um("""
        SELECT codigo_barras, descricao, preco_venda, estoque_atual
        FROM produtos WHERE codigo_barras = ? AND ativo = 1
    """, (termo,))
    if exato:
        return [montar(exato)]

    # 2) Busca por nome: usar SQL com LOWER(descricao) LIKE ? e LIMIT
    # Preferencialmente use FTS5 (se disponível) para busca rápida e sem acentos.
    try:
        # Monta busca prefixada para cada token: 'cervej' -> 'cervej*'
        tokens = [t + '*' for t in str(termo).strip().split() if t]
        fts_query = ' '.join(tokens) if tokens else termo
        termino_exato = termo.strip()
        termino_prefixo = termino_exato.lower() + '%'
        termino_contem = '%' + termino_exato.lower() + '%'

        rows = db_buscar_todos("""
            SELECT p.codigo_barras, p.descricao, p.preco_venda, p.estoque_atual
            FROM produtos p JOIN produtos_fts ON p.codigo_barras = produtos_fts.codigo_barras
            WHERE p.ativo = 1 AND produtos_fts MATCH ?
            ORDER BY
                CASE
                    WHEN lower(p.descricao) = lower(?) THEN 0
                    WHEN lower(p.descricao) LIKE ? THEN 1
                    WHEN lower(p.descricao) LIKE ? THEN 2
                    ELSE 3
                END,
                bm25(produtos_fts),
                lower(p.descricao)
            LIMIT ?
        """, (fts_query, termino_exato, termino_prefixo, termino_contem, limite))

        if rows:
            return [montar(l) for l in rows]
    except Exception:
        # Falha no FTS (p.ex. FTS5 não disponível) -> fallback para LIKE
        pass

    termo_like = f"%{str(termo).lower()}%"
    rows = db_buscar_todos("""
        SELECT codigo_barras, descricao, preco_venda, estoque_atual
        FROM produtos
        WHERE ativo = 1 AND lower(descricao) LIKE ?
        ORDER BY descricao
        LIMIT ?
    """, (termo_like, limite))

    return [montar(l) for l in rows]


def db_produto_buscar_qualquer(codigo):
    """Busca um produto independente de estar ativo — usado em fluxos administrativos
    (importação de XML, cadastro) que precisam saber se o código já existe, mesmo inativado."""
    linha = db_buscar_um("""
        SELECT codigo_barras, descricao, preco_venda, estoque_atual, ativo
        FROM produtos WHERE codigo_barras = ?
    """, (codigo,))
    if not linha:
        return None
    return {
        "codigo_barras": linha[0],
        "descricao": linha[1],
        "preco_venda": linha[2],
        "estoque_atual": linha[3],
        "ativo": bool(linha[4]),
    }


def db_produto_cadastrar(codigo, descricao, preco, estoque_min, estoque_atual):
    db_executar_query("""
        INSERT INTO produtos (codigo_barras, descricao, descricao_normalizada, preco_venda, estoque_minimo, estoque_atual, ativo)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, (codigo, descricao, _normalizar_texto(descricao), preco, estoque_min, estoque_atual))
    # Atualiza índice FTS (se disponível)
    _fts_insert(codigo, descricao)


def db_produto_reativar_com_dados(codigo, descricao, preco, estoque_min, estoque_atual):
    """Reativa um produto previamente inativado, atualizando seus dados com o que veio do formulário."""
    db_executar_query("""
        UPDATE produtos
        SET descricao = ?, descricao_normalizada = ?, preco_venda = ?, estoque_minimo = ?, estoque_atual = ?, ativo = 1
        WHERE codigo_barras = ?
    """, (descricao, _normalizar_texto(descricao), preco, estoque_min, estoque_atual, codigo))
    # Atualiza índice FTS (reativa/atualiza entrada)
    _fts_update(codigo, descricao)


def db_produto_atualizar_preco(codigo, novo_preco):
    """Atualiza somente o preço de venda de um produto já cadastrado."""
    db_executar_query(
        "UPDATE produtos SET preco_venda = ? WHERE codigo_barras = ?",
        (novo_preco, codigo)
    )


def db_produto_atualizar_descricao(codigo, nova_descricao):
    """Atualiza somente a descrição (nome) de um produto já cadastrado."""
    db_executar_query(
        "UPDATE produtos SET descricao = ?, descricao_normalizada = ? WHERE codigo_barras = ?",
        (nova_descricao, _normalizar_texto(nova_descricao), codigo)
    )
    # Sincroniza a mudança com o índice FTS
    _fts_update(codigo, nova_descricao)


def db_produto_definir_ativo(codigo, ativo):
    """Inativa (ativo=False) ou reativa (ativo=True) um produto. Nunca apaga a linha —
    preserva a integridade referencial com vendas/movimentações antigas."""
    db_executar_query(
        "UPDATE produtos SET ativo = ? WHERE codigo_barras = ?",
        (1 if ativo else 0, codigo)
    )
    # Atualiza índice FTS: remove se inativado, adiciona/atualiza se reativado
    if ativo:
        # Busca a descrição atual e insere no FTS
        linha = db_buscar_um("SELECT descricao FROM produtos WHERE codigo_barras = ?", (codigo,))
        if linha:
            _fts_update(codigo, linha[0])
    else:
        _fts_delete(codigo)


def db_produto_listar(incluir_inativos=False, limit=None, offset=0, termo=""):
    """Lista produtos já formatados como dicionário.
    Suporta paginação e busca por termo de texto usando FTS5 quando disponível.
    """
    termo = str(termo or "").strip()
    params = []

    if termo:
        tokens = [t + '*' for t in termo.split() if t]
        fts_query = ' '.join(tokens)
        termino_exato = termo
        termino_prefixo = termo.lower() + '%'
        termino_contem = '%' + termo.lower() + '%'

        sql = """
            SELECT p.codigo_barras, p.descricao, p.preco_venda, p.estoque_atual, p.estoque_minimo, p.ativo
            FROM produtos p JOIN produtos_fts ON p.codigo_barras = produtos_fts.codigo_barras
            WHERE produtos_fts MATCH ?
        """
        params.append(fts_query)

        if not incluir_inativos:
            sql += " AND p.ativo = 1"

        sql += """
            ORDER BY
                CASE
                    WHEN lower(p.descricao) = lower(?) THEN 0
                    WHEN lower(p.descricao) LIKE ? THEN 1
                    WHEN lower(p.descricao) LIKE ? THEN 2
                    ELSE 3
                END,
                bm25(f),
                lower(p.descricao)
        """
        params.extend([termino_exato, termino_prefixo, termino_contem])

        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
            if offset:
                sql += " OFFSET ?"
                params.append(offset)

        try:
            linhas = db_buscar_todos(sql, tuple(params))
        except sqlite3.OperationalError:
            # FTS não disponível; fallback para LIKE simples
            sql = """
                SELECT codigo_barras, descricao, preco_venda, estoque_atual, estoque_minimo, ativo
                FROM produtos
                WHERE lower(descricao) LIKE ?
            """
            params = [termino_contem]
            if not incluir_inativos:
                sql += " AND ativo = 1"
            sql += " ORDER BY descricao"
            if limit is not None:
                sql += " LIMIT ?"
                params.append(limit)
                if offset:
                    sql += " OFFSET ?"
                    params.append(offset)
            linhas = db_buscar_todos(sql, tuple(params))
    else:
        if incluir_inativos:
            sql = """
                SELECT codigo_barras, descricao, preco_venda, estoque_atual, estoque_minimo, ativo
                FROM produtos
                ORDER BY descricao
            """
        else:
            sql = """
                SELECT codigo_barras, descricao, preco_venda, estoque_atual, estoque_minimo, ativo
                FROM produtos
                WHERE ativo = 1
                ORDER BY descricao
            """
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
            if offset:
                sql += " OFFSET ?"
                params.append(offset)
        linhas = db_buscar_todos(sql, tuple(params))

    return [
        {
            "codigo_barras": row[0],
            "descricao": row[1],
            "preco_venda": row[2],
            "estoque_atual": row[3],
            "estoque_minimo": row[4],
            "ativo": bool(row[5]),
        }
        for row in linhas
    ]


def db_estoque_atualizar(codigo, quantidade, operacao):
    """operacao: 'ENTRADA' ou 'ESTORNO' somam ao estoque; qualquer outro valor ('SAIDA', 'AVARIA'...) subtrai."""
    sinal = "+" if operacao in ("ENTRADA", "ESTORNO") else "-"
    db_executar_query(f"""
        UPDATE produtos SET estoque_atual = estoque_atual {sinal} ?
        WHERE codigo_barras = ?
    """, (quantidade, codigo))


def db_estoque_critico():
    """Retorna lista de produtos com estoque abaixo (ou igual) ao mínimo."""
    return db_buscar_todos("""
        SELECT codigo_barras, descricao, estoque_atual, estoque_minimo
        FROM produtos
        WHERE estoque_atual <= estoque_minimo
    """)


def registrar_movimentacao(codigo, quantidade, tipo, justificativa=""):
    """Registra no histórico de movimentações e atualiza o saldo do produto."""
    db_executar_query("""
        INSERT INTO movimentacoes_estoque (codigo_barras, quantidade, tipo_movimentacao, justificativa)
        VALUES (?, ?, ?, ?)
    """, (codigo, quantidade, tipo, justificativa))
    db_estoque_atualizar(codigo, quantidade, tipo)


# ============================================================
# VENDAS
# ============================================================

def db_venda_registrar(total, pagamentos, operador, carrinho):
    """Insere a venda, os itens de pagamento (suporta fracionamento) e dá baixa no estoque,
    tudo em uma única transação.
    pagamentos: lista de dicts {"forma_pagamento": str, "valor": float} — nunca vazia.
    Retorna (sucesso: bool, mensagem_erro: str | None)."""
    conn = db_conectar()
    try:
        cursor = conn.cursor()

        # 'forma_pagamento' da venda é só um resumo pro cupom/telas antigas;
        # o detalhamento real (usado nos relatórios) mora em itens_pagamento.
        resumo_forma_pagamento = (
            pagamentos[0]["forma_pagamento"] if len(pagamentos) == 1 else "Fracionado"
        )

        cursor.execute(
            "INSERT INTO vendas (total, forma_pagamento, operador) VALUES (?, ?, ?)",
            (total, resumo_forma_pagamento, operador),
        )
        venda_id = cursor.lastrowid

        for pagamento in pagamentos:
            cursor.execute(
                "INSERT INTO itens_pagamento (venda_id, forma_pagamento, valor) VALUES (?, ?, ?)",
                (venda_id, pagamento["forma_pagamento"], pagamento["valor"]),
            )

        for item in carrinho:
            cursor.execute(
                "INSERT INTO itens_venda (venda_id, codigo_barras, descricao, quantidade, preco_unitario) VALUES (?, ?, ?, ?, ?)",
                (venda_id, item["codigo_barras"], item.get("descricao", ""), item["qty"], item.get("preco_venda", 0)),
            )
            cursor.execute(
                "UPDATE produtos SET estoque_atual = estoque_atual - ? WHERE codigo_barras = ?",
                (item["qty"], item["codigo_barras"]),
            )

        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        print(f"ERRO NO SQL: {e}")
        return False, str(e)
    finally:
        conn.close()


def db_venda_detalhes(venda_id):
    """Retorna o detalhe completo de uma venda: cabeçalho, itens vendidos e pagamentos usados.
    None se a venda não existir."""
    cabecalho = db_buscar_um("""
        SELECT id, data_hora, total, forma_pagamento, operador, estornada, data_estorno, motivo_estorno
        FROM vendas WHERE id = ?
    """, (venda_id,))
    if not cabecalho:
        return None

    itens = db_buscar_todos("""
        SELECT codigo_barras, descricao, quantidade, preco_unitario
        FROM itens_venda WHERE venda_id = ?
    """, (venda_id,))

    pagamentos = db_buscar_todos("""
        SELECT forma_pagamento, valor FROM itens_pagamento WHERE venda_id = ?
    """, (venda_id,))

    return {
        "id": cabecalho[0],
        "data_hora": cabecalho[1],
        "total": cabecalho[2],
        "forma_pagamento": cabecalho[3],
        "operador": cabecalho[4],
        "estornada": bool(cabecalho[5]),
        "data_estorno": cabecalho[6],
        "motivo_estorno": cabecalho[7],
        "itens": [
            {"codigo_barras": i[0], "descricao": i[1], "quantidade": i[2], "preco_unitario": i[3]}
            for i in itens
        ],
        "pagamentos": [{"forma_pagamento": p[0], "valor": p[1]} for p in pagamentos],
    }


def db_venda_estornar(venda_id, motivo=""):
    """Estorna uma venda: marca como estornada (nunca apaga), devolve as quantidades ao
    estoque e registra a movimentação de auditoria. Não pode estornar duas vezes.
    Retorna (sucesso: bool, mensagem_erro: str | None)."""
    conn = db_conectar()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT estornada FROM vendas WHERE id = ?", (venda_id,))
        linha = cursor.fetchone()
        if not linha:
            return False, "Venda não encontrada."
        if linha[0]:
            return False, "Essa venda já foi estornada anteriormente."

        cursor.execute(
            "UPDATE vendas SET estornada = 1, data_estorno = datetime('now','localtime'), motivo_estorno = ? WHERE id = ?",
            (motivo, venda_id),
        )

        cursor.execute("SELECT codigo_barras, quantidade FROM itens_venda WHERE venda_id = ?", (venda_id,))
        itens = cursor.fetchall()
        for codigo, quantidade in itens:
            cursor.execute(
                "INSERT INTO movimentacoes_estoque (codigo_barras, quantidade, tipo_movimentacao, justificativa) VALUES (?, ?, 'ESTORNO', ?)",
                (codigo, quantidade, f"Estorno da venda #{venda_id}" + (f" — {motivo}" if motivo else "")),
            )
            cursor.execute(
                "UPDATE produtos SET estoque_atual = estoque_atual + ? WHERE codigo_barras = ?",
                (quantidade, codigo),
            )

        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        print(f"ERRO NO SQL (estorno): {e}")
        return False, str(e)
    finally:
        conn.close()


def db_venda_totais_desde(data_hora):
    """Retorna (faturamento_dinheiro, faturamento_eletronico, faturamento_total, numero_vendas) desde data_hora.
    Vendas estornadas NÃO entram nesses totais (mas continuam existindo na tabela pra auditoria)."""
    por_metodo = db_buscar_um("""
        SELECT
            SUM(CASE WHEN ip.forma_pagamento = 'Dinheiro' THEN ip.valor ELSE 0 END),
            SUM(CASE WHEN ip.forma_pagamento IN ('Crédito', 'Débito', 'Pix', 'VR') THEN ip.valor ELSE 0 END)
        FROM itens_pagamento ip
        JOIN vendas v ON v.id = ip.venda_id
        WHERE v.data_hora >= ? AND v.estornada = 0
    """, (data_hora,))

    resumo = db_buscar_um(
        "SELECT SUM(total), COUNT(*) FROM vendas WHERE data_hora >= ? AND estornada = 0",
        (data_hora,)
    )

    fat_dinheiro = (por_metodo[0] if por_metodo else 0) or 0
    fat_eletronico = (por_metodo[1] if por_metodo else 0) or 0
    total_geral = (resumo[0] if resumo else 0) or 0
    numero_vendas = (resumo[1] if resumo else 0) or 0

    return (fat_dinheiro, fat_eletronico, total_geral, numero_vendas)

def db_fluxo_totais_desde(data_hora):
    """Retorna (total_suprimentos, total_sangrias) desde data_hora."""
    return db_buscar_um("""
        SELECT
            SUM(CASE WHEN tipo = 'SUPRIMENTO' THEN valor ELSE 0 END),
            SUM(CASE WHEN tipo = 'SANGRIA' THEN valor ELSE 0 END)
        FROM fluxo_caixa
        WHERE data_hora >= ? AND tipo IN ('SUPRIMENTO', 'SANGRIA')
    """, (data_hora,))


# ============================================================
# RELATÓRIOS (RF12/RF13 — consulta por período arbitrário)
# ============================================================

def db_vendas_periodo(data_inicio, data_fim, formas=None):
    """Lista vendas entre data_inicio e data_fim (inclusive), mais recentes primeiro.
    Inclui vendas estornadas (marcadas via 'estornada') — ficam visíveis pra auditoria,
    mas não entram nos totais de faturamento (ver db_venda_totais_desde).
    formas: lista opcional de formas de pagamento pra filtrar (considera qualquer venda
    que tenha USADO ao menos uma dessas formas, mesmo em pagamento fracionado)."""
    if formas:
        placeholders = ",".join("?" for _ in formas)
        return db_buscar_todos(f"""
            SELECT DISTINCT v.id, v.data_hora, v.total, v.forma_pagamento, v.operador, v.estornada
            FROM vendas v
            JOIN itens_pagamento ip ON ip.venda_id = v.id
            WHERE v.data_hora BETWEEN ? AND ? AND ip.forma_pagamento IN ({placeholders})
            ORDER BY v.data_hora DESC
        """, (data_inicio, data_fim, *formas))

    return db_buscar_todos("""
        SELECT id, data_hora, total, forma_pagamento, operador, estornada
        FROM vendas
        WHERE data_hora BETWEEN ? AND ?
        ORDER BY data_hora DESC
    """, (data_inicio, data_fim))


def db_totais_por_forma_pagamento(data_inicio, data_fim, formas=None):
    """Retorna [(forma_pagamento, total), ...] agregado a partir de itens_pagamento no período
    (funciona corretamente mesmo com vendas fracionadas em mais de uma forma).
    Exclui vendas estornadas. formas: lista opcional pra restringir quais métodos entram."""
    if formas:
        placeholders = ",".join("?" for _ in formas)
        return db_buscar_todos(f"""
            SELECT ip.forma_pagamento, SUM(ip.valor)
            FROM itens_pagamento ip
            JOIN vendas v ON v.id = ip.venda_id
            WHERE v.data_hora BETWEEN ? AND ? AND v.estornada = 0 AND ip.forma_pagamento IN ({placeholders})
            GROUP BY ip.forma_pagamento
            ORDER BY SUM(ip.valor) DESC
        """, (data_inicio, data_fim, *formas))

    return db_buscar_todos("""
        SELECT ip.forma_pagamento, SUM(ip.valor)
        FROM itens_pagamento ip
        JOIN vendas v ON v.id = ip.venda_id
        WHERE v.data_hora BETWEEN ? AND ? AND v.estornada = 0
        GROUP BY ip.forma_pagamento
        ORDER BY SUM(ip.valor) DESC
    """, (data_inicio, data_fim))


def db_fluxo_periodo(data_inicio, data_fim):
    """Lista lançamentos de SUPRIMENTO/SANGRIA no período, mais recentes primeiro."""
    return db_buscar_todos("""
        SELECT id, data_hora, tipo, valor, operador, justificativa
        FROM fluxo_caixa
        WHERE data_hora BETWEEN ? AND ? AND tipo IN ('SUPRIMENTO', 'SANGRIA')
        ORDER BY data_hora DESC
    """, (data_inicio, data_fim))


def db_extrato_caixa_periodo(data_inicio, data_fim, formas=None):
    """Extrato consolidado do período: vendas (entrada), suprimentos (entrada) e sangrias
    (saída) numa única linha do tempo, mais recentes primeiro. Vendas estornadas aparecem
    marcadas (campo 'estornada'), mas o valor mostrado é o original — pra dar transparência.
    formas: filtra as linhas de VENDA pela forma de pagamento usada; SUPRIMENTO/SANGRIA
    não têm forma de pagamento, então sempre aparecem independente do filtro."""
    if formas:
        placeholders = ",".join("?" for _ in formas)
        return db_buscar_todos(f"""
            SELECT v.data_hora, 'VENDA' AS tipo, v.total AS valor, v.operador, v.forma_pagamento AS detalhe, v.estornada
            FROM vendas v
            WHERE v.data_hora BETWEEN ? AND ?
              AND v.id IN (SELECT venda_id FROM itens_pagamento WHERE forma_pagamento IN ({placeholders}))

            UNION ALL

            SELECT data_hora, tipo, valor, operador, justificativa AS detalhe, 0 AS estornada
            FROM fluxo_caixa
            WHERE data_hora BETWEEN ? AND ? AND tipo IN ('SUPRIMENTO', 'SANGRIA')

            ORDER BY data_hora DESC
        """, (data_inicio, data_fim, *formas, data_inicio, data_fim))

    return db_buscar_todos("""
        SELECT data_hora, 'VENDA' AS tipo, total AS valor, operador, forma_pagamento AS detalhe, estornada
        FROM vendas
        WHERE data_hora BETWEEN ? AND ?

        UNION ALL

        SELECT data_hora, tipo, valor, operador, justificativa AS detalhe, 0 AS estornada
        FROM fluxo_caixa
        WHERE data_hora BETWEEN ? AND ? AND tipo IN ('SUPRIMENTO', 'SANGRIA')

        ORDER BY data_hora DESC
    """, (data_inicio, data_fim, data_inicio, data_fim))


def db_top_produtos_periodo(data_inicio, data_fim, limite=8):
    """Retorna [(descricao, quantidade_total), ...] dos produtos mais vendidos no período,
    excluindo vendas estornadas."""
    return db_buscar_todos("""
        SELECT iv.descricao, SUM(iv.quantidade) AS qtd
        FROM itens_venda iv
        JOIN vendas v ON v.id = iv.venda_id
        WHERE v.data_hora BETWEEN ? AND ? AND v.estornada = 0
        GROUP BY iv.codigo_barras, iv.descricao
        ORDER BY qtd DESC
        LIMIT ?
    """, (data_inicio, data_fim, limite))


def db_estornos_periodo(data_inicio, data_fim):
    """Lista as vendas estornadas cujo ESTORNO (não a venda original) caiu dentro do período —
    é o log de auditoria que responde 'quem estornou o quê, quando e por quê'."""
    return db_buscar_todos("""
        SELECT id, data_hora, total, operador, data_estorno, motivo_estorno
        FROM vendas
        WHERE estornada = 1 AND data_estorno BETWEEN ? AND ?
        ORDER BY data_estorno DESC
    """, (data_inicio, data_fim))


# ============================================================
# CAIXA (fluxo_caixa: ABERTURA / FECHAMENTO / SUPRIMENTO / SANGRIA)
# ============================================================

def db_caixa_registrar_fluxo(tipo, valor, operador, justificativa):
    """Insere um lançamento genérico no fluxo de caixa e retorna o id gerado."""
    cursor = db_executar_query("""
        INSERT INTO fluxo_caixa (tipo, valor, operador, justificativa)
        VALUES (?, ?, ?, ?)
    """, (tipo, valor, operador, justificativa))
    return cursor.lastrowid


def db_caixa_get_ultimo_status():
    """Retorna o 'tipo' do último lançamento do fluxo de caixa (ou None)."""
    resultado = db_buscar_um("SELECT tipo FROM fluxo_caixa ORDER BY id DESC LIMIT 1")
    return resultado[0] if resultado else None



def db_caixa_ultima_abertura():
    """Retorna (id, data_hora, valor, operador) da última ABERTURA (ou None).
    O 'id' é usado para comparações de ordem, porque data_hora tem precisão de apenas
    1 segundo e dois lançamentos no mesmo segundo ficariam ambíguos."""
    return db_buscar_um(
        """SELECT id, data_hora, valor, operador
           FROM fluxo_caixa WHERE tipo = 'ABERTURA'
           ORDER BY id DESC LIMIT 1"""
    )


def db_caixa_fechamento_apos(id_abertura):
    """Retorna a data_hora do FECHAMENTO posterior à abertura informada (ou None, se o
    caixa segue aberto). Compara por 'id' (AUTOINCREMENT, sempre crescente e único) e não
    por data_hora: abrir e fechar dentro do mesmo segundo faria a comparação por tempo
    falhar, e o sistema acharia que o caixa continua aberto."""
    resultado = db_buscar_um(
        """SELECT data_hora FROM fluxo_caixa
           WHERE tipo = 'FECHAMENTO' AND id > ?
           ORDER BY id DESC LIMIT 1""",
        (id_abertura,),
    )
    return resultado[0] if resultado else None


if __name__ == "__main__":
    inicializar_banco()