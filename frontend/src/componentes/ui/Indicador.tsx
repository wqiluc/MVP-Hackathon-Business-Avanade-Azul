import type { ReactNode } from 'react';
import { Cartao } from './Cartao';

interface IndicadorProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  children?: ReactNode;
}

export function Indicador({ label, value, hint, children }: IndicadorProps) {
  return (
    <Cartao>
      <div className="stat">
        <span className="stat__label">{label}</span>
        <span className="stat__value">{value}</span>
        {hint && <span className="stat__hint">{hint}</span>}
        {children}
      </div>
    </Cartao>
  );
}
