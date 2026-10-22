import type { Sessao } from '../tipos/autenticacao';

// sessionStorage: a sessão some ao fechar a aba. A senha nunca é guardada.
const CHAVE = 'crm-alto-valor:sessao';
export const EVENTO_SESSAO = 'crm-alto-valor:sessao-alterada';
let invalidada = false;

function sessaoValida(valor: unknown): valor is Sessao {
  if (!valor || typeof valor !== 'object') return false;
  const sessao = valor as Partial<Sessao>;
  const usuario = sessao.usuario;
  return typeof sessao.token === 'string' && Boolean(sessao.token.trim())
    && typeof sessao.expiraEm === 'string'
    && Number.isFinite(Date.parse(sessao.expiraEm))
    && Date.parse(sessao.expiraEm) > Date.now()
    && usuario !== undefined && usuario !== null && typeof usuario.id === 'string'
    && typeof usuario.nome === 'string' && typeof usuario.email === 'string'
    && typeof usuario.equipe === 'string'
    && ['analista', 'gestor', 'admin'].includes(usuario.perfil);
}

export function lerSessao(): Sessao | null {
  if (invalidada) return null;
  try {
    const bruto = sessionStorage.getItem(CHAVE);
    if (!bruto) return null;
    const sessao: unknown = JSON.parse(bruto);
    if (!sessaoValida(sessao)) {
      limparSessao();
      return null;
    }
    return sessao;
  } catch {
    console.warn('Não foi possível ler a sessão; autenticação encerrada.');
    limparSessao();
    return null;
  }
}

export function gravarSessao(sessao: Sessao): void {
  if (!sessaoValida(sessao)) {
    limparSessao();
    throw new Error('O serviço retornou uma sessão inválida. Entre novamente.');
  }
  try {
    sessionStorage.setItem(CHAVE, JSON.stringify(sessao));
    if (sessionStorage.getItem(CHAVE) !== JSON.stringify(sessao)) throw new Error('Storage write failed');
  } catch {
    limparSessao();
    throw new Error('Não foi possível salvar a sessão. Permita o armazenamento desta página para entrar.');
  }
  invalidada = false;
  window.dispatchEvent(new Event(EVENTO_SESSAO));
}

export function limparSessao(): void {
  invalidada = true;
  try {
    sessionStorage.removeItem(CHAVE);
  } catch {
    console.warn('Não foi possível remover a sessão armazenada; autenticação encerrada nesta página.');
  }
  window.dispatchEvent(new Event(EVENTO_SESSAO));
}
