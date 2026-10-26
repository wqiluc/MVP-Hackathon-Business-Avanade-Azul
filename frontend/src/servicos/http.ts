export const TIMEOUT_HTTP_MS = 60_000;
export const TIMEOUT_UPLOAD_MS = 120_000;

type TipoErroHttp = 'http' | 'timeout' | 'network' | 'cancelled' | 'invalid-response';

export class ErroHttpApi extends Error {
  readonly status: number;
  readonly retryAfterSeconds: number | null;
  readonly tipo: TipoErroHttp;

  constructor(message: string, status: number, retryAfterSeconds: number | null = null, tipo: TipoErroHttp = 'http') {
    super(message);
    this.name = 'ErroHttpApi';
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
    this.tipo = tipo;
  }
}

function retryAfter(valor: string | null): number | null {
  if (!valor?.trim()) return null;
  if (!/^\d+$/.test(valor.trim()) && !/^[A-Za-z]{3}, \d{2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2} GMT$/.test(valor.trim())) return null;
  const segundos = /^\d+$/.test(valor.trim())
    ? Number(valor)
    : (Date.parse(valor) - Date.now()) / 1000;
  return Number.isSafeInteger(Math.ceil(segundos)) ? Math.max(0, Math.ceil(segundos)) : null;
}

function mensagemValidacao(payload: unknown): string | undefined {
  if (!payload || typeof payload !== 'object') return undefined;
  const body = payload as Record<string, unknown>;
  const mensagem = typeof body.message === 'string' ? body.message : body.detail;
  if (typeof mensagem !== 'string') return undefined;
  const campos = [
    ['missing_columns', 'Colunas ausentes'],
    ['invalid_columns', 'Colunas inválidas'],
  ] as const;
  const detalhes = campos.map(([chave, rotulo]) => {
    const colunas = body[chave];
    return Array.isArray(colunas) && colunas.length && colunas.every((item) => typeof item === 'string')
      ? ` ${rotulo}: ${colunas.join(', ')}.`
      : '';
  }).join('');
  return `${mensagem}${detalhes}`;
}

function mensagemErro(status: number, espera: number | null, payload: unknown): string {
  switch (status) {
    case 401: return 'Sua sessão expirou ou é inválida. Entre novamente.';
    case 403: return 'Você não tem permissão para realizar esta ação.';
    case 404: return 'O registro solicitado não foi encontrado.';
    case 429:
      return espera === null
        ? 'Limite de solicitações atingido. Aguarde antes de tentar novamente.'
        : `Limite de solicitações atingido. Tente novamente em ${espera} segundos.`;
    case 502:
    case 503: return 'Serviço temporariamente indisponível. Tente novamente mais tarde.';
    case 504: return 'O serviço demorou para responder. Tente novamente mais tarde.';
  }
  if (status >= 500) return 'Não foi possível concluir a operação. Tente novamente mais tarde.';
  if ([400, 413, 422].includes(status)) return mensagemValidacao(payload) ?? 'Verifique os dados enviados.';
  return 'Não foi possível concluir a solicitação.';
}

async function lerJson(resposta: Response, signal: AbortSignal): Promise<unknown> {
  try {
    return await resposta.json();
  } catch {
    if (signal.aborted) throw new Error('Request aborted');
    if (resposta.ok) {
      throw new ErroHttpApi('O serviço retornou uma resposta inválida.', resposta.status, null, 'invalid-response');
    }
    return undefined;
  }
}

interface OpcoesHttp {
  timeoutMs?: number;
  onUnauthorized?: () => void;
}

export async function requisitarJson<T>(
  url: string,
  init: RequestInit = {},
  { timeoutMs = TIMEOUT_HTTP_MS, onUnauthorized }: OpcoesHttp = {},
): Promise<T> {
  const controller = new AbortController();
  let expirou = false;
  const cancelar = () => controller.abort();
  if (init.signal?.aborted) controller.abort();
  else init.signal?.addEventListener('abort', cancelar, { once: true });
  const timer = setTimeout(() => {
    expirou = true;
    controller.abort();
  }, timeoutMs);
  try {
    const resposta = await fetch(url, { ...init, signal: controller.signal });
    if (resposta.status === 401) onUnauthorized?.();
    const espera = resposta.status === 429 ? retryAfter(resposta.headers.get('Retry-After')) : null;
    const payload = await lerJson(resposta, controller.signal);
    if (!resposta.ok) throw new ErroHttpApi(mensagemErro(resposta.status, espera, payload), resposta.status, espera);
    return payload as T;
  } catch (error_) {
    if (error_ instanceof ErroHttpApi) throw error_;
    if (expirou) throw new ErroHttpApi('A solicitação excedeu o tempo de espera. Verifique o resultado antes de tentar novamente.', 0, null, 'timeout');
    if (controller.signal.aborted) throw new ErroHttpApi('Solicitação cancelada.', 0, null, 'cancelled');
    throw new ErroHttpApi('Não foi possível conectar ao serviço. Verifique sua conexão.', 0, null, 'network');
  } finally {
    clearTimeout(timer);
    init.signal?.removeEventListener('abort', cancelar);
  }
}
