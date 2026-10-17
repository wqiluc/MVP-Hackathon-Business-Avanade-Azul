import { createContext } from 'react';
import type { Usuario } from '../tipos/autenticacao';

export interface EstadoAutenticacao {
  usuario: Usuario | null;
  entrar(email: string, senha: string): Promise<void>;
  sair(): void;
}

export const ContextoAutenticacao = createContext<EstadoAutenticacao | null>(null);
