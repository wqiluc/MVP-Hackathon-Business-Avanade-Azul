import type { NivelRisco, Tier } from '../tipos/crm';

// PREMISSA: limites ilustrativos para a base sintética. Antes de uso real,
// substituir pelas regras vigentes publicadas em voeazul.com.br/azulfidelidade.
export const TIERS: Tier[] = ['Básico', 'Topázio', 'Safira', 'Diamante'];

export const PONTOS_QUALIFICAVEIS_POR_TIER: Record<Tier, number> = {
  Básico: 0,
  Topázio: 5_000,
  Safira: 10_000,
  Diamante: 20_000,
};

export function tierPorPontos(pontos: number): Tier {
  let atual: Tier = 'Básico';
  for (const tier of TIERS) {
    if (pontos >= PONTOS_QUALIFICAVEIS_POR_TIER[tier]) atual = tier;
  }
  return atual;
}

export function proximoTier(tier: Tier): Tier | null {
  const i = TIERS.indexOf(tier);
  return i < TIERS.length - 1 ? TIERS[i + 1] : null;
}

// Cortes de negócio usados no dashboard e na matriz de prioridade.
export const SCORE_ALTO_VALOR = 70;
export const RISCO_ALTO = 0.5;

export function nivelRisco(risco: number): NivelRisco {
  if (risco >= 0.7) return 'critico';
  if (risco >= RISCO_ALTO) return 'alto';
  if (risco >= 0.3) return 'moderado';
  return 'baixo';
}

// Trechos da base de conhecimento do agente (RAG sobre o regulamento público).
// PREMISSA: redação ilustrativa — validar contra o regulamento vigente.
export const REGRAS_FIDELIDADE = {
  categorias:
    'Categorias Topázio, Safira e Diamante são conquistadas por pontos qualificáveis acumulados em 12 meses.',
  bonusRelacionamento:
    'Pontos bônus de relacionamento podem ser creditados pela companhia em campanhas e ações de reconhecimento.',
  beneficiosCategoria:
    'Clientes de categoria têm benefícios como prioridade de embarque e acesso a assentos com mais espaço.',
  pontosEmDobro:
    'Campanhas promocionais podem multiplicar o acúmulo de pontos em rotas e períodos específicos.',
  contatoServico:
    'Contato de serviço sobre uma falha operacional não depende de consentimento de marketing (base legal a validar com o jurídico).',
} as const;
