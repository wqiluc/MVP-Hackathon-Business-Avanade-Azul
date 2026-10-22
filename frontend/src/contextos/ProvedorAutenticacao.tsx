import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { servicoAutenticacao } from '../servicos/servicoAutenticacao';
import { EVENTO_SESSAO, gravarSessao, lerSessao, limparSessao } from '../servicos/sessao';
import type { Usuario } from '../tipos/autenticacao';
import { ContextoAutenticacao } from './contextoAutenticacao';

export function ProvedorAutenticacao({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(() => lerSessao()?.usuario ?? null);

  useEffect(() => {
    let timer: number | undefined;
    const atualizar = () => {
      window.clearTimeout(timer);
      const sessao = lerSessao();
      setUsuario(sessao?.usuario ?? null);
      if (sessao) {
        timer = window.setTimeout(atualizar, Math.min(Date.parse(sessao.expiraEm) - Date.now(), 2_147_483_647));
      }
    };
    window.addEventListener(EVENTO_SESSAO, atualizar);
    window.addEventListener('focus', atualizar);
    atualizar();
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener(EVENTO_SESSAO, atualizar);
      window.removeEventListener('focus', atualizar);
    };
  }, []);

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
