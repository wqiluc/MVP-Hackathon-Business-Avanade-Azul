// Contratos de dados do front-end.
// Espelham as tabelas da camada Ouro (Snowflake) expostas pelo backend.
// Ao trocar a base sintética por dados reais, basta a API respeitar estes tipos.

export type Tier = 'Básico' | 'Topázio' | 'Safira' | 'Diamante';

export type PersonaId =
  | 'executivo-frequente'
  | 'lazer-premium'
  | 'regional-conectado'
  | 'potencial-ascensao';

export type NivelRisco = 'baixo' | 'moderado' | 'alto' | 'critico';

export type Sentimento = 'positivo' | 'neutro' | 'negativo';

export type TipoAcao =
  | 'upgrade'
  | 'bonus-pontos'
  | 'comunicacao'
  | 'oferta-rota'
  | 'recuperacao-servico';

export interface Persona {
  id: PersonaId;
  nome: string;
  descricao: string;
  necessidades: string[];
  acaoRecomendada: string;
}

/** Contribuição aditiva de um fator para o score (estilo SHAP). */
export interface FatorExplicativo {
  fator: string;
  /** Valor observado do fator, já formatado para exibição. */
  valor: string;
  /** Pontos (score de valor) ou pontos percentuais (risco) somados à base. */
  impacto: number;
}

export interface RotaFavorita {
  origem: string;
  destino: string;
  voos12m: number;
}

export interface PontoMensal {
  /** Rótulo curto do mês, ex.: "set/26". */
  mes: string;
  voos: number;
  receita: number;
}

export interface Interacao {
  data: string;
  canal: string;
  tema: string;
  texto: string;
  sentimento: Sentimento;
}

export interface ProximaAcao {
  tipo: TipoAcao;
  titulo: string;
  justificativa: string[];
  canal: string;
  mensagem: string;
  /** Regras do Azul Fidelidade usadas como base de conhecimento do agente. */
  regrasFidelidade: string[];
  confianca: number;
  /** Quem gerou a recomendação: simulação local ou IA generativa no backend. */
  origem: 'simulacao' | 'ia-generativa';
  impactoEstimado: {
    reducaoRiscoPp: number;
    receitaProtegida: number;
  };
}

export interface Cliente {
  id: string;
  nome: string;
  tier: Tier;
  persona: PersonaId;
  aeroportoBase: string;
  cidadeBase: string;
  membroDesde: string;
  consentimentoMarketing: boolean;

  /** CLV: receita projetada em 24 meses caso o cliente seja retido, em R$. */
  clvProjetado: number;
  /** Score de alto valor, 0–100 (valor monetário, frequência, recência e potencial). */
  scoreValor: number;
  /** Probabilidade de evasão nos próximos 6 meses, 0–1. */
  riscoEvasao: number;

  recenciaDias: number;
  voos12m: number;
  receita12m: number;
  ticketMedio: number;
  saldoPontos: number;
  pontosQualificaveis: number;
  sentimentoScore: number;

  rotasFavoritas: RotaFavorita[];
  historico: PontoMensal[];
  interacoes: Interacao[];
  explicacaoValor: FatorExplicativo[];
  explicacaoRisco: FatorExplicativo[];
  proximaAcao: ProximaAcao;
}

/** Versão enxuta para listas e tabelas. */
export type ClienteResumo = Pick<
  Cliente,
  | 'id'
  | 'nome'
  | 'tier'
  | 'persona'
  | 'aeroportoBase'
  | 'clvProjetado'
  | 'scoreValor'
  | 'riscoEvasao'
> & { proximaAcao: string };

export interface FiltroClientes {
  persona?: PersonaId;
  tier?: Tier;
}

export interface ResumoDashboard {
  /** Data de corte dos dados exibidos (ISO). */
  dataReferencia: string;
  totalClientes: number;
  clientesAltoValor: number;
  clvMedio: number;
  receitaEmRisco: number;
  percentualRiscoAlto: number;
  sentimentoMedio: number;
  receitaMensal: PontoMensal[];
  /** Respeita o filtro de categoria, mas não o de persona (o painel é o seletor). */
  porPersona: {
    persona: PersonaId;
    clientes: number;
    clvTotal: number;
    riscoMedio: number;
  }[];
  porTier: { tier: Tier; clientes: number }[];
  atritos: { tema: string; mencoes: number }[];
  matriz: ClienteResumo[];
  prioritarios: ClienteResumo[];
}

/** Metadados do modelo de evasão registrado no MLflow/DagsHub. */
export interface ModeloInfo {
  nome: string;
  versao: string;
  plataforma: 'MLflow' | 'DagsHub';
  status: 'em-producao' | 'aguardando-registro';
  /** Meta de acurácia acordada na mentoria. */
  metaAcuracia: number;
  /** Métricas de validação; null enquanto não houver modelo registrado. */
  acuracia: number | null;
  auc: number | null;
  treinadoEm: string | null;
}

/** Retorno do envio de uma base de clientes pelo front-end. */
export interface ReciboIngestao {
  arquivo: string;
  tamanhoBytes: number;
  status: 'recebido' | 'simulado';
  mensagem: string;
}
