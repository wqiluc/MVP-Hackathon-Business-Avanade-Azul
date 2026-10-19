import { RISCO_ALTO, SCORE_ALTO_VALOR, TIERS } from '../configuracao/fidelidade';
import { PERSONA_IDS } from '../configuracao/personas';
import { CLIENTES, DATA_REFERENCIA, MESES } from '../dados/sinteticos/gerarClientes';
import type { Cliente, ClienteResumo, FiltroClientes, ModeloInfo, ResumoDashboard } from '../tipos/crm';
import type { FonteDeDadosCrm } from './fonteDeDados';

function filtrar(filtro: FiltroClientes = {}): Cliente[] {
  return CLIENTES.filter(
    (c) => (!filtro.persona || c.persona === filtro.persona) && (!filtro.tier || c.tier === filtro.tier),
  );
}

function resumir(c: Cliente): ClienteResumo {
  return {
    id: c.id,
    nome: c.nome,
    tier: c.tier,
    persona: c.persona,
    aeroportoBase: c.aeroportoBase,
    clvProjetado: c.clvProjetado,
    scoreValor: c.scoreValor,
    riscoEvasao: c.riscoEvasao,
    proximaAcao: c.proximaAcao.titulo,
  };
}

const esperar = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const MODELO_SIMULADO: ModeloInfo = {
  nome: 'Heurística sintética demonstrativa',
  versao: '—',
  plataforma: 'MLflow',
  status: 'aguardando-registro',
  metaAcuracia: null,
  acuracia: null,
  auc: null,
  treinadoEm: null,
};

const media = (valores: number[]) => (valores.length ? valores.reduce((a, b) => a + b, 0) / valores.length : 0);

// Agregações que, em produção, viriam prontas de views da camada Ouro.
// `semFiltroPersona` alimenta o painel de personas, que funciona como seletor.
function calcularResumo(clientes: Cliente[], semFiltroPersona: Cliente[]): ResumoDashboard {
  const atritos = new Map<string, number>();
  for (const c of clientes) {
    for (const i of c.interacoes) {
      if (i.sentimento === 'negativo') atritos.set(i.tema, (atritos.get(i.tema) ?? 0) + 1);
    }
  }

  return {
    dataReferencia: DATA_REFERENCIA,
    totalClientes: clientes.length,
    clientesAltoValor: clientes.filter((c) => c.scoreValor >= SCORE_ALTO_VALOR).length,
    clvMedio: media(clientes.map((c) => c.clvProjetado)),
    receitaEmRisco: clientes
      .filter((c) => c.riscoEvasao !== null && c.riscoEvasao >= RISCO_ALTO)
      .reduce((a, c) => a + c.clvProjetado, 0),
    percentualRiscoAlto: clientes.length
      ? clientes.filter((c) => c.riscoEvasao !== null && c.riscoEvasao >= RISCO_ALTO).length / clientes.length
      : 0,
    sentimentoMedio: media(clientes.map((c) => c.sentimentoScore)),
    receitaMensal: MESES.map((mes, i) => ({
      mes,
      voos: clientes.reduce((a, c) => a + c.historico[i].voos, 0),
      receita: clientes.reduce((a, c) => a + c.historico[i].receita, 0),
    })),
    porPersona: PERSONA_IDS.map((persona) => {
      const grupo = semFiltroPersona.filter((c) => c.persona === persona);
      return {
        persona,
        clientes: grupo.length,
        clvTotal: grupo.reduce((a, c) => a + c.clvProjetado, 0),
        riscoMedio: media(grupo.flatMap((c) => (c.riscoEvasao === null ? [] : [c.riscoEvasao]))),
      };
    }),
    porTier: TIERS.map((tier) => ({ tier, clientes: clientes.filter((c) => c.tier === tier).length })),
    atritos: [...atritos.entries()]
      .map(([tema, mencoes]) => ({ tema, mencoes }))
      .sort((a, b) => b.mencoes - a.mencoes),
    matriz: clientes.map(resumir),
    prioritarios: [...clientes]
      .sort((a, b) => b.clvProjetado * (b.riscoEvasao ?? 0) - a.clvProjetado * (a.riscoEvasao ?? 0))
      .slice(0, 10)
      .map(resumir),
  };
}

export const fonteSintetica: FonteDeDadosCrm = {
  async listarClientes(filtro) {
    return filtrar(filtro)
      .map(resumir)
      .sort((a, b) => b.clvProjetado * (b.riscoEvasao ?? 0) - a.clvProjetado * (a.riscoEvasao ?? 0));
  },
  async obterCliente(id) {
    return CLIENTES.find((c) => c.id === id) ?? null;
  },
  async obterResumoDashboard(filtro) {
    return calcularResumo(filtrar(filtro), filtrar({ tier: filtro?.tier }));
  },
  async gerarRecomendacao(id) {
    const cliente = CLIENTES.find((c) => c.id === id);
    if (!cliente) throw new Error(`Cliente ${id} não encontrado`);
    await esperar(900);
    return cliente.proximaAcao;
  },
  async enviarBaseClientes(arquivo) {
    await esperar(600);
    return {
      arquivo: arquivo.name,
      tamanhoBytes: arquivo.size,
      status: 'simulado',
      mensagem:
        'Modo sintético: o arquivo foi lido apenas no navegador. Configure VITE_API_URL para enviá-lo ao backend (camada Bronze).',
    };
  },
  async obterModelo() {
    return MODELO_SIMULADO;
  },
};
