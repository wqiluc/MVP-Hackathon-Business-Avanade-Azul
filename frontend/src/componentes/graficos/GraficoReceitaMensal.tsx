import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts';
import type { PontoMensal } from '../../tipos/crm';
import { formatBRLCompacto, formatNumero } from '../../utilitarios/formatacao';

function TooltipReceita({ active, payload, label }: TooltipContentProps) {
  const ponto = active ? (payload?.[0]?.payload as PontoMensal | undefined) : undefined;
  if (!ponto) return null;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__title">{label}</div>
      <div className="chart-tooltip__row">
        <span>
          <span className="chart-tooltip__key" style={{ background: 'var(--series-1)' }} />
          Receita
        </span>
        <strong>{formatBRLCompacto(ponto.receita)}</strong>
      </div>
      <div className="chart-tooltip__row">
        <span>Voos</span>
        <strong>{formatNumero(ponto.voos)}</strong>
      </div>
    </div>
  );
}

export function GraficoReceitaMensal({ dados }: { dados: PontoMensal[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={dados} margin={{ top: 8, right: 16, bottom: 0, left: 4 }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey="mes" stroke="var(--axis)" tick={{ fill: 'var(--text-muted)' }} tickLine={false} interval="preserveStartEnd" />
        <YAxis
          stroke="var(--axis)"
          tick={{ fill: 'var(--text-muted)' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => formatBRLCompacto(v)}
          width={76}
        />
        <Tooltip cursor={{ stroke: 'var(--axis)' }} content={TooltipReceita} />
        <Area
          type="monotone"
          dataKey="receita"
          stroke="var(--series-1)"
          strokeWidth={2}
          fill="var(--series-1-wash)"
          fillOpacity={1}
          activeDot={{ r: 5, stroke: 'var(--surface)', strokeWidth: 2, fill: 'var(--series-1)' }}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
