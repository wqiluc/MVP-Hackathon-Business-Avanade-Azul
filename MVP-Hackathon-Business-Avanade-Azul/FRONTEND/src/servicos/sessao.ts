import type { Sessao } from '../tipos/autenticacao';

// sessionStorage: a sessão some ao fechar a aba. A senha nunca é guardada.
const CHAVE = 'crm-alto-valor:sessao';

export function lerSessao(): Sessao | null {
  try {
    const bruto = sessionStorage.getItem(CHAVE);
    if (!bruto) return null;
    const sessao = JSON.parse(bruto) as Sessao;
    if (new Date(sessao.expiraEm).getTime() <= Date.now()) {
      limparSessao();
      return null;
    }
    return sessao;
  } catch {
    return null;
  }
}

export function gravarSessao(sessao: Sessao): void {
  try {
    sessionStorage.setItem(CHAVE, JSON.stringify(sessao));
  } catch {
    // Armazenamento bloqueado (ex.: janela privada): a sessão vale só enquanto a página estiver aberta.
  }
}

export function limparSessao(): void {
  try {
    sessionStorage.removeItem(CHAVE);
  } catch {
    // ignorado
  }
}
