export const AEROPORTOS: Record<string, string> = {
  VCP: 'Campinas',
  CNF: 'Belo Horizonte',
  REC: 'Recife',
  POA: 'Porto Alegre',
  CWB: 'Curitiba',
  BSB: 'Brasília',
  SDU: 'Rio de Janeiro',
  CGH: 'São Paulo',
  SSA: 'Salvador',
  GYN: 'Goiânia',
  FLN: 'Florianópolis',
  FOR: 'Fortaleza',
  NAT: 'Natal',
  MCZ: 'Maceió',
  BPS: 'Porto Seguro',
  FEN: 'Fernando de Noronha',
  MCO: 'Orlando',
  FLL: 'Fort Lauderdale',
  LIS: 'Lisboa',
  MOC: 'Montes Claros',
  JDO: 'Juazeiro do Norte',
  CXJ: 'Caxias do Sul',
  RAO: 'Ribeirão Preto',
  UDI: 'Uberlândia',
  IOS: 'Ilhéus',
  PMW: 'Palmas',
  MAB: 'Marabá',
};

export function cidade(iata: string): string {
  return AEROPORTOS[iata] ?? iata;
}
