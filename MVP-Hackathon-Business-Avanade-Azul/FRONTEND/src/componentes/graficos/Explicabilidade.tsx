import type { FatorExplicativo } from '../../tipos/crm';
import { formatSinal } from '../../utilitarios/formatacao';
import { Legenda } from './Legenda';

interface ExplicabilidadeProps {
  fatores: FatorExplicativo[];
  unidade: string;
  /** true quando uma contribuição positiva é boa para a Azul (ex.: score de valor). */
  positivoEhBom: boolean;
  rotulos: { bom: string; ruim: string };
}

/**
 * Contribuição de cada fator para o resultado do modelo (aditiva, estilo SHAP).
 * Azul = favorável à retenção/valor; vermelho = desfavorável.
 */
export function Explicabilidade({ fatores, unidade, positivoEhBom, rotulos }: ExplicabilidadeProps) {
  const ordenados = [...fatores].sort((a, b) => Math.abs(b.impacto) - Math.abs(a.impacto));
  const max = Math.max(1, ...ordenados.map((f) => Math.abs(f.impacto)));

  return (
    <div className="stack-v">
      <Legenda
        itens={[
          { rotulo: rotulos.bom, cor: 'var(--div-pos)' },
          { rotulo: rotulos.ruim, cor: 'var(--div-neg)' },
        ]}
      />
      <div className="diverging">
        {ordenados.map((f) => {
          const bom = f.impacto >= 0 === positivoEhBom;
          const largura = `calc(${(Math.abs(f.impacto) / max) * 50}% - 1px)`;
          const texto = formatSinal(f.impacto, ` ${unidade}`);
          return (
            <div key={f.fator} className="diverging__row">
              <div className="diverging__label">
                <span title={f.fator}>{f.fator}</span>
                <span>{f.valor}</span>
              </div>
              <div className="diverging__track">
                <div
                  className={`diverging__bar ${f.impacto >= 0 ? 'diverging__bar--right' : 'diverging__bar--left'}`}
                  style={{ width: largura, background: bom ? 'var(--div-pos)' : 'var(--div-neg)' }}
                  data-tip={`${f.fator}: ${texto}`}
                  tabIndex={0}
                />
              </div>
              <span className="diverging__value">{formatSinal(f.impacto)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
