import {
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
  type TooltipContentProps,
} from 'recharts';
import { RISCO_ALTO } from '../../configuracao/fidelidade';
import { PERSONAS } from '../../configuracao/personas';
import { usandoDadosSinteticos } from '../../servicos/configuracaoApi';
import type { ClienteResumo } from '../../tipos/crm';
import { formatBRLCompacto, formatPercentual } from '../../utilitarios/formatacao';

interface Ponto {
  id: string;
  nome: string;
  persona: string;
  risco: number;
  clv: number;
}

interface MatrizValorRiscoProps {
  clientes: ClienteResumo[];
  /** CLV a partir do qual o cliente é considerado de alto valor. */
  corteClv: number;
  onSelecionar: (id: string) => void;
}

const eixo = {
  stroke: 'var(--axis)',
  tick: { fill: 'var(--text-muted)' },
  tickLine: false,
} as const;

function TooltipMatriz({ active, payload }: TooltipContentProps) {
  const ponto = active ? (payload?.[0]?.payload as Ponto | undefined) : undefined;
  if (!ponto) return null;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__title">{ponto.persona}</div>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{ponto.nome}</div>
      <div className="chart-tooltip__row">
        <span>CLV {usandoDadosSinteticos ? 24 : 12}m</span>
        <strong>{formatBRLCompacto(ponto.clv)}</strong>
      </div>
      <div className="chart-tooltip__row">
        <span>{usandoDadosSinteticos ? 'Score sintético' : 'Score de churn'}</span>
        <strong>{formatPercentual(ponto.risco / 100)}</strong>
      </div>
      <div className="chart-tooltip__title" style={{ marginTop: 6, marginBottom: 0 }}>
        Clique para abrir o cliente
      </div>
    </div>
  );
}

export function MatrizValorRisco({ clientes, corteClv, onSelecionar }: MatrizValorRiscoProps) {
  const clientesComScore = clientes.filter((cliente) => cliente.riscoEvasao !== null);
  const pontos = clientes
    .filter(
      (cliente): cliente is ClienteResumo & { riscoEvasao: number; clvProjetado: number } =>
        cliente.riscoEvasao !== null && cliente.clvProjetado !== null,
    )
    .map((c) => ({
      id: c.id,
      nome: c.nome,
      persona: PERSONAS[c.persona].nome,
      risco: Math.round(c.riscoEvasao * 1000) / 10,
      clv: c.clvProjetado,
      prioritario: c.riscoEvasao >= RISCO_ALTO && c.clvProjetado >= corteClv,
    }));

  if (pontos.length === 0) {
    return (
      <div className="empty">
        {clientesComScore.length ? 'CLV indisponível.' : 'Score indisponível.'}
      </div>
    );
  }

  const abrir = (ponto: { payload?: Ponto }) => {
    if (ponto.payload) onSelecionar(ponto.payload.id);
  };

  return (
    <ResponsiveContainer width="100%" height={420}>
      <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 4 }}>
        <CartesianGrid stroke="var(--grid)" />
        <XAxis
          {...eixo}
          type="number"
          dataKey="risco"
          name={usandoDadosSinteticos ? 'Score sintético' : 'Score de churn'}
          domain={[0, 100]}
          ticks={[0, 25, 50, 75, 100]}
          tickFormatter={(v: number) => `${v}%`}
          height={44}
          label={{ value: usandoDadosSinteticos ? 'Score sintético demonstrativo' : 'Score de churn (classe positiva)', position: 'insideBottom', offset: 0, fill: 'var(--text-muted)', fontSize: 12 }}
        />
        <YAxis
          {...eixo}
          type="number"
          dataKey="clv"
          name="CLV"
          tickFormatter={(v: number) => formatBRLCompacto(v)}
          width={76}
        />
        <ZAxis range={[64, 64]} />
        <ReferenceLine x={RISCO_ALTO * 100} stroke="var(--axis)" />
        <ReferenceLine y={corteClv} stroke="var(--axis)" />
        <Tooltip cursor={false} content={TooltipMatriz} />
        <Scatter
          name="Demais clientes"
          data={pontos.filter((p) => !p.prioritario)}
          fill="var(--deemphasis)"
          stroke="var(--surface)"
          strokeWidth={2}
          cursor="pointer"
          onClick={abrir}
          isAnimationActive={false}
        />
        <Scatter
          name="Prioridade de retenção"
          data={pontos.filter((p) => p.prioritario)}
          fill="var(--series-1)"
          stroke="var(--surface)"
          strokeWidth={2}
          cursor="pointer"
          onClick={abrir}
          isAnimationActive={false}
        />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
