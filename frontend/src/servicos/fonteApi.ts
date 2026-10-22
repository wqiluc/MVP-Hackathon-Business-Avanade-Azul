import type { FiltroClientes } from '../tipos/crm';
import type { FonteDeDadosCrm } from './fonteDeDados';
import { lerSessao, limparSessao } from './sessao';
import { ErroHttpApi, requisitarJson, TIMEOUT_UPLOAD_MS } from './http';

export { ErroHttpApi } from './http';

function querystring(filtro: FiltroClientes = {}): string {
  const params = new URLSearchParams();
  if (filtro.persona) params.set('persona', filtro.persona);
  if (filtro.tier) params.set('tier', filtro.tier);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

async function requisitar<T>(baseUrl: string, caminho: string, init?: RequestInit, timeoutMs?: number): Promise<T> {
  const token = lerSessao()?.token;
  const encerrarSessao = () => {
    limparSessao();
    if (window.location.pathname !== '/login') window.location.assign('/login');
  };
  if (!token) {
    encerrarSessao();
    throw new ErroHttpApi('Sua sessão expirou. Entre novamente.', 401);
  }
  return requisitarJson<T>(`${baseUrl}${caminho}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  }, { timeoutMs, onUnauthorized: encerrarSessao });
}

/** Fonte que consome os contratos HTTP do backend FastAPI. */
export function criarFonteApi(baseUrl: string): FonteDeDadosCrm {
  return {
    listarClientes: (filtro) => requisitar(baseUrl, `/clientes${querystring(filtro)}`),
    async obterCliente(id) {
      try {
        return await requisitar(baseUrl, `/clientes/${encodeURIComponent(id)}`);
      } catch (error) {
        if (error instanceof ErroHttpApi && error.status === 404) return null;
        throw error;
      }
    },
    obterResumoDashboard: (filtro) => requisitar(baseUrl, `/dashboard/resumo${querystring(filtro)}`),
    gerarRecomendacao: (id) =>
      requisitar(baseUrl, `/clientes/${encodeURIComponent(id)}/recomendacao`, { method: 'POST' }),
    enviarBaseClientes(arquivo) {
      const corpo = new FormData();
      corpo.append('arquivo', arquivo);
      return requisitar(baseUrl, '/ingestao/clientes', { method: 'POST', body: corpo }, TIMEOUT_UPLOAD_MS);
    },
    obterModelo: () => requisitar(baseUrl, '/modelo'),
  };
}
