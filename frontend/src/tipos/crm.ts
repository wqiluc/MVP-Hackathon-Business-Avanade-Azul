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
  confianca: number | null;
  /** LLM means a validated OpenAI response; rules/simulation are not generative AI. */
  origem: 'simulacao' | 'regras' | 'llm' | 'llm-indisponivel';
  impactoEstimado: {
    reducaoRiscoPp: number | null;
    receitaProtegida: number | null;
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
  consentimentoMarketing: boolean | null;

  /** CLV real de 12 meses na API; synthetic source retains its 24-month projection. */
  clvProjetado: number | null;
  clvHorizonteMeses?: 12 | 24 | null;
  clvModelSource?: 'local' | 'databricks' | null;
  clvModelName?: string | null;
  clvModelVersion?: string | null;
  /** Score de alto valor, 0–100 (valor monetário, frequência, recência e potencial). */
  scoreValor: number;
  /** API model probability or synthetic demo score; null when model features are unavailable. */
  riscoEvasao: number | null;

  recenciaDias: number;
  voos12m: number;
  /** Synthetic incident count; not an observed airline operations feed. */
  incidentesVoo: number;
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
  clvMedio: number | null;
  receitaEmRisco: number | null;
  percentualRiscoAlto: number | null;
  sentimentoMedio: number;
  receitaMensal: PontoMensal[];
  /** Respeita o filtro de categoria, mas não o de persona (o painel é o seletor). */
  porPersona: {
    persona: PersonaId;
    clientes: number;
    clvTotal: number | null;
    riscoMedio: number | null;
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
  plataforma: 'MLflow';
  status:
    | 'em-producao'
    | 'aguardando-registro'
    | 'aguardando-configuracao'
    | 'aguardando-serving'
    | 'serving-configurado';
  /** Meta de acurácia acordada na mentoria. */
  metaAcuracia: number | null;
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
  /** Contrato de ingestão detectado pelo backend (ex.: CRM_CANONICAL). */
  ingestion_contract?: string | null;
  /** Resumo agregado do scoring ML_FEATURES_52 (sem dados individuais). */
  scoring_summary?: {
    churn_score_mean: number | null;
    churn_score_max: number | null;
    clv_mean: number | null;
  };
}
