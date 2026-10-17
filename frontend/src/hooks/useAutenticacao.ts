import { useContext } from 'react';
import { ContextoAutenticacao, type EstadoAutenticacao } from '../contextos/contextoAutenticacao';

export function useAutenticacao(): EstadoAutenticacao {
  const contexto = useContext(ContextoAutenticacao);
  if (!contexto) throw new Error('useAutenticacao precisa estar dentro de <ProvedorAutenticacao>.');
  return contexto;
}
