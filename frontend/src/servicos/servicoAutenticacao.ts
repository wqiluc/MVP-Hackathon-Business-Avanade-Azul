import type { Sessao, Usuario } from '../tipos/autenticacao';
import { apiUrl } from './configuracaoApi';

export interface ServicoAutenticacao {
  entrar(email: string, senha: string): Promise<Sessao>;
}

export class ErroCredenciais extends Error {
  constructor() {
    super('E-mail ou senha incorretos.');
  }
}

const HORAS_SESSAO = 8;

// Acessos de demonstração, válidos apenas no modo sintético (sem backend).
export const ACESSOS_DEMONSTRACAO: { email: string; senha: string; usuario: Usuario }[] = [
  {
    email: 'analista@exemplo.com',
    senha: 'azul2026',
    usuario: {
      id: 'u-analista',
      nome: 'Ana Analista',
      email: 'analista@exemplo.com',
      perfil: 'analista',
      equipe: 'CRM e Relacionamento',
    },
  },
  {
    email: 'gestor@exemplo.com',
    senha: 'azul2026',
    usuario: {
      id: 'u-gestor',
      nome: 'Gustavo Gestor',
      email: 'gestor@exemplo.com',
      perfil: 'gestor',
      equipe: 'Fidelidade',
    },
  },
];

const autenticacaoDemonstracao: ServicoAutenticacao = {
  async entrar(email, senha) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    const acesso = ACESSOS_DEMONSTRACAO.find((a) => a.email === email.trim().toLowerCase() && a.senha === senha);
    if (!acesso) throw new ErroCredenciais();
    return {
      token: `demo-${acesso.usuario.id}`,
      usuario: acesso.usuario,
      expiraEm: new Date(Date.now() + HORAS_SESSAO * 3_600_000).toISOString(),
    };
  },
};

function criarAutenticacaoApi(baseUrl: string): ServicoAutenticacao {
  return {
    async entrar(email, senha) {
      const resposta = await fetch(`${baseUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ email: email.trim(), senha }),
      });
      if (resposta.status === 401) throw new ErroCredenciais();
      if (!resposta.ok) throw new Error(`Não foi possível entrar agora (HTTP ${resposta.status}).`);
      return resposta.json() as Promise<Sessao>;
    },
  };
}

export const servicoAutenticacao: ServicoAutenticacao = apiUrl
  ? criarAutenticacaoApi(apiUrl)
  : autenticacaoDemonstracao;
