// Base sintética determinística para o protótipo.
// Em produção estes registros vêm da camada analítica (gold) via API — ver
// src/servicos/servicoCrm.ts. As faixas por persona são premissas calibráveis
// pelos microdados públicos de tarifas e demanda da ANAC.

import {
  PONTOS_QUALIFICAVEIS_POR_TIER,
  REGRAS_FIDELIDADE,
  TIERS,
  proximoTier,
  tierPorPontos,
} from '../../configuracao/fidelidade';
import { PERSONA_IDS } from '../../configuracao/personas';
import type {
  Cliente,
  FatorExplicativo,
  Interacao,
  PersonaId,
  PontoMensal,
  ProximaAcao,
  RotaFavorita,
  Sentimento,
} from '../../tipos/crm';
import { formatBRLCompacto, formatNumero, formatPercentual, formatSinal } from '../../utilitarios/formatacao';
import { AEROPORTOS, cidade } from '../../configuracao/aeroportos';

export const DATA_REFERENCIA = '2026-09-30';
export const MESES = [
  'out/25', 'nov/25', 'dez/25', 'jan/26', 'fev/26', 'mar/26',
  'abr/26', 'mai/26', 'jun/26', 'jul/26', 'ago/26', 'set/26',
];
const AVISO_RECOMENDACAO_DEMONSTRATIVA =
  'Demonstração não verificada: oferta, condições e elegibilidade precisam ser confirmadas por um analista antes de qualquer comunicação ou aplicação.';

// ---------------------------------------------------------------------------
// Aleatoriedade reprodutível

function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rnd = mulberry32(2026);
const entre = (min: number, max: number) => min + rnd() * (max - min);
const inteiro = (min: number, max: number) => Math.floor(entre(min, max + 1));
const escolher = <T,>(lista: readonly T[]): T => lista[Math.floor(rnd() * lista.length)];
const limitar = (x: number, min: number, max: number) => Math.min(max, Math.max(min, x));
const normalizar = (x: number, lo: number, hi: number) => limitar((x - lo) / (hi - lo), 0, 1);
const umaCasa = (x: number) => Math.round(x * 10) / 10;

// ---------------------------------------------------------------------------
// Perfis de geração por persona

interface PerfilPersona {
  peso: number;
  voos: [number, number];
  ticket: [number, number];
  recencia: [number, number];
  tendencia: [number, number];
  atrasosMax: number;
  bases: string[];
  destinos: string[];
}

const PERFIS: Record<PersonaId, PerfilPersona> = {
  'executivo-frequente': {
    peso: 0.27,
    voos: [28, 64],
    ticket: [850, 1500],
    recencia: [1, 20],
    tendencia: [-0.35, 0.3],
    atrasosMax: 6,
    bases: ['VCP', 'CNF', 'REC', 'POA', 'CWB', 'BSB'],
    destinos: ['SDU', 'CGH', 'BSB', 'CNF', 'POA', 'CWB', 'REC', 'SSA', 'VCP'],
  },
  'lazer-premium': {
    peso: 0.2,
    voos: [6, 14],
    ticket: [1700, 3400],
    recencia: [15, 120],
    tendencia: [-0.4, 0.3],
    atrasosMax: 3,
    bases: ['VCP', 'CNF', 'POA', 'CWB', 'BSB', 'GYN'],
    destinos: ['REC', 'MCZ', 'NAT', 'FOR', 'SSA', 'FLN', 'BPS', 'FEN', 'MCO', 'FLL', 'LIS'],
  },
  'regional-conectado': {
    peso: 0.26,
    voos: [12, 30],
    ticket: [650, 1150],
    recencia: [4, 45],
    tendencia: [-0.4, 0.25],
    atrasosMax: 5,
    bases: ['MOC', 'JDO', 'CXJ', 'RAO', 'UDI', 'IOS', 'PMW', 'MAB'],
    destinos: ['VCP', 'CNF', 'REC', 'BSB'],
  },
  'potencial-ascensao': {
    peso: 0.27,
    voos: [8, 22],
    ticket: [800, 1400],
    recencia: [2, 25],
    tendencia: [0.2, 0.6],
    atrasosMax: 3,
    bases: ['VCP', 'CNF', 'REC', 'CWB', 'FLN', 'BSB', 'SSA'],
    destinos: ['SDU', 'CGH', 'POA', 'SSA', 'FOR', 'REC', 'CNF', 'VCP'],
  },
};

const NOMES = [
  'Ana', 'Bruno', 'Carla', 'Diego', 'Eduarda', 'Felipe', 'Gabriela', 'Henrique', 'Isabela', 'João',
  'Karina', 'Leonardo', 'Mariana', 'Nicolas', 'Olívia', 'Paulo', 'Rafaela', 'Rodrigo', 'Sofia', 'Thiago',
  'Valéria', 'Vinícius', 'Yasmin', 'André', 'Beatriz', 'Caio', 'Débora', 'Fernando', 'Helena', 'Igor',
  'Juliana', 'Lucas', 'Marcelo', 'Natália', 'Otávio', 'Patrícia', 'Renata', 'Sérgio', 'Tatiana', 'Wagner',
];

const SOBRENOMES = [
  'Almeida', 'Barbosa', 'Cardoso', 'Costa', 'Dias', 'Ferreira', 'Gomes', 'Lima', 'Martins', 'Melo',
  'Monteiro', 'Moreira', 'Nascimento', 'Oliveira', 'Pereira', 'Ramos', 'Ribeiro', 'Rocha', 'Santos', 'Silva',
  'Souza', 'Teixeira', 'Vieira', 'Azevedo', 'Batista', 'Campos', 'Freitas', 'Macedo', 'Nunes', 'Pinto',
];

const INTERACOES: Record<Sentimento, Omit<Interacao, 'data' | 'sentimento'>[]> = {
  negativo: [
    { tema: 'Atraso de voo', canal: 'Reclame Aqui', texto: 'Voo atrasou mais de 2 horas e perdi a conexão. Pouca informação no portão.' },
    { tema: 'Bagagem', canal: 'App', texto: 'Bagagem extraviada no desembarque; levou 3 dias para ser entregue.' },
    { tema: 'Remarcação', canal: 'Central de atendimento', texto: 'Não consegui remarcar pelo app e paguei uma diferença tarifária alta.' },
    { tema: 'Atendimento', canal: 'Redes sociais', texto: 'Esperei mais de 40 minutos no chat para resolver um problema simples.' },
    { tema: 'App e check-in', canal: 'Loja de apps', texto: 'O check-in pelo app travou duas vezes e precisei ir ao balcão.' },
    { tema: 'Programa de pontos', canal: 'E-mail', texto: 'Os pontos do último voo ainda não apareceram no extrato.' },
  ],
  neutro: [
    { tema: 'Programa de pontos', canal: 'App', texto: 'Consultou regras de resgate e saldo de pontos.' },
    { tema: 'Remarcação', canal: 'App', texto: 'Remarcou um voo sem custo adicional.' },
    { tema: 'Atendimento', canal: 'Central de atendimento', texto: 'Pediu informações sobre franquia de bagagem.' },
  ],
  positivo: [
    { tema: 'Experiência a bordo', canal: 'Pesquisa NPS', texto: 'Tripulação atenciosa e embarque rápido. Nota 10.' },
    { tema: 'Pontualidade', canal: 'Pesquisa NPS', texto: 'Voo pontual e conexão tranquila em Campinas.' },
    { tema: 'Programa de pontos', canal: 'Redes sociais', texto: 'Emiti passagem com pontos para as férias, processo fácil.' },
  ],
};

// ---------------------------------------------------------------------------
// Blocos de geração

function escolherPersona(): PersonaId {
  let alvo = rnd();
  for (const id of PERSONA_IDS) {
    alvo -= PERFIS[id].peso;
    if (alvo <= 0) return id;
  }
  return PERSONA_IDS.at(-1) as PersonaId;
}

/** Distribui o total de voos em 12 meses, respeitando tendência e recência. */
function gerarHistorico(voos12m: number, ticket: number, tendencia: number, recenciaDias: number): PontoMensal[] {
  const mesesSemVoo = Math.min(Math.floor(recenciaDias / 30), 6);
  const pesos = MESES.map((_, i) =>
    i >= MESES.length - mesesSemVoo ? 0 : Math.max(0.05, 1 + tendencia * ((i - 5.5) / 5.5)) * entre(0.7, 1.3),
  );
  const soma = pesos.reduce((a, b) => a + b, 0);
  const brutos = pesos.map((p) => (p / soma) * voos12m);
  const voos = brutos.map(Math.floor);
  let resto = voos12m - voos.reduce((a, b) => a + b, 0);
  const ordem = brutos.map((b, i) => ({ i, frac: b - Math.floor(b) })).sort((a, b) => b.frac - a.frac);
  for (const { i } of ordem) {
    if (resto <= 0) break;
    voos[i] += 1;
    resto -= 1;
  }
  return MESES.map((mes, i) => ({
    mes,
    voos: voos[i],
    receita: Math.round(voos[i] * ticket * entre(0.85, 1.15)),
  }));
}

function gerarRotas(base: string, destinos: string[], voos12m: number): RotaFavorita[] {
  const opcoes = destinos.filter((d) => d !== base);
  const escolhidas: string[] = [];
  while (escolhidas.length < 3) {
    const d = escolher(opcoes);
    if (!escolhidas.includes(d)) escolhidas.push(d);
  }
  const fatias = [0.45, 0.3, 0.15];
  return escolhidas.map((destino, i) => ({
    origem: base,
    destino,
    voos12m: Math.max(1, Math.round(voos12m * fatias[i])),
  }));
}

function gerarInteracoes(sentimentoScore: number): Interacao[] {
  const total = inteiro(2, 4);
  const referencia = new Date(`${DATA_REFERENCIA}T12:00:00`);
  const lista: Interacao[] = [];
  for (let i = 0; i < total; i++) {
    const x = sentimentoScore + entre(-0.5, 0.5);
    let sentimento: Sentimento = 'neutro';
    if (x < -0.2) sentimento = 'negativo';
    else if (x > 0.3) sentimento = 'positivo';
    const data = new Date(referencia);
    data.setDate(data.getDate() - inteiro(1, 120));
    lista.push({ ...escolher(INTERACOES[sentimento]), sentimento, data: data.toISOString().slice(0, 10) });
  }
  return lista.sort((a, b) => b.data.localeCompare(a.data));
}

function rotuloSentimento(score: number): string {
  if (score <= -0.2) return 'Negativo';
  if (score >= 0.3) return 'Positivo';
  return 'Neutro';
}

// Recomendações sintéticas construídas por regras determinísticas. O projeto
// não executa LLM neste fluxo. Ver ProximaAcao em src/tipos/crm.ts.
function gerarProximaAcao(
  c: Omit<Cliente, 'proximaAcao'>,
): ProximaAcao {
  const nome = c.nome.split(' ')[0];
  const rota = c.rotasFavoritas[0];
  const negativa = c.interacoes.find((i) => i.sentimento === 'negativo');
  const prox = proximoTier(c.tier);
  const faltam = prox ? Math.max(0, PONTOS_QUALIFICAVEIS_POR_TIER[prox] - c.pontosQualificaveis) : 0;

  const canalPorPersona: Record<PersonaId, string> = {
    'executivo-frequente': 'App + e-mail',
    'lazer-premium': 'E-mail',
    'regional-conectado': 'WhatsApp',
    'potencial-ascensao': 'App (push)',
  };

  let base: Pick<ProximaAcao, 'tipo' | 'titulo' | 'justificativa' | 'mensagem' | 'regrasFidelidade'>;

  if (c.riscoEvasao !== null && c.riscoEvasao >= 0.5 && negativa) {
    base = {
      tipo: 'recuperacao-servico',
      titulo: 'Contato de recuperação com bônus de pontos',
      justificativa: [
        `Risco de evasão de ${formatPercentual(c.riscoEvasao)}, com atrito recente em "${negativa.tema.toLowerCase()}"`,
        `CLV projetado de ${formatBRLCompacto(c.clvProjetado)} em 24 meses está exposto`,
        'Reconhecer a falha antes de qualquer oferta reduz a chance de rejeição',
      ],
      mensagem: `Olá, ${nome}! Esta é uma sugestão demonstrativa: após analisar sua experiência com ${negativa.tema.toLowerCase()} e consultar as regras vigentes, um analista poderia avaliar se há alguma forma de reconhecimento, como pontos bônus. Nenhum ponto foi creditado nem benefício confirmado. Nossa equipe pode ajudar a planejar sua próxima viagem para ${cidade(rota.destino)}.`,
      regrasFidelidade: [REGRAS_FIDELIDADE.bonusRelacionamento, REGRAS_FIDELIDADE.contatoServico],
    };
  } else if (c.persona === 'executivo-frequente' || (c.persona === 'potencial-ascensao' && !prox)) {
    base = {
      tipo: 'upgrade',
      titulo: 'Upgrade de cortesia para assentos com mais espaço',
      justificativa: [
        `${c.voos12m} voos nos últimos 12 meses; ${rota.origem}–${rota.destino} é a rota mais usada`,
        'Persona sensível a conforto e pontualidade',
        `Categoria ${c.tier}: o upgrade reforça o valor percebido do status`,
      ],
      mensagem: `Olá, ${nome}! Esta é uma sugestão demonstrativa: considerando seu histórico de ${c.voos12m} voos, um analista poderia verificar se existe alguma opção de assento com mais espaço para viagens entre ${cidade(rota.origem)} e ${cidade(rota.destino)}. Upgrade, disponibilidade e elegibilidade não estão confirmados.`,
      regrasFidelidade: [REGRAS_FIDELIDADE.beneficiosCategoria, REGRAS_FIDELIDADE.categorias],
    };
  } else if (c.persona === 'lazer-premium') {
    base = {
      tipo: 'oferta-rota',
      titulo: `Oferta antecipada para ${cidade(rota.destino)} com pontos em dobro`,
      justificativa: [
        `${rota.origem}–${rota.destino} concentra as viagens de lazer do cliente`,
        `Ticket médio de ${formatBRLCompacto(c.ticketMedio)}, acima da média da base`,
        `Última viagem há ${c.recenciaDias} dias: momento de planejar a próxima`,
      ],
      mensagem: `Olá, ${nome}! Esta é uma sugestão demonstrativa: um analista poderia verificar se existe campanha vigente de pontos em dobro para viagens a ${cidade(rota.destino)} e se há alguma condição aplicável. Campanha, prazo, assentos e elegibilidade não estão confirmados.`,
      regrasFidelidade: [REGRAS_FIDELIDADE.pontosEmDobro, REGRAS_FIDELIDADE.bonusRelacionamento],
    };
  } else if (c.persona === 'regional-conectado') {
    base = {
      tipo: 'comunicacao',
      titulo: `Comunicação personalizada para quem voa de ${c.cidadeBase}`,
      justificativa: [
        `Base em ${c.cidadeBase} (${c.aeroportoBase}), com alta dependência da malha regional`,
        `${c.voos12m} voos nos últimos 12 meses`,
        'Informação proativa sobre conexões reduz atrito percebido',
      ],
      mensagem: `Olá, ${nome}! Esta é uma sugestão demonstrativa: um analista poderia confirmar informações de conexão para viagens a ${cidade(rota.destino)} e verificar se existe alguma ação vigente de pontos bônus para quem voa a partir de ${c.cidadeBase}. Horários, campanha e elegibilidade não estão confirmados.`,
      regrasFidelidade: [REGRAS_FIDELIDADE.bonusRelacionamento],
    };
  } else {
    base = {
      tipo: 'bonus-pontos',
      titulo: `Desafio de categoria: faltam ${formatNumero(faltam)} pontos para ${prox}`,
      justificativa: [
        `Frequência ${formatSinal(tendenciaRecente(c.historico, c.voos12m) * 100, '%')} nos últimos 3 meses`,
        `A ${formatNumero(faltam)} pontos qualificáveis da categoria ${prox}`,
        'Subir de categoria aumenta o custo de troca e o CLV futuro',
      ],
      mensagem: `Olá, ${nome}! Os dados sintéticos estimam uma distância de ${formatNumero(faltam)} pontos qualificáveis até a categoria ${prox}; saldo e regras precisam ser confirmados. Como demonstração, um analista poderia verificar opções vigentes para apoiar sua jornada. Não há bônus ou mudança de categoria confirmados.`,
      regrasFidelidade: [REGRAS_FIDELIDADE.categorias, REGRAS_FIDELIDADE.bonusRelacionamento],
    };
  }

  return {
    ...base,
    mensagem: `${AVISO_RECOMENDACAO_DEMONSTRATIVA}\n\n${base.mensagem}`,
    regrasFidelidade: [AVISO_RECOMENDACAO_DEMONSTRATIVA, ...base.regrasFidelidade],
    canal: c.consentimentoMarketing || base.tipo === 'recuperacao-servico'
      ? canalPorPersona[c.persona]
      : 'Bloqueado: sem consentimento de marketing',
    confianca: null,
    origem: 'simulacao',
    impactoEstimado: {
      reducaoRiscoPp: null,
      receitaProtegida: null,
    },
  };
}

/** Variação da média de voos dos últimos 3 meses contra a média de 12 meses. */
function tendenciaRecente(historico: PontoMensal[], voos12m: number): number {
  if (voos12m === 0) return 0;
  const ultimos3 = historico.slice(-3).reduce((a, p) => a + p.voos, 0) / 3;
  return ultimos3 / (voos12m / 12) - 1;
}

// ---------------------------------------------------------------------------

function gerarCliente(indice: number): Cliente {
  const persona = escolherPersona();
  const perfil = PERFIS[persona];
  const emRisco = rnd() < 0.25;

  const voos12m = inteiro(...perfil.voos);
  const ticketBase = entre(...perfil.ticket);
  const recenciaDias = inteiro(...perfil.recencia) + (emRisco ? inteiro(40, 100) : 0);
  const tendencia = limitar(entre(...perfil.tendencia) - (emRisco ? 0.3 : 0), -0.6, 0.6);
  const atrasos = inteiro(0, perfil.atrasosMax) + (emRisco ? 2 : 0);
  const resgates = inteiro(0, 4);
  const sentimentoScore = umaCasa(limitar(entre(-0.6, 0.9) - atrasos * 0.06 - (emRisco ? 0.5 : 0), -1, 1) * 10) / 10;

  const historico = gerarHistorico(voos12m, ticketBase, tendencia, recenciaDias);
  const receita12m = historico.reduce((a, p) => a + p.receita, 0);
  const ticketMedio = Math.round(receita12m / voos12m);
  const tendReal = tendenciaRecente(historico, voos12m);

  const pontosQualificaveis = Math.round(receita12m * 0.4 * entre(0.85, 1.15));
  const tier = tierPorPontos(pontosQualificaveis);
  const tierIdx = TIERS.indexOf(tier);
  const base = escolher(perfil.bases);

  // Score de valor: base 50 + contribuições aditivas (RFM + potencial).
  const explicacaoValor: FatorExplicativo[] = [
    { fator: 'Receita nos últimos 12 meses', valor: formatBRLCompacto(receita12m), impacto: 30 * (normalizar(Math.log(receita12m), Math.log(6000), Math.log(80000)) - 0.5) },
    { fator: 'Frequência de voos', valor: `${voos12m} voos`, impacto: 20 * (normalizar(voos12m, 4, 50) - 0.5) },
    { fator: 'Tendência de frequência (3m)', valor: formatSinal(tendReal * 100, '%'), impacto: 14 * (normalizar(tendReal, -1, 1) - 0.5) },
    { fator: 'Recência da última viagem', valor: `${recenciaDias} dias`, impacto: 12 * (0.5 - normalizar(recenciaDias, 0, 120)) },
    { fator: 'Categoria Azul Fidelidade', valor: tier, impacto: 10 * (tierIdx / 3 - 0.5) },
    { fator: 'Resgates de pontos', valor: `${resgates} em 12m`, impacto: 6 * (resgates / 4 - 0.5) },
  ].map((f) => ({ ...f, impacto: umaCasa(f.impacto) }));
  const scoreValor = Math.round(limitar(50 + explicacaoValor.reduce((a, f) => a + f.impacto, 0), 1, 99));

  // Risco de evasão: taxa base de 18 p.p. + contribuições aditivas.
  const explicacaoRisco: FatorExplicativo[] = [
    { fator: 'Dias desde a última viagem', valor: `${recenciaDias} dias`, impacto: 30 * (normalizar(recenciaDias, 0, 150) - 0.25) },
    { fator: 'Variação da frequência (3m)', valor: formatSinal(tendReal * 100, '%'), impacto: -24 * (normalizar(tendReal, -1, 1) - 0.5) },
    { fator: 'Sentimento nas interações', valor: rotuloSentimento(sentimentoScore), impacto: -12 * sentimentoScore },
    { fator: 'Atrasos e cancelamentos sofridos', valor: `${atrasos} ocorrências`, impacto: 3 * atrasos - 4 },
    { fator: 'Resgates de pontos', valor: `${resgates} em 12m`, impacto: 3 - 3 * resgates },
    { fator: 'Categoria (custo de troca)', valor: tier, impacto: 3 - 3 * tierIdx },
  ].map((f) => ({ ...f, impacto: umaCasa(f.impacto) }));
  const riscoEvasao = limitar(18 + explicacaoRisco.reduce((a, f) => a + f.impacto, 0), 3, 95) / 100;

  // CLV = receita projetada em 24 meses caso o cliente seja retido. O risco fica
  // separado para que perda esperada = CLV × risco de evasão.
  const clvProjetado = Math.round(receita12m * 2 * (1 + 0.25 * limitar(tendReal, -1, 1)));

  const sobrenomes = rnd() > 0.5 ? [escolher(SOBRENOMES), escolher(SOBRENOMES)] : [escolher(SOBRENOMES)];
  const nome = [escolher(NOMES), ...sobrenomes].join(' ');
  const parcial: Omit<Cliente, 'proximaAcao'> = {
    id: `AZ-${String(10_000 + indice * 37).padStart(5, '0')}`,
    nome,
    tier,
    persona,
    aeroportoBase: base,
    cidadeBase: AEROPORTOS[base],
    membroDesde: `${inteiro(2009, 2024)}-${String(inteiro(1, 12)).padStart(2, '0')}-01`,
    consentimentoMarketing: rnd() > 0.15,
    clvProjetado,
    scoreValor,
    riscoEvasao,
    recenciaDias,
    voos12m,
    incidentesVoo: atrasos,
    receita12m,
    ticketMedio,
    saldoPontos: Math.round(pontosQualificaveis * entre(0.8, 2.6)),
    pontosQualificaveis,
    sentimentoScore,
    rotasFavoritas: gerarRotas(base, perfil.destinos, voos12m),
    historico,
    interacoes: gerarInteracoes(sentimentoScore),
    explicacaoValor,
    explicacaoRisco,
  };

  return { ...parcial, proximaAcao: gerarProximaAcao(parcial) };
}

export const CLIENTES: Cliente[] = Array.from({ length: 160 }, (_, i) => gerarCliente(i));
