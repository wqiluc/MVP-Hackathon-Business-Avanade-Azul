import type { Sessao, Usuario } from '../tipos/autenticacao';
import { apiUrl, configuracaoAusente, MENSAGEM_CONFIGURACAO_AUSENTE } from './configuracaoApi';

export interface ServicoAutenticacao {
  entrar(email: string, senha: string): Promise<Sessao>;
}

export class ErroCredenciais extends Error {
  constructor() {
    super('E-mail ou senha incorretos.');
  }
}

const HORAS_SESSAO = 8;

const autenticacaoDemonstracao: ServicoAutenticacao = {
  async entrar(email, senha) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail.includes('@') || !senha) throw new ErroCredenciais();
    const localPart = normalizedEmail.split('@')[0] || 'Analista';
    const usuario: Usuario = {
      id: `synthetic-${crypto.randomUUID()}`,
      nome: localPart.replace(/[._-]+/g, ' '),
      email: normalizedEmail,
      perfil: 'analista',
      equipe: 'Demonstração sintética',
    };
    return {
      token: `demo-${usuario.id}`,
      usuario,
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

const autenticacaoIndisponivel: ServicoAutenticacao = {
  entrar: () => Promise.reject(new Error(MENSAGEM_CONFIGURACAO_AUSENTE)),
};

export const servicoAutenticacao: ServicoAutenticacao = apiUrl
  ? criarAutenticacaoApi(apiUrl)
  : configuracaoAusente
    ? autenticacaoIndisponivel
    : autenticacaoDemonstracao;
