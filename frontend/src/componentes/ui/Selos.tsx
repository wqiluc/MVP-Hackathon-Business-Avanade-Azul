import { TIERS, nivelRisco } from '../../configuracao/fidelidade';
import { PERSONAS } from '../../configuracao/personas';
import type { NivelRisco, PersonaId, Sentimento, Tier } from '../../tipos/crm';
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

const STATUS_RISCO: Record<NivelRisco, { classe: string; icone: NomeIcone; rotulo: string }> = {
  baixo: { classe: 'good', icone: 'check', rotulo: 'Baixo' },
  moderado: { classe: 'warning', icone: 'info', rotulo: 'Moderado' },
  alto: { classe: 'serious', icone: 'alert', rotulo: 'Alto' },
  critico: { classe: 'critical', icone: 'octagon', rotulo: 'Crítico' },
};

export function SeloRisco({ risco, mostrarValor = true }: { risco: number; mostrarValor?: boolean }) {
  const status = STATUS_RISCO[nivelRisco(risco)];
  return (
    <span className={`badge badge--status badge--${status.classe}`}>
      <Icone name={status.icone} size={14} />
      {status.rotulo}
      {mostrarValor && <span className="tabular">· {formatPercentual(risco)}</span>}
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
