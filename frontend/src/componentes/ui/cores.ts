import type { NivelRisco, Tier } from '../../tipos/crm';

// Rampa ordinal (validada com --ordinal) para as categorias do programa.
export const COR_TIER: Record<Tier, string> = {
  Básico: 'var(--ord-1)',
  Topázio: 'var(--ord-2)',
  Safira: 'var(--ord-3)',
  Diamante: 'var(--ord-4)',
};

// Cores de status: sempre acompanhadas de ícone + rótulo.
export const COR_STATUS_RISCO: Record<NivelRisco, string> = {
  baixo: 'var(--good)',
  moderado: 'var(--warning)',
  alto: 'var(--serious)',
  critico: 'var(--critical)',
};
