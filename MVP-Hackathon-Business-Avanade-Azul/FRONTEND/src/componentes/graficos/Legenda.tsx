interface ItemLegenda {
  rotulo: string;
  cor: string;
  forma?: 'quadrado' | 'ponto';
}

export function Legenda({ itens }: { itens: ItemLegenda[] }) {
  return (
    <div className="legend">
      {itens.map((item) => (
        <span key={item.rotulo} className="legend__item">
          <span
            className={`legend__swatch ${item.forma === 'ponto' ? 'legend__swatch--dot' : ''}`}
            style={{ background: item.cor }}
          />
          {item.rotulo}
        </span>
      ))}
    </div>
  );
}
