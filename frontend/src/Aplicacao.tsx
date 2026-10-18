import { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { LayoutPrincipal } from './componentes/estrutura/LayoutPrincipal';
import { RotaProtegida } from './componentes/estrutura/RotaProtegida';
import { ProvedorAutenticacao } from './contextos/ProvedorAutenticacao';
import { useBuscaAssincrona } from './hooks/useBuscaAssincrona';
import { PaginaLogin } from './paginas/PaginaLogin';
import { PaginaMenu } from './paginas/PaginaMenu';
import { servicoCrm } from './servicos/servicoCrm';

// Telas com gráficos carregadas sob demanda (o Menu não precisa do Recharts).
const PaginaDashboard = lazy(() =>
  import('./paginas/PaginaDashboard').then((m) => ({ default: m.PaginaDashboard })),
);
const PaginaClientes = lazy(() =>
  import('./paginas/PaginaClientes').then((m) => ({ default: m.PaginaClientes })),
);
const PaginaCliente = lazy(() => import('./paginas/PaginaCliente').then((m) => ({ default: m.PaginaCliente })));

const carregando = <p className="empty">Carregando…</p>;

/** /clientes sem ID abre o primeiro cliente da fila de prioridade. */
function ClientePrioritario() {
  const { data, erro } = useBuscaAssincrona(() => servicoCrm.listarClientes(), []);
  if (data === undefined && !erro) return carregando;
  return <Navigate to={data?.length ? `/clientes/${data[0].id}` : '/dashboard'} replace />;
}

export function Aplicacao() {
  return (
    <ProvedorAutenticacao>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<PaginaLogin />} />
          <Route element={<RotaProtegida />}>
            <Route element={<LayoutPrincipal />}>
              <Route path="/" element={<PaginaMenu />} />
              <Route path="/dashboard" element={<Suspense fallback={carregando}><PaginaDashboard /></Suspense>} />
              <Route path="/clientes/lista" element={<Suspense fallback={carregando}><PaginaClientes /></Suspense>} />
              <Route path="/clientes" element={<ClientePrioritario />} />
              <Route path="/clientes/:id" element={<Suspense fallback={carregando}><PaginaCliente /></Suspense>} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ProvedorAutenticacao>
  );
}
