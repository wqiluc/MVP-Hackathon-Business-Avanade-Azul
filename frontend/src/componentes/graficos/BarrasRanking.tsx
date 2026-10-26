export interface ItemRanking {
  rotulo: string;
  valor: number;
  valorFormatado?: string;
  /** Texto completo para dica e leitores de tela, quando o rótulo é abreviado. */
  descricao?: string;
}

/** Barras horizontais de série única, com valor no fim da barra. */
export function BarrasRanking({ itens, cor = 'var(--series-1)' }: { itens: ItemRanking[]; cor?: string }) {
  const max = Math.max(1, ...itens.map((i) => i.valor));
  return (
    <div className="hbars">
      {itens.map((item) => {
        const texto = item.valorFormatado ?? String(item.valor);
        const descricao = item.descricao ?? item.rotulo;
        return (
          <div key={item.rotulo} className="hbar">
            <span className="hbar__label" title={descricao}>
              {item.rotulo}
            </span>
            <div className="hbar__track">
              <div
                className="hbar__fill"
                style={{ width: `${(item.valor / max) * 100}%`, background: cor }}
                data-tip={`${descricao}: ${texto}`}
                tabIndex={0}
              />
            </div>
            <span className="hbar__value">{texto}</span>
          </div>
        );
      })}
    </div>
  );
}
