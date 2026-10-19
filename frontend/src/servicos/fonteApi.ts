import type { FiltroClientes } from '../tipos/crm';
import type { FonteDeDadosCrm } from './fonteDeDados';
import { lerSessao, limparSessao } from './sessao';

export class ErroHttpApi extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

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
  let payload: unknown;
  try {
    payload = await resposta.json();
  } catch {
    if (!resposta.ok) {
      throw new ErroHttpApi(`Falha em ${caminho} (HTTP ${resposta.status})`, resposta.status);
    }
    throw new Error(`Resposta inválida da API em ${caminho}.`);
  }
  if (!resposta.ok) {
    const body = payload as {
      message?: unknown;
      detail?: unknown;
      missing_columns?: unknown;
      invalid_columns?: unknown;
    };
    const message =
      typeof body.message === 'string'
        ? body.message
        : typeof body.detail === 'string'
          ? body.detail
          : `Falha em ${caminho}`;
    const missing =
      Array.isArray(body.missing_columns) && body.missing_columns.every((item) => typeof item === 'string')
        ? ` Colunas ausentes: ${body.missing_columns.join(', ')}.`
        : '';
    const invalid =
      Array.isArray(body.invalid_columns) && body.invalid_columns.every((item) => typeof item === 'string')
        ? ` Colunas inválidas: ${body.invalid_columns.join(', ')}.`
        : '';
    throw new ErroHttpApi(`${message}${missing}${invalid} (HTTP ${resposta.status})`, resposta.status);
  }
  return payload as T;
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
      return requisitar(baseUrl, '/ingestao/clientes', { method: 'POST', body: corpo });
    },
    obterModelo: () => requisitar(baseUrl, '/modelo'),
  };
}
