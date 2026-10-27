import type { Tier } from '../../tipos/crm';
import { formatPercentual } from '../../utilitarios/formatacao';
import { COR_TIER } from '../ui/cores';

interface ComposicaoCategoriasProps {
  dados: { tier: Tier; clientes: number }[];
}

/** Barra empilhada 100% na rampa ordinal das categorias. */
export function ComposicaoCategorias({ dados }: ComposicaoCategoriasProps) {
  const total = dados.reduce((a, d) => a + d.clientes, 0) || 1;
  return (
    <div className="stack-v">
      <div className="stack" role="img" aria-label="Composição da base por categoria">
        {dados
          .filter((d) => d.clientes > 0)
          .map((d) => (
            <div
              key={d.tier}
              className="stack__seg"
              style={{ flex: d.clientes, background: COR_TIER[d.tier] }}
              data-tip={`${d.tier}: ${d.clientes} clientes (${formatPercentual(d.clientes / total)})`}
              tabIndex={0}
            />
          ))}
      </div>
      <div className="legend">
        {dados.map((d) => (
          <span key={d.tier} className="legend__item">
            <span className="legend__swatch" style={{ background: COR_TIER[d.tier] }} />
            {d.tier}
            <strong className="tabular" style={{ color: 'var(--text-primary)' }}>
              {d.clientes}
            </strong>
            <span className="muted tabular">({formatPercentual(d.clientes / total)})</span>
          </span>
        ))}
      </div>
    </div>
  );
}
