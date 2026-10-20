import { NavLink, Outlet, useLocation } from 'react-router-dom';
import logo from '../../imagens/logo-azul.jpg';
import { usandoDadosSinteticos } from '../../servicos/servicoCrm';
import { Icone, type NomeIcone } from '../ui/Icone';
import { BuscaCliente } from './BuscaCliente';
import { MenuUsuario } from './MenuUsuario';
import { AlternadorTema } from './AlternadorTema';

const NAVEGACAO: { para: string; rotulo: string; icone: NomeIcone; fim?: boolean }[] = [
  { para: '/', rotulo: 'Menu', icone: 'grid', fim: true },
  { para: '/dashboard', rotulo: 'Dashboard', icone: 'chart' },
  { para: '/clientes/lista', rotulo: 'Clientes', icone: 'users' },
  { para: '/clientes', rotulo: 'Cliente prioritário', icone: 'user', fim: true },
];

const TITULOS: Record<string, string> = {
  dashboard: 'Dashboard',
  clientes: 'Visão do cliente',
};

export function LayoutPrincipal() {
  const { pathname } = useLocation();
  const secao = pathname === '/clientes/lista' ? 'Clientes' : TITULOS[pathname.split('/')[1]] ?? '';

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink to="/" className="sidebar__brand" aria-label="Azul CRM de Alto Valor — voltar ao menu">
          <img src={logo} alt="Azul Linhas Aéreas Brasileiras" />
          <span>CRM de Alto Valor</span>
        </NavLink>
        <nav aria-label="Navegação principal">
          {NAVEGACAO.map((item) => (
            <NavLink key={item.para} to={item.para} end={item.fim} className="nav-link">
              <Icone name={item.icone} />
              {item.rotulo}
            </NavLink>
          ))}
        </nav>
        <AlternadorTema lateral />
        <div className="sidebar__footer">
          <Icone name="shield" size={16} />
          <span>
            {usandoDadosSinteticos
              ? 'Base 100% sintética. Nenhum dado real de cliente é usado neste protótipo.'
              : 'Conectado à API da camada analítica.'}
          </span>
        </div>
        <MenuUsuario />
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar__crumb">
            <span>CRM de Alto Valor</span>
            <span aria-hidden="true">/</span>
            <strong style={{ color: 'var(--text-primary)' }}>{secao}</strong>
          </div>
          <BuscaCliente />
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
