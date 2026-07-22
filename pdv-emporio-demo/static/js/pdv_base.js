// pdv_base.js - Contrato de Comunicação Front-End -> Back-End

const API = {
    caixa: {
        getStatus: () => fetch('/api/caixa/status').then(res => res.json()),
        abrir: (dados) => fetch('/api/caixa/abrir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        }).then(res => res.json()),
        fechar: (dados) => fetch('/api/caixa/fechar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        }).then(res => res.json()),
        getDadosAtuais: () => fetch('/api/caixa/dados_atuais').then(res => res.json())
    },
    fluxo: {
        sangria: (dados) => fetch('/api/fluxo/sangria', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        }).then(res => res.json()),
        suprimento: (dados) => fetch('/api/fluxo/suprimento', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        }).then(res => res.json())
    },
    vendas: {
        registrar: (dados) => fetch('/api/vendas', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        }).then(res => res.json()),
        estornar: (dados) => fetch('/api/venda/estornar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        }).then(res => res.json())
    },
    produtos: {
        buscar: (query) => fetch('/api/produto/' + String(query).trim()).then(res => res.json()),
        buscarTexto: (termo) => fetch('/api/produtos/busca?q=' + encodeURIComponent(String(termo).trim())).then(res => res.json())
    },
    estoque: {
        listar: (incluirInativos = false, limit = null, offset = 0, q = '') => {
            let qs = [];
            if (incluirInativos) qs.push('incluir_inativos=1');
            if (q) qs.push('q=' + encodeURIComponent(q));
            if (limit !== null && limit !== undefined) qs.push('limit=' + encodeURIComponent(limit));
            if (offset) qs.push('offset=' + encodeURIComponent(offset));
            const query = qs.length ? ('?' + qs.join('&')) : '';
            return fetch('/api/estoque/lista' + query).then(res => res.json());
        },
        cadastrar: (dados) => fetch('/api/produto-cadastrar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        }).then(res => res.json()),
        movimentar: (dados) => fetch('/api/estoque/movimentar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        }).then(res => res.json()),
        atualizarPreco: (dados) => fetch('/api/produto/atualizar-preco', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        }).then(res => res.json()),
        atualizarDescricao: (dados) => fetch('/api/produto/atualizar-descricao', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        }).then(res => res.json()),
        inativar: (dados) => fetch('/api/produto/inativar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        }).then(res => res.json()),
        reativar: (dados) => fetch('/api/produto/reativar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        }).then(res => res.json()),
        importarXml: (arquivo) => {
            // multipart/form-data: NÃO definir Content-Type manualmente,
            // o navegador precisa gerar o boundary sozinho.
            const formData = new FormData();
            formData.append('arquivo', arquivo);
            return fetch('/api/estoque/importar-xml', {
                method: 'POST',
                body: formData
            }).then(res => res.json());
        }
    },
    relatorios: {
        resumo: (inicio, fim, formas = []) => {
            const query = formas.length ? `&formas=${formas.map(encodeURIComponent).join(',')}` : '';
            return fetch(`/api/relatorios/resumo?inicio=${inicio}&fim=${fim}${query}`).then(res => res.json());
        },
        detalheVenda: (id) => fetch(`/api/relatorios/venda/${id}`).then(res => res.json())
    }
};

// Gerenciamento de Estado Local
const PDV_STATE = {
    operador: localStorage.getItem('pdv_operador') || 'Admin',
    setOperador: (nome) => localStorage.setItem('pdv_operador', nome),
    getOperador: () => localStorage.getItem('pdv_operador') || 'Admin'
};

// Função de Fechamento Global
async function dispararFechamentoGlobal() {
    if (typeof processarFechamentoCaixa === 'function') {
        await processarFechamentoCaixa();
    } else {
        window.location.href = '/';
    }
}

// Atalhos de teclado
document.addEventListener('keydown', function(event) {
    // Navegação entre telas (sempre ativa, em qualquer página)
    const atalhosNavegacao = { 'F1': '/', 'F2': '/estoque', 'F3': '/relatorios' };
    if (atalhosNavegacao[event.key]) {
        event.preventDefault();
        window.location.href = atalhosNavegacao[event.key];
        return;
    }

    // Fecha a tela de atalhos se estiver aberta
    if (event.key === 'Escape') {
        const overlay = document.getElementById('overlay-atalhos');
        if (overlay) { overlay.remove(); return; }
    }

    // Tela de atalhos disponíveis (mesma tecla abre e fecha)
    if (event.key === '?') {
        event.preventDefault();
        abrirTelaDeAtalhos();
        return;
    }

    // Atalhos de função — cada página define suas próprias funções globais
    // (atalhoF4, atalhoF6, atalhoF7, atalhoF8, atalhoF9). Se a página não
    // definir uma delas, a tecla simplesmente não faz nada nessa tela.
    const mapaFuncoes = { 'F4': 'atalhoF4', 'F6': 'atalhoF6', 'F7': 'atalhoF7', 'F8': 'atalhoF8', 'F9': 'atalhoF9' };
    const nomeFuncao = mapaFuncoes[event.key];
    if (nomeFuncao && typeof window[nomeFuncao] === 'function') {
        event.preventDefault();
        window[nomeFuncao]();
        return;
    }

    // Fallback universal pra "Finalizar Venda": alguns navegadores/SOs reservam o F6
    // pra focar a barra de endereço e não deixam a página bloquear isso. Ctrl+Enter
    // sempre funciona como alternativa, mesmo sem aparecer no botão.
    if (event.ctrlKey && event.key === 'Enter' && typeof window.atalhoF6 === 'function') {
        event.preventDefault();
        window.atalhoF6();
    }
});

// Tela (overlay) com os atalhos disponíveis na página atual.
// Cada página pode declarar window.ATALHOS_DESTA_TELA = [{tecla, acao}, ...]
// com os atalhos específicos dela; os globais (F1-F3, Esc, ?) já entram automaticamente.
function abrirTelaDeAtalhos() {
    const existente = document.getElementById('overlay-atalhos');
    if (existente) { existente.remove(); return; }

    const atalhosGlobais = [
        { tecla: 'F1', acao: 'Ir para Vendas' },
        { tecla: 'F2', acao: 'Ir para Estoque' },
        { tecla: 'F3', acao: 'Ir para Relatórios' },
        { tecla: 'Esc', acao: 'Fechar modal aberto' },
    ];
    const atalhos = atalhosGlobais.concat(window.ATALHOS_DESTA_TELA || []);

    const linhas = atalhos.map(a => `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:9px 0; border-bottom:1px solid rgba(255,255,255,0.1);">
            <span style="color:#e5e7eb; font-size:14px;">${a.acao}</span>
            <kbd style="background:#0f0f0f; border:1px solid #4b5563; border-radius:4px; padding:3px 10px; font-family:monospace; font-size:13px; color:#10b981; font-weight:700;">${a.tecla}</kbd>
        </div>`).join('');

    const overlay = document.createElement('div');
    overlay.id = 'overlay-atalhos';
    overlay.style.cssText = 'position:fixed; inset:0; background:rgba(0,0,0,0.75); z-index:99999; display:flex; align-items:center; justify-content:center;';
    overlay.innerHTML = `
        <div style="background:#111827; border:1px solid #333; border-radius:8px; padding:24px; max-width:380px; width:90%; box-shadow:0 10px 40px rgba(0,0,0,0.5); max-height:80vh; overflow-y:auto;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
                <h3 style="color:#fff; font-size:17px;">Atalhos de teclado</h3>
                <span style="cursor:pointer; color:#9ca3af; font-size:13px;" onclick="document.getElementById('overlay-atalhos').remove()">Fechar (Esc)</span>
            </div>
            ${linhas}
        </div>
    `;
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
}