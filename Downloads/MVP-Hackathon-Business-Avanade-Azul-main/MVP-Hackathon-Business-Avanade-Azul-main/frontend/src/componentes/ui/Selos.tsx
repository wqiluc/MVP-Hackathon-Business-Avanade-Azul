import { TIERS } from '../../configuracao/fidelidade';
import { PERSONAS } from '../../configuracao/personas';
import type { PersonaId, Sentimento, Tier } from '../../tipos/crm';
import { formatPercentual } from '../../utilitarios/formatacao';
import { COR_TIER } from './cores';
import { Icone, type NomeIcone } from './Icone';

export function SeloCategoria({ tier }: { tier: Tier }) {
  return (
    <span className="badge" title={`Categoria ${TIERS.indexOf(tier) + 1} de ${TIERS.length}`}>
      <span className="badge__dot" style={{ background: COR_TIER[tier] }} />
      {tier}
    </span>
  );
}

export function SeloPersona({ persona }: { persona: PersonaId }) {
  return (
    <span className="badge">
      <Icone name="users" size={14} />
      {PERSONAS[persona].nome}
    </span>
  );
}

export function SeloRisco({
  risco,
  origem = 'classificador',
}: {
  risco: number | null;
  origem?: 'classificador' | 'heuristica-sintetica';
}) {
  if (risco === null) {
    return <span className="badge badge--status">Score indisponível</span>;
  }
  return (
    <span className={`badge ${origem === 'heuristica-sintetica' ? 'badge--synthetic' : 'badge--status'}`}>
      {origem === 'heuristica-sintetica' ? 'Heurística sintética' : 'Score de churn'}
      <span className="tabular">· {formatPercentual(risco)}</span>
    </span>
  );
}

const STATUS_SENTIMENTO: Record<Sentimento, { classe: string; icone: NomeIcone; rotulo: string }> = {
  positivo: { classe: 'good', icone: 'smile', rotulo: 'Positivo' },
  neutro: { classe: 'neutral', icone: 'info', rotulo: 'Neutro' },
  negativo: { classe: 'critical', icone: 'alert', rotulo: 'Negativo' },
};

export function SeloSentimento({ sentimento }: { sentimento: Sentimento }) {
  const status = STATUS_SENTIMENTO[sentimento];
  return (
    <span className={`badge badge--status badge--${status.classe}`}>
      <Icone name={status.icone} size={14} />
      {status.rotulo}
    </span>
  );
}

export function SeloDadosSinteticos() {
  return (
    <span className="badge badge--synthetic" title="Todos os dados exibidos são sintéticos">
      <Icone name="database" size={14} />
      Dados sintéticos
    </span>
  );
}
