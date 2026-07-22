import sqlite3
import xml.etree.ElementTree as ET
from flask import Flask, render_template, jsonify, request

from database import (
    db_produto_buscar,
    db_produto_buscar_qualquer,
    db_produto_buscar_por_texto,
    db_backup,
    db_produto_cadastrar,
    db_produto_reativar_com_dados,
    db_produto_atualizar_preco,
    db_produto_atualizar_descricao,
    db_produto_definir_ativo,
    db_produto_listar,
    db_estoque_atualizar,
    registrar_movimentacao,
    db_venda_registrar,
    db_venda_totais_desde,
    db_venda_detalhes,
    db_venda_estornar,
    db_fluxo_totais_desde,
    db_vendas_periodo,
    db_totais_por_forma_pagamento,
    db_fluxo_periodo,
    db_extrato_caixa_periodo,
    db_top_produtos_periodo,
    db_estornos_periodo,
    db_caixa_registrar_fluxo,
    db_caixa_get_ultimo_status,
    db_caixa_ultima_abertura,
    db_caixa_fechamento_apos,

)

app = Flask(__name__)

import demo_mode
demo_mode.ativar()


@app.context_processor
def inject_demo_mode():
    return {"demo_mode": demo_mode.esta_ativo()}

# ============================================================
# ONDE SALVAR OS BACKUPS
# ============================================================
# Por padrão, salva numa pasta "backups" ao lado do sistema (só no computador).
# Pra fazer o backup subir sozinho pra nuvem, troque o caminho abaixo pra dentro da
# pasta que o Google Drive / OneDrive já sincroniza automaticamente no computador.
# Exemplos (ajuste pro caminho real da sua máquina):
#   BACKUP_PASTA = r"C:\Users\Junior\Google Drive\Backups PDV Emporio"
#   BACKUP_PASTA = r"C:\Users\Junior\OneDrive\Backups PDV Emporio"
# Depois de trocar, todo fechamento de caixa já salva direto na pasta sincronizada —
# nenhum outro código precisa mudar.
BACKUP_PASTA = r"G:\Meu Drive\PDV Emporio"


def _strip_ns(tag):
    """Remove o namespace da NF-e de uma tag XML (ex: '{http://...}det' -> 'det')."""
    return tag.split("}")[-1] if "}" in tag else tag


def _parse_nfe_xml(conteudo_xml):
    """Extrai (codigo_barras, descricao, quantidade) de cada item <det><prod> de uma NF-e.
    Regra RF05: só extrai Código de Barras, Descrição e Quantidade — preço nunca vem do XML.
    Se o item não tiver GTIN/EAN ('SEM GTIN' ou vazio), usa o código interno da nota (cProd)
    como código de barras e sinaliza em 'codigo_interno' para o operador conferir depois."""
    root = ET.fromstring(conteudo_xml)
    itens = []
    for det in root.iter():
        if _strip_ns(det.tag) != "det":
            continue
        prod = next((c for c in det if _strip_ns(c.tag) == "prod"), None)
        if prod is None:
            continue

        campos = {_strip_ns(c.tag): (c.text or "").strip() for c in prod}
        cEAN = campos.get("cEAN", "")
        cProd = campos.get("cProd", "")
        usar_ean = bool(cEAN) and cEAN.upper() != "SEM GTIN"
        codigo = cEAN if usar_ean else cProd

        try:
            quantidade = round(float(campos.get("qCom", "0") or "0"))
        except ValueError:
            quantidade = 0

        itens.append({
            "codigo_barras": codigo,
            "descricao": campos.get("xProd", "").strip(),
            "quantidade": quantidade,
            "codigo_interno": not usar_ean,
        })
    return itens

# ---- ROTAS DO SISTEMA ----

@app.route("/")
def index():
    """Rota principal que abre a tela de vendas do seu PDV."""
    return render_template("pos_distribuidora_emporio.html")


@app.route("/estoque")
def pagina_estoque():
    return render_template("estoque.html")


@app.route("/relatorios")
def pagina_relatorios():
    return render_template("relatorios.html")


@app.route("/api/produtos/busca", methods=["GET"])
def api_buscar_produto_texto():
    """Busca por código de barras exato OU por trecho do nome (RF02).
    Caminho no plural de propósito: '/api/produto/busca' colidiria com a rota
    dinâmica '/api/produto/<codigo_barras>' logo abaixo."""
    termo = request.args.get("q", "").strip()
    if not termo:
        return jsonify({"sucesso": False, "mensagem": "Informe um termo de busca."}), 400

    resultados = db_produto_buscar_por_texto(termo)
    return jsonify({
        "sucesso": True,
        "resultados": resultados,
        "total": len(resultados),
        # O front usa isso pra decidir se oferece cadastro rápido: só faz sentido
        # oferecer quando o operador bipou/digitou algo que parece um código de barras.
        "parece_codigo": termo.isdigit(),
    })


@app.route("/api/produto/<codigo_barras>", methods=["GET"])
def api_buscar_produto(codigo_barras):
    """Rota que o JavaScript chama para consultar produtos."""
    produto = db_produto_buscar(codigo_barras)

    if produto:
        return jsonify({"sucesso": True, "produto": produto})

    return jsonify({"sucesso": False, "mensagem": "Produto não cadastrado!"}), 404


@app.route("/api/produto-cadastrar", methods=["POST"])
def api_cadastrar_produto():
    dados = request.get_json()
    try:
        existente = db_produto_buscar_qualquer(dados["codigo_barras"])
        if existente and not existente["ativo"]:
            # Código já existiu mas foi inativado: reativa e atualiza em vez de barrar como duplicado.
            db_produto_reativar_com_dados(
                dados["codigo_barras"],
                dados["descricao"],
                dados["preco_venda"],
                dados.get("estoque_minimo", 0),
                dados.get("estoque_atual", 0),
            )
            return jsonify({"sucesso": True, "mensagem": "Produto reativado e atualizado com sucesso!"})

        db_produto_cadastrar(
            dados["codigo_barras"],
            dados["descricao"],
            dados["preco_venda"],
            dados.get("estoque_minimo", 0),
            dados.get("estoque_atual", 0),
        )
        return jsonify({"sucesso": True, "mensagem": "Produto cadastrado com sucesso!"})
    except sqlite3.IntegrityError:
        return jsonify({"sucesso": False, "mensagem": "Este código de barras já está cadastrado!"}), 400
    except Exception as e:
        return jsonify({"sucesso": False, "mensagem": str(e)}), 500


@app.route("/api/produto/atualizar-descricao", methods=["POST"])
def api_atualizar_descricao():
    dados = request.get_json()
    try:
        descricao = dados["descricao"].strip()
        if not descricao:
            return jsonify({"sucesso": False, "mensagem": "Descrição não pode ficar vazia."}), 400
        db_produto_atualizar_descricao(dados["codigo_barras"], descricao)
        return jsonify({"sucesso": True})
    except Exception as e:
        return jsonify({"sucesso": False, "mensagem": str(e)}), 500


@app.route("/api/produto/inativar", methods=["POST"])
def api_inativar_produto():
    dados = request.get_json()
    try:
        db_produto_definir_ativo(dados["codigo_barras"], False)
        return jsonify({"sucesso": True, "mensagem": "Produto inativado — não aparece mais nas vendas."})
    except Exception as e:
        return jsonify({"sucesso": False, "mensagem": str(e)}), 500


@app.route("/api/produto/reativar", methods=["POST"])
def api_reativar_produto():
    dados = request.get_json()
    try:
        db_produto_definir_ativo(dados["codigo_barras"], True)
        return jsonify({"sucesso": True, "mensagem": "Produto reativado."})
    except Exception as e:
        return jsonify({"sucesso": False, "mensagem": str(e)}), 500


@app.route("/api/produto/atualizar-preco", methods=["POST"])
def api_atualizar_preco():
    dados = request.get_json()
    try:
        codigo = dados["codigo_barras"]
        preco = float(dados["preco_venda"])
        if preco < 0:
            return jsonify({"sucesso": False, "mensagem": "Preço não pode ser negativo."}), 400
        db_produto_atualizar_preco(codigo, preco)
        return jsonify({"sucesso": True})
    except Exception as e:
        return jsonify({"sucesso": False, "mensagem": str(e)}), 500


@app.route("/api/estoque/importar-xml", methods=["POST"])
def api_importar_xml():
    if "arquivo" not in request.files:
        return jsonify({"sucesso": False, "mensagem": "Nenhum arquivo enviado."}), 400

    arquivo = request.files["arquivo"]
    if not arquivo.filename.lower().endswith(".xml"):
        return jsonify({"sucesso": False, "mensagem": "Envie um arquivo .xml de Nota Fiscal."}), 400

    try:
        itens = _parse_nfe_xml(arquivo.read())
    except ET.ParseError:
        return jsonify({"sucesso": False, "mensagem": "Não foi possível ler o XML. Verifique se é uma NF-e válida."}), 400

    if not itens:
        return jsonify({"sucesso": False, "mensagem": "Nenhum item <det> encontrado no XML."}), 400

    criados, atualizados, avisos = [], [], []

    for item in itens:
        codigo = item["codigo_barras"]
        if not codigo:
            avisos.append(f"Item \"{item['descricao']}\" sem código de barras nem código interno — ignorado.")
            continue

        if item["codigo_interno"]:
            avisos.append(
                f"\"{item['descricao']}\" não tem GTIN/EAN na nota — foi importado usando o código interno "
                f"da NF ({codigo}). Confira antes de vender por leitor de código de barras."
            )

        existente = db_produto_buscar_qualquer(codigo)
        if existente and existente["ativo"]:
            # Produto já cadastrado e ativo: só entra com a quantidade, nunca mexe em descrição/preço.
            registrar_movimentacao(codigo, item["quantidade"], "ENTRADA", "Importação de XML de NF")
            atualizados.append(f"{existente['descricao']} (+{item['quantidade']})")
        elif existente and not existente["ativo"]:
            # Produto existia mas estava inativado: reativa (chegou de novo numa NF) e dá entrada.
            db_produto_definir_ativo(codigo, True)
            registrar_movimentacao(codigo, item["quantidade"], "ENTRADA", "Importação de XML de NF (reativado)")
            avisos.append(f"\"{existente['descricao']}\" estava inativado e foi reativado por essa importação.")
            atualizados.append(f"{existente['descricao']} (+{item['quantidade']}, reativado)")
        else:
            # Produto novo: entra com preço 0 (placeholder) — precisa ser definido manualmente (RF05).
            db_produto_cadastrar(codigo, item["descricao"], 0, 0, item["quantidade"])
            criados.append(item["descricao"])

    return jsonify({
        "sucesso": True,
        "criados": criados,
        "atualizados": atualizados,
        "avisos": avisos,
    })


@app.route("/api/estoque/lista", methods=["GET"])
def estoque_lista():
    incluir_inativos = request.args.get("incluir_inativos") == "1"
    try:
        limit = request.args.get("limit")
        offset = request.args.get("offset", 0)
        limit = int(limit) if limit is not None else None
        offset = int(offset)
    except Exception:
        return jsonify({"sucesso": False, "mensagem": "Parâmetros de paginação inválidos."}), 400

    termo = request.args.get("q", "").strip()
    produtos = db_produto_listar(incluir_inativos=incluir_inativos, limit=limit, offset=offset, termo=termo)
    return jsonify(produtos)


@app.route("/api/estoque/movimentar", methods=["POST"])
def api_movimentar():
    try:
        dados = request.get_json()
        registrar_movimentacao(
            dados["codigo_barras"],
            dados["quantidade"],
            dados["tipo"],
        )
        return jsonify({"sucesso": True})
    except Exception as e:
        print(f"Erro na movimentação: {e}")
        return jsonify({"sucesso": False, "mensagem": str(e)}), 500


@app.route("/api/vendas", methods=["POST"])
def registrar_venda():
    dados = request.get_json()
    carrinho = dados.get("carrinho", [])
    operador = dados.get("operador", "Desconhecido")
    total_venda = sum(item.get("preco_venda", 0) * item.get("qty", 1) for item in carrinho)

    # Suporta pagamento fracionado (Pix + Dinheiro, etc). Mantém compatibilidade retroativa
    # com um payload antigo que mandasse só "forma_pagamento" (um único método).
    pagamentos = dados.get("pagamentos")
    if not pagamentos:
        forma_pagamento_legado = dados.get("forma_pagamento")
        if forma_pagamento_legado:
            pagamentos = [{"forma_pagamento": forma_pagamento_legado, "valor": total_venda}]

    if not carrinho:
        return jsonify({"sucesso": False, "mensagem": "Carrinho vazio."}), 400
    if not pagamentos:
        return jsonify({"sucesso": False, "mensagem": "Nenhuma forma de pagamento informada."}), 400

    soma_pagamentos = sum(p.get("valor", 0) for p in pagamentos)
    if soma_pagamentos < total_venda - 0.01:
        return jsonify({
            "sucesso": False,
            "mensagem": f"Pagamento incompleto: faltam R$ {total_venda - soma_pagamentos:.2f}."
        }), 400

    sucesso, erro = db_venda_registrar(total_venda, pagamentos, operador, carrinho)

    if sucesso:
        return jsonify({"sucesso": True})
    return jsonify({"sucesso": False, "mensagem": erro}), 500


@app.route("/api/caixa/abrir", methods=["POST"])
def abrir_caixa():
    """Rota que registra a abertura do caixa."""
    dados = request.get_json()
    operador = dados.get("operador")
    fundo_inicial = dados.get("fundo_inicial", 0)

    if not operador:
        return jsonify({"sucesso": False, "mensagem": "Operador é obrigatório!"}), 400

    try:
        caixa_id = db_caixa_registrar_fluxo("ABERTURA", fundo_inicial, operador, "Abertura de caixa")
        return jsonify({
            "sucesso": True,
            "mensagem": "Caixa aberto com sucesso!",
            "caixa_id": caixa_id,
        })
    except sqlite3.Error as e:
        print(f"Erro ao abrir caixa: {e}")
        return jsonify({"sucesso": False, "mensagem": f"Erro no banco: {e}"}), 500


@app.route("/api/caixa/fechar", methods=["POST"])
def fechar_caixa():
    dados = request.get_json()
    operador = dados.get("operador")
    valor_fechamento = dados.get("valor_fechamento")

    try:
        db_caixa_registrar_fluxo("FECHAMENTO", valor_fechamento, operador, "Fechamento de turno regular")

        # Backup automático a cada fechamento de turno. Se falhar, o fechamento continua
        # válido — o backup é uma proteção extra, não pode derrubar a operação do caixa.
        backup_ok, backup_info = db_backup(pasta=BACKUP_PASTA)
        if not backup_ok:
            print(f"AVISO: fechamento gravado, mas o backup falhou: {backup_info}")

        return jsonify({
            "sucesso": True,
            "backup_ok": backup_ok,
            "backup_arquivo": backup_info if backup_ok else None,
        })
    except Exception as e:
        print(f"Erro ao fechar caixa: {e}")
        return jsonify({"sucesso": False, "mensagem": str(e)}), 500


@app.route("/api/fluxo/suprimento", methods=["POST"])
def realizar_suprimento():
    try:
        dados = request.get_json()
        valor = float(dados.get("valor", 0))
        operador = dados.get("operador", "Operador Padrão")
        justificativa = dados.get("justificativa", "Suprimento de troco")

        if valor <= 0:
            return jsonify({"sucesso": False, "mensagem": "Valor deve ser maior que zero."}), 400

        db_caixa_registrar_fluxo("SUPRIMENTO", valor, operador, justificativa)
        return jsonify({"sucesso": True, "mensagem": "Suprimento registrado com sucesso!"})
    except Exception as e:
        return jsonify({"sucesso": False, "mensagem": str(e)}), 500


@app.route("/api/fluxo/sangria", methods=["POST"])
def realizar_sangria():
    try:
        dados = request.get_json()
        valor = float(dados.get("valor", 0))
        operador = dados.get("operador", "Operador Padrão")
        justificativa = dados.get("justificativa", "")

        if valor <= 0:
            return jsonify({"sucesso": False, "mensagem": "Valor deve ser maior que zero."}), 400
        if not justificativa.strip():
            return jsonify({"sucesso": False, "mensagem": "A justificativa é obrigatória para sangrias."}), 400

        db_caixa_registrar_fluxo("SANGRIA", valor, operador, justificativa)
        return jsonify({"sucesso": True, "mensagem": "Sangria realizada com sucesso!"})
    except Exception as e:
        return jsonify({"sucesso": False, "mensagem": str(e)}), 500


@app.route("/api/relatorios/resumo", methods=["GET"])
def api_relatorio_resumo():
    """Query params: inicio=YYYY-MM-DD, fim=YYYY-MM-DD, formas=Dinheiro,Pix (opcional).
    Devolve vendas do período, totais por forma de pagamento, lançamentos de fluxo
    (suprimento/sangria), produtos mais vendidos, estornos e um resumo consolidado —
    base do RF12 + RF13."""
    inicio_str = request.args.get("inicio")
    fim_str = request.args.get("fim")
    formas_str = request.args.get("formas", "").strip()
    formas = [f for f in formas_str.split(",") if f] if formas_str else None

    if not inicio_str or not fim_str:
        return jsonify({"sucesso": False, "mensagem": "Informe 'inicio' e 'fim' (YYYY-MM-DD)."}), 400

    # Amplia pro range completo dos dias, já que data_hora tem hora:minuto:segundo.
    data_inicio = f"{inicio_str} 00:00:00"
    data_fim = f"{fim_str} 23:59:59"

    try:
        vendas = db_vendas_periodo(data_inicio, data_fim, formas)
        vendas_json = [
            {"id": v[0], "data_hora": v[1], "total": v[2], "forma_pagamento": v[3], "operador": v[4], "estornada": bool(v[5])}
            for v in vendas
        ]

        por_forma = db_totais_por_forma_pagamento(data_inicio, data_fim, formas)
        por_forma_json = [{"forma_pagamento": f[0], "total": f[1] or 0} for f in por_forma]

        fluxo = db_fluxo_periodo(data_inicio, data_fim)
        fluxo_json = [
            {"id": f[0], "data_hora": f[1], "tipo": f[2], "valor": f[3], "operador": f[4], "justificativa": f[5]}
            for f in fluxo
        ]

        extrato = db_extrato_caixa_periodo(data_inicio, data_fim, formas)
        extrato_json = [
            {"data_hora": e[0], "tipo": e[1], "valor": e[2], "operador": e[3], "detalhe": e[4], "estornada": bool(e[5])}
            for e in extrato
        ]

        top_produtos = db_top_produtos_periodo(data_inicio, data_fim)
        top_produtos_json = [{"descricao": p[0], "quantidade": p[1] or 0} for p in top_produtos]

        estornos = db_estornos_periodo(data_inicio, data_fim)
        estornos_json = [
            {"id": e[0], "data_hora": e[1], "total": e[2], "operador": e[3], "data_estorno": e[4], "motivo_estorno": e[5]}
            for e in estornos
        ]

        vendas_validas = [v for v in vendas_json if not v["estornada"]]
        faturamento_total = sum(v["total"] for v in vendas_validas)
        numero_vendas = len(vendas_validas)
        ticket_medio = (faturamento_total / numero_vendas) if numero_vendas else 0
        total_suprimentos = sum(f["valor"] for f in fluxo_json if f["tipo"] == "SUPRIMENTO")
        total_sangrias = sum(f["valor"] for f in fluxo_json if f["tipo"] == "SANGRIA")

        return jsonify({
            "sucesso": True,
            "vendas": vendas_json,
            "por_forma_pagamento": por_forma_json,
            "fluxo": fluxo_json,
            "extrato": extrato_json,
            "top_produtos": top_produtos_json,
            "estornos": estornos_json,
            "resumo": {
                "faturamento_total": faturamento_total,
                "numero_vendas": numero_vendas,
                "ticket_medio": ticket_medio,
                "total_suprimentos": total_suprimentos,
                "total_sangrias": total_sangrias,
            }
        })
    except Exception as e:
        return jsonify({"sucesso": False, "mensagem": str(e)}), 500


@app.route("/api/relatorios/venda/<int:venda_id>", methods=["GET"])
def api_venda_detalhes(venda_id):
    detalhes = db_venda_detalhes(venda_id)
    if not detalhes:
        return jsonify({"sucesso": False, "mensagem": "Venda não encontrada."}), 404
    return jsonify({"sucesso": True, "venda": detalhes})


@app.route("/api/venda/estornar", methods=["POST"])
def api_venda_estornar():
    dados = request.get_json()
    venda_id = dados.get("venda_id")
    motivo = (dados.get("motivo") or "").strip()

    if not venda_id:
        return jsonify({"sucesso": False, "mensagem": "Informe 'venda_id'."}), 400

    sucesso, erro = db_venda_estornar(venda_id, motivo)
    if sucesso:
        return jsonify({"sucesso": True, "mensagem": "Venda estornada com sucesso."})
    return jsonify({"sucesso": False, "mensagem": erro}), 400


@app.route("/api/caixa/status", methods=["GET"])
def status_caixa():
    try:
        ultimo_tipo = db_caixa_get_ultimo_status()
        esta_aberto = ultimo_tipo == "ABERTURA"
        return jsonify({"aberto": esta_aberto})
    except Exception as e:
        print(f"Erro no status: {e}")
        return jsonify({"aberto": False, "erro": str(e)}), 500


@app.route("/api/caixa/dados_atuais", methods=["GET"])
def api_caixa_dados_atuais():
    try:
        abertura = db_caixa_ultima_abertura()
        if not abertura:
            return jsonify({"aberto": False})

        id_abertura, data_abertura, fundo, operador = abertura

        # Se houve um fechamento após a última abertura, o caixa está fechado.
        # Compara por id (e não por data_hora) para não falhar quando a abertura e o
        # fechamento caem dentro do mesmo segundo.
        if db_caixa_fechamento_apos(id_abertura):
            return jsonify({"aberto": False})

        totais = db_venda_totais_desde(data_abertura)
        fluxo = db_fluxo_totais_desde(data_abertura)

        return jsonify({
            "aberto": True,
            "operador": operador,
            "fundo": fundo,
            "data_abertura": data_abertura,   # <- novo
            "faturamento_dinheiro": totais[0] or 0,
            "faturamento_eletronico": totais[1] or 0,
            "faturamento_turno": totais[2] or 0,
            "numero_vendas": totais[3] or 0,
            "suprimentos": fluxo[0] or 0,      # <- usado no ponto 2, já adianto aqui
            "sangrias": fluxo[1] or 0,
        })
    except Exception as e:
        return jsonify({"aberto": False, "erro": str(e)}), 500


if __name__ == "__main__":
    # debug=False: em uso real, um erro mostra só uma mensagem genérica pro usuário,
    # não o código-fonte nem um console interativo. Os detalhes continuam indo pro
    # terminal onde o servidor está rodando (pra você conseguir investigar depois).
    app.run(debug=False)