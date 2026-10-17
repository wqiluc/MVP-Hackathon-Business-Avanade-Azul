export type PerfilUsuario = 'analista' | 'gestor';

export interface Usuario {
  id: string;
  nome: string;
  email: string;
  perfil: PerfilUsuario;
  equipe: string;
}

/** Retorno de POST /auth/login. */
export interface Sessao {
  token: string;
  usuario: Usuario;
  /** ISO 8601. Depois disso o usuário precisa entrar de novo. */
  expiraEm: string;
}
