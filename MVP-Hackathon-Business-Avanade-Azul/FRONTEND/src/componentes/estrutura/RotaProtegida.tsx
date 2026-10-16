import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAutenticacao } from '../../hooks/useAutenticacao';

/** Sem sessão, manda para o login e guarda a página pedida para voltar depois. */
export function RotaProtegida() {
  const { usuario } = useAutenticacao();
  const location = useLocation();

  if (!usuario) {
    return <Navigate to="/login" replace state={{ de: `${location.pathname}${location.search}` }} />;
  }
  return <Outlet />;
}
