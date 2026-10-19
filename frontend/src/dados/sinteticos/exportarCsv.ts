import { CLIENTES } from './gerarClientes';

const COLUNAS = [
  'CUSTOMER_ID',
  'CATEGORIA_TIER',
  'PONTOS_ACUMULADOS',
  'VOOS_ANO',
  'DATA_CADASTRO',
  'RISCO_CHURN',
  'RECENCIA_DIAS',
  'GASTO_TOTAL',
  'INCIDENTES',
];

export function baixarBaseSinteticaCsv(): void {
  const linhas = CLIENTES.map((cliente) =>
    [
      cliente.id,
      cliente.tier,
      cliente.pontosQualificaveis,
      cliente.voos12m,
      cliente.membroDesde,
      cliente.riscoEvasao,
      cliente.recenciaDias,
      cliente.receita12m,
      cliente.incidentesVoo,
    ].join(','),
  );
  const blob = new Blob([`\uFEFF${[COLUNAS.join(','), ...linhas].join('\n')}`], {
    type: 'text/csv;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'CRM Alto Valor.csv';
  link.click();
  URL.revokeObjectURL(url);
}
