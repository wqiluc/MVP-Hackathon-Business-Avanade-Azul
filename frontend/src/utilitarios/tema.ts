export type Tema = 'light' | 'dark';

const CHAVE_TEMA = 'azul-crm-theme';

export function lerPreferenciaTema(): Tema | null {
  try {
    const tema = window.localStorage.getItem(CHAVE_TEMA);
    return tema === 'light' || tema === 'dark' ? tema : null;
  } catch (erro) {
    if (!(erro instanceof DOMException)) throw erro;
    console.warn('Não foi possível ler a preferência de tema; usando o sistema.', erro);
    return null;
  }
}

export function salvarPreferenciaTema(tema: Tema): void {
  window.localStorage.setItem(CHAVE_TEMA, tema);
}

export function temaDoSistema(): Tema {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function inicializarTema(): void {
  document.documentElement.dataset.theme = lerPreferenciaTema() ?? temaDoSistema();
}
