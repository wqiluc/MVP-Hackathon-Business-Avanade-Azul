import type { FiltroClientes } from '../tipos/crm';
import type { FonteDeDadosCrm } from './fonteDeDados';
import { lerSessao, limparSessao } from './sessao';

function querystring(filtro: FiltroClientes = {}): string {
  const params = new URLSearchParams();
  if (filtro.persona) params.set('persona', filtro.persona);
  if (filtro.tier) params.set('tier', filtro.tier);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

async function requisitar<T>(baseUrl: string, caminho: string, init?: RequestInit): Promise<T> {
  const token = lerSessao()?.token;
  const resposta = await fetch(`${baseUrl}${caminho}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (resposta.status === 401) {
    // Sessão expirada ou inválida no backend: volta para o login.
    limparSessao();
    window.location.assign('/login');
  }
  if (!resposta.ok) throw new Error(`Falha em ${caminho} (HTTP ${resposta.status})`);
  return resposta.json() as Promise<T>;
}

/** Backend real: Snowflake (camada Ouro) + modelo do MLflow + IA generativa. */
export function criarFonteApi(baseUrl: string): FonteDeDadosCrm {
  return {
    listarClientes: (filtro) => requisitar(baseUrl, `/clientes${querystring(filtro)}`),
    async obterCliente(id) {
      try {
        return await requisitar(baseUrl, `/clientes/${encodeURIComponent(id)}`);
      } catch {
        return null;
      }
    },
    obterResumoDashboard: (filtro) => requisitar(baseUrl, `/dashboard/resumo${querystring(filtro)}`),
    gerarRecomendacao: (id) =>
      requisitar(baseUrl, `/clientes/${encodeURIComponent(id)}/recomendacao`, { method: 'POST' }),
    enviarBaseClientes(arquivo) {
      const corpo = new FormData();
      corpo.append('arquivo', arquivo);
      return requisitar(baseUrl, '/ingestao/clientes', { method: 'POST', body: corpo });
    },
    obterModelo: () => requisitar(baseUrl, '/modelo'),
  };
}
