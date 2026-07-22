<div align="center">

# 🧾 Sistema PDV Empório

**Sistema de ponto de venda completo — do levantamento de requisitos à operação em produção real**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-FTS5-07405E?style=flat-square&logo=sqlite&logoColor=white)](https://sqlite.org)
[![Tests](https://img.shields.io/badge/tests-72%20passing-brightgreen?style=flat-square)](#-testes)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

[![Demo ao vivo](https://img.shields.io/badge/🔴_DEMO_AO_VIVO-pdv--demo.onrender.com-7c3aed?style=for-the-badge)](https://pdv-demo.onrender.com)

🇧🇷 [Português](#-sobre-o-projeto) &nbsp;|&nbsp; 🇺🇸 [English](#-about-the-project)

</div>

> ⚠️ **Este é um repositório de demonstração.** É uma versão sanitizada de um sistema real, desenvolvido e entregue para uma distribuidora de bebidas. Nenhum dado de cliente, produto ou venda real está incluído aqui — a demo roda com produtos fictícios e reseta o banco automaticamente a cada 3 horas.

---

## 🇧🇷 Sobre o projeto

Sistema PDV desenvolvido sob contrato real, a partir da observação de um problema operacional concreto: vendas sendo registradas à mão, em caderno, sem controle de estoque ou fluxo de caixa. Projeto conduzido de ponta a ponta — levantamento de requisitos, modelagem de dados, implementação, testes automatizados e entrega — usando uma metodologia de **Spec-Driven Development**: a especificação formal (requisitos, regras de negócio, modelo de dados) é escrita antes do código e usada para validar cada entrega.

**[→ Testar a demo ao vivo](https://pdv-demo.onrender.com)** *(pode levar ~30s para "acordar" no primeiro acesso — plano gratuito)*

### ✨ Funcionalidades

- Controle de abertura/fechamento de caixa, com trava de acesso à tela de vendas
- Busca de produto por código de barras ou nome (com normalização de acentos)
- Carrinho dinâmico com edição de item, quantidade e preço em tempo real
- Pagamento fracionado — uma venda dividida em múltiplas formas (Pix + Dinheiro + Cartão)
- Estorno de venda com trilha de auditoria (nada é apagado, tudo fica rastreável)
- Importação de estoque via XML de nota fiscal
- Movimentação manual de estoque (avarias, devoluções, entradas)
- Relatórios financeiros por período e forma de pagamento
- Impressão de cupom (formatado para impressora térmica 58/80mm)
- Operação 100% via atalhos de teclado (F1–F9), sem depender de mouse

### 🏗️ Arquitetura

```
Front-end (JS puro, sem framework) ──fetch──► API REST Flask ──► SQLite (arquivo único)
```

| Decisão | Por quê |
|---|---|
| SQLite em vez de Postgres/MySQL | Caixa único, sem servidor externo, sem depender de internet — banco = 1 arquivo |
| Chave primária = código de barras | É assim que o fluxo real busca o produto (leitor de código de barras) |
| Nenhum `DELETE` físico no schema | Toda remoção é lógica (`ativo`, `estornada`) — histórico nunca se perde, pensado para auditoria |
| Front-end sem framework | Sistema pequeno, mantido por uma pessoa só, sem build step |

**Modelo de dados:** 6 tabelas — `produtos`, `vendas`, `itens_venda`, `itens_pagamento`, `fluxo_caixa`, `movimentacoes_estoque` — com pagamento fracionado suportado via tabela dedicada e trilha de auditoria completa.

### 🔌 API REST

22 endpoints, organizados por domínio:

| Domínio | Endpoints |
|---|---|
| Caixa | `GET /api/caixa/status`, `POST /abrir`, `POST /fechar`, `GET /dados_atuais` |
| Vendas | `POST /api/vendas`, `POST /api/venda/estornar` |
| Produtos | `GET /api/produto/<codigo>`, `GET /api/produtos/busca`, `POST /api/produto-cadastrar`, `atualizar-preco`, `atualizar-descricao`, `inativar`, `reativar` |
| Estoque | `GET /api/estoque/lista`, `POST /movimentar`, `POST /importar-xml` |
| Fluxo de caixa | `POST /api/fluxo/sangria`, `POST /suprimento` |
| Relatórios | `GET /api/relatorios/resumo`, `GET /api/relatorios/venda/<id>` |

### 🧪 Testes

**72 testes automatizados, 0 falhas**, cobrindo os 16 requisitos funcionais, 4 não funcionais e 5 regras de negócio documentados. Alguns exemplos do que é validado:

- Estorno bloqueado em duplicidade
- Alteração de preço no carrinho não sobrescreve o preço cadastrado do produto (regra de negócio)
- Importação de XML soma quantidade em produto existente, mas não sobrescreve preço
- Uma condição de corrida real no status do caixa foi identificada e corrigida (comparação por ID sequencial em vez de timestamp)

### 🖥️ Rodando localmente

```bash
git clone https://github.com/Brisolaa/pdv-demo.git
cd pdv-demo
pip install -r requirements.txt
python app.py
```

Acesse `http://127.0.0.1:5000`. O banco SQLite é criado automaticamente na primeira execução.

### 🎭 Sobre o modo demo

O ambiente publicado em [pdv-demo.onrender.com](https://pdv-demo.onrender.com) roda com uma variável de ambiente (`DEMO_MODE=true`) que:
- Popula o banco com produtos fictícios (não o catálogo real do cliente)
- Reseta os dados automaticamente a cada 3 horas
- Exibe um aviso visível de que é um ambiente de demonstração

Esse comportamento fica completamente inativo sem a variável — é assim que o sistema real roda em produção, sem nenhuma dessas camadas extras.

### 👤 Autor

**Felipe Brisola** — [LinkedIn](https://linkedin.com/in/felipebrisola/) · [GitHub](https://github.com/Brisolaa) · brisola.dev@gmail.com

---
---

## 🇺🇸 About the project

A point-of-sale system built under a real contract, starting from a concrete operational problem: sales being tracked by hand, in a notebook, with no inventory or cash-flow control. Built end-to-end — requirements gathering, data modeling, implementation, automated testing, and delivery — using a **Spec-Driven Development** approach: the formal specification (requirements, business rules, data model) is written before the code and used to validate every delivery.

**[→ Try the live demo](https://pdv-demo.onrender.com)** *(may take ~30s to wake up on first load — free tier)*

### ✨ Features

- Cash register open/close flow, gating access to the sales screen
- Product lookup by barcode or name (accent-insensitive search)
- Dynamic cart with real-time item, quantity, and price editing
- Split payments — a single sale divided across multiple methods (Pix + Cash + Card)
- Sale reversal with a full audit trail (nothing is deleted, everything stays traceable)
- Inventory import from invoice XML files
- Manual stock movement (damage, returns, incoming stock)
- Financial reports by period and payment method
- Receipt printing (formatted for 58/80mm thermal printers)
- 100% keyboard-driven operation (F1–F9), no mouse required

### 🏗️ Architecture

```
Front-end (vanilla JS, no framework) ──fetch──► Flask REST API ──► SQLite (single file)
```

| Decision | Why |
|---|---|
| SQLite over Postgres/MySQL | Single-register operation, no external server, no internet dependency — the database is one file |
| Barcode as primary key | Matches how the real workflow looks up a product (barcode scanner) |
| No physical `DELETE` in the schema | Every removal is logical (`ativo`, `estornada`) — history is never lost, built for auditability |
| No front-end framework | Small system maintained by one person, no build step |

**Data model:** 6 tables — `produtos`, `vendas`, `itens_venda`, `itens_pagamento`, `fluxo_caixa`, `movimentacoes_estoque` — with split payments supported via a dedicated table and a full audit trail.

### 🔌 REST API

22 endpoints across: cash register, sales, products, inventory, cash flow, and reports (see the Portuguese section above for the full table — same endpoints).

### 🧪 Testing

**72 automated tests, 0 failures**, covering all 16 functional requirements, 4 non-functional requirements, and 5 business rules. Notably includes a real concurrency bug that was found and fixed (timestamp-based comparison replaced with sequential ID comparison for cash-register status).

### 🖥️ Running locally

```bash
git clone https://github.com/Brisolaa/pdv-demo.git
cd pdv-demo
pip install -r requirements.txt
python app.py
```

Visit `http://127.0.0.1:5000`. The SQLite database is created automatically on first run.

### 🎭 About demo mode

The environment at [pdv-demo.onrender.com](https://pdv-demo.onrender.com) runs with an environment variable (`DEMO_MODE=true`) that seeds fictional products, resets data every 3 hours, and shows a visible demo banner. This behavior is entirely inactive without that variable — which is exactly how the real production system runs, with none of these extra layers.

### 👤 Author

**Felipe Brisola** — [LinkedIn](https://linkedin.com/in/felipebrisola/) · [GitHub](https://github.com/Brisolaa) · brisola.dev@gmail.com
