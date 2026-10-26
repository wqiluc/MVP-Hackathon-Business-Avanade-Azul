import { useState, type ReactNode } from 'react';
import { Cartao } from '../ui/Cartao';

export interface TabelaDados {
  colunas: { rotulo: string; numerica?: boolean }[];
  linhas: ReactNode[][];
}

interface CartaoGraficoProps {
  title: string;
  subtitle?: string;
  legend?: ReactNode;
  /** Visão em tabela equivalente ao gráfico (acessibilidade). */
  tabela?: TabelaDados;
  className?: string;
  children: ReactNode;
}

export function CartaoGrafico({ title, subtitle, legend, tabela, className, children }: CartaoGraficoProps) {
  const [modo, setModo] = useState<'grafico' | 'tabela'>('grafico');

  const alternador = tabela && (
    <div className="segmented" role="group" aria-label="Forma de visualização">
      <button type="button" aria-pressed={modo === 'grafico'} onClick={() => setModo('grafico')}>
        Gráfico
      </button>
      <button type="button" aria-pressed={modo === 'tabela'} onClick={() => setModo('tabela')}>
        Tabela
      </button>
    </div>
  );

  return (
    <Cartao title={title} subtitle={subtitle} actions={alternador} className={className}>
      {modo === 'grafico' || !tabela ? (
        <>
          {legend && <div style={{ marginBottom: 12 }}>{legend}</div>}
          {children}
        </>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                {tabela.colunas.map((c) => (
                  <th key={c.rotulo} className={c.numerica ? 'num' : undefined}>
                    {c.rotulo}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tabela.linhas.map((linha, i) => (
                <tr key={i}>
                  {linha.map((celula, j) => (
                    <td key={j} className={tabela.colunas[j]?.numerica ? 'num' : undefined}>
                      {celula}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Cartao>
  );
}
