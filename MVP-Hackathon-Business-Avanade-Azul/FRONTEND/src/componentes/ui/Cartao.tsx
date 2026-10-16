import type { ReactNode } from 'react';

interface CartaoProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}

export function Cartao({ title, subtitle, actions, className, children }: CartaoProps) {
  return (
    <section className={`card ${className ?? ''}`}>
      {(title || actions) && (
        <header className="card__header">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}
