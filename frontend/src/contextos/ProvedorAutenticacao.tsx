import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { servicoAutenticacao } from '../servicos/servicoAutenticacao';
import { gravarSessao, lerSessao, limparSessao } from '../servicos/sessao';
import type { Usuario } from '../tipos/autenticacao';
import { ContextoAutenticacao } from './contextoAutenticacao';

export function ProvedorAutenticacao({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(() => lerSessao()?.usuario ?? null);

  const entrar = useCallback(async (email: string, senha: string) => {
    const sessao = await servicoAutenticacao.entrar(email, senha);
    gravarSessao(sessao);
    setUsuario(sessao.usuario);
  }, []);

  const sair = useCallback(() => {
    limparSessao();
    setUsuario(null);
  }, []);

  const valor = useMemo(() => ({ usuario, entrar, sair }), [usuario, entrar, sair]);

  return <ContextoAutenticacao.Provider value={valor}>{children}</ContextoAutenticacao.Provider>;
}
