import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts';
import type { PontoMensal } from '../../tipos/crm';
import { formatBRL } from '../../utilitarios/formatacao';

function TooltipVoos({ active, payload, label }: TooltipContentProps) {
  const ponto = active ? (payload?.[0]?.payload as PontoMensal | undefined) : undefined;
  if (!ponto) return null;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__title">{label}</div>
      <div className="chart-tooltip__row">
        <span>Voos</span>
        <strong>{ponto.voos}</strong>
      </div>
      <div className="chart-tooltip__row">
        <span>Receita</span>
        <strong>{formatBRL(ponto.receita)}</strong>
      </div>
    </div>
  );
}

export function GraficoVoosMensais({ dados }: { dados: PontoMensal[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={dados} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey="mes" stroke="var(--axis)" tick={{ fill: 'var(--text-muted)' }} tickLine={false} interval={1} />
        <YAxis
          stroke="var(--axis)"
          tick={{ fill: 'var(--text-muted)' }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
          width={40}
        />
        <Tooltip cursor={{ fill: 'var(--accent-wash)' }} content={TooltipVoos} />
        <Bar dataKey="voos" fill="var(--series-1)" maxBarSize={20} radius={[4, 4, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}
