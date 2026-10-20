import { Link } from 'react-router-dom';
import { BuscaCliente } from '../componentes/estrutura/BuscaCliente';
import { MenuUsuario } from '../componentes/estrutura/MenuUsuario';
import { AlternadorTema } from '../componentes/estrutura/AlternadorTema';
import { EnvioBaseClientes } from '../componentes/ingestao/EnvioBaseClientes';
import { SeloDadosSinteticos, SeloPersona, SeloRisco } from '../componentes/ui/Selos';
import { Icone, type NomeIcone } from '../componentes/ui/Icone';
import { useBuscaAssincrona } from '../hooks/useBuscaAssincrona';
import logo from '../imagens/logo-azul.jpg';
import { servicoCrm } from '../servicos/servicoCrm';
import { usandoDadosSinteticos } from '../servicos/configuracaoApi';
import { formatBRLCompacto, formatNumero } from '../utilitarios/formatacao';
import './PaginaMenu.css';

interface Modulo {
  titulo: string;
  descricao: string;
  icone: NomeIcone;
  para?: string;
}

const MODULOS: Modulo[] = [
  {
    titulo: 'Dashboard',
    descricao: 'Visão executiva da base: CLV, score high_risk_flag, personas, categorias e atritos da jornada.',
    icone: 'chart',
    para: '/dashboard',
  },
  {
    titulo: 'Visão dos clientes',
    descricao: 'Lista de clientes, filtros e acesso ao perfil, contexto do classificador e recomendação por LLM configurado ou regras.',
    icone: 'user',
    para: '/clientes/lista',
  },
  {
    titulo: 'Personas e segmentação',
    descricao: 'Clusters comportamentais com características, necessidades e estratégia por persona.',
    icone: 'users',
  },
  {
    titulo: 'Sentimento da jornada',
    descricao: 'Avaliações públicas (Reclame Aqui, lojas de apps e redes) para encontrar atritos.',
    icone: 'message',
  },
  {
    titulo: 'Modelo e governança',
    descricao: 'Experimentos e versões no MLflow, linhagem Bronze → Prata → Ouro e controles de LGPD.',
    icone: 'shield',
  },
];

function CartaoModulo({ modulo }: { modulo: Modulo }) {
  const conteudo = (
    <>
      <span className="modulo__icon">
        <Icone name={modulo.icone} size={20} />
      </span>
      <h3>{modulo.titulo}</h3>
      <p>{modulo.descricao}</p>
      <span className="modulo__cta">
        {modulo.para ? (
          <>
            Abrir <Icone name="arrowRight" size={16} />
          </>
        ) : (
          'Em breve'
        )}
      </span>
    </>
  );

  return modulo.para ? (
    <Link to={modulo.para} className="modulo">
      {conteudo}
    </Link>
  ) : (
    <div className="modulo modulo--inativo" aria-disabled="true">
      {conteudo}
    </div>
  );
}

export function PaginaMenu() {
  const { data: resumo } = useBuscaAssincrona(() => servicoCrm.obterResumoDashboard(), []);

  const stats = resumo && [
    { rotulo: 'Clientes monitorados', valor: formatNumero(resumo.totalClientes) },
    { rotulo: 'Alto valor (score ≥ 70)', valor: formatNumero(resumo.clientesAltoValor) },
    { rotulo: 'CLV médio (24 meses)', valor: formatBRLCompacto(resumo.clvMedio) },
    { rotulo: 'Receita em risco', valor: formatBRLCompacto(resumo.receitaEmRisco) },
  ];

  return (
    <div className="menu">
      <header className="menu__hero">
        <div className="menu__hero-inner">
          <div className="menu__topo">
            <img className="menu__logo" src={logo} alt="Azul Linhas Aéreas Brasileiras" />
            <MenuUsuario />
          </div>
          <AlternadorTema />
          <div>
            <h1>CRM de Alto Valor</h1>
            <p style={{ marginTop: 10 }}>
              Ferramenta interna para as equipes de CRM, Fidelidade e Relacionamento identificarem, priorizarem e
              reterem os clientes estratégicos da Azul.
            </p>
          </div>
          <BuscaCliente placeholder="Buscar cliente por nome ou ID (ex.: AZ-10000)" />
          {stats && (
            <div className="menu__stats">
              {stats.map((s) => (
                <div key={s.rotulo} className="menu__stat">
                  <span>{s.rotulo}</span>
                  <strong>{s.valor}</strong>
                </div>
              ))}
            </div>
          )}
        </div>
      </header>

      <main className="menu__body">
        <section>
          <h2 className="menu__section-title">Módulos</h2>
          <div className="menu__grid">
            {MODULOS.slice(0, 2).map((m) => (
              <CartaoModulo key={m.titulo} modulo={m} />
            ))}
            <EnvioBaseClientes />
            {MODULOS.slice(2).map((m) => (
              <CartaoModulo key={m.titulo} modulo={m} />
            ))}
          </div>
        </section>

        {resumo && (
          <section>
            <div className="row" style={{ justifyContent: 'space-between', marginBottom: 14 }}>
              <h2 className="menu__section-title" style={{ margin: 0 }}>
                Clientes que pedem ação agora
              </h2>
              <Link to="/dashboard" className="modulo__cta">
                Ver todos no dashboard <Icone name="arrowRight" size={16} />
              </Link>
            </div>
            <div className="atencao">
              {resumo.prioritarios.slice(0, 3).map((c) => (
                <Link key={c.id} to={`/clientes/${c.id}`} className="atencao__item">
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <strong>{c.nome}</strong>
                    <SeloRisco
                      risco={c.riscoEvasao}
                      origem={usandoDadosSinteticos ? 'heuristica-sintetica' : 'classificador'}
                    />
                  </div>
                  <div className="row">
                    <SeloPersona persona={c.persona} />
                    <small className="tabular">CLV {formatBRLCompacto(c.clvProjetado)}</small>
                  </div>
                  <small>
                    <Icone name="sparkles" size={14} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                    {c.proximaAcao}
                  </small>
                </Link>
              ))}
            </div>
          </section>
        )}
      </main>

      <footer className="menu__footer">
        <SeloDadosSinteticos /> &nbsp;Protótipo com base sintética calibrada por dados públicos. Pronto para receber
        dados reais via backend.
      </footer>
    </div>
  );
}
