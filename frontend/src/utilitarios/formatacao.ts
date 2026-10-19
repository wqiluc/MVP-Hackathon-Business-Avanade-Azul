const brl = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  maximumFractionDigits: 0,
});

const numero = new Intl.NumberFormat('pt-BR');

const compacto = new Intl.NumberFormat('pt-BR', {
  notation: 'compact',
  maximumFractionDigits: 1,
});

export function formatBRL(valor: number): string {
  return brl.format(valor);
}

/** R$ 12,4 mil · R$ 1,3 mi */
export function formatBRLCompacto(valor: number | null): string {
  if (valor === null) return '—';
  return `R$ ${compacto.format(valor)}`;
}

export function formatNumero(valor: number): string {
  return numero.format(valor);
}

export function formatPercentual(fracao: number | null, casas = 0): string {
  if (fracao === null) return '—';
  return `${(fracao * 100).toLocaleString('pt-BR', {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  })}%`;
}

export function formatData(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function formatSinal(valor: number | null, sufixo = ''): string {
  if (valor === null) return '—';
  const arredondado = Math.round(valor * 10) / 10;
  const texto = Math.abs(arredondado).toLocaleString('pt-BR', { maximumFractionDigits: 1 });
  if (arredondado > 0) return `+${texto}${sufixo}`;
  if (arredondado < 0) return `−${texto}${sufixo}`;
  return `0${sufixo}`;
}

export function iniciais(nome: string): string {
  const partes = nome.split(' ');
  return `${partes[0][0]}${partes[partes.length - 1][0]}`.toUpperCase();
}
