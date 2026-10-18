import { Link } from 'react-router-dom';
import { EnvioBaseClientes } from '../componentes/ingestao/EnvioBaseClientes';
import { SeloDadosSinteticos } from '../componentes/ui/Selos';
import { Icone, type NomeIcone } from '../componentes/ui/Icone';
import { useBuscaAssincrona } from '../hooks/useBuscaAssincrona';
import { servicoCrm } from '../servicos/servicoCrm';
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
    descricao: 'Visão executiva da base: CLV, risco de evasão, personas, categorias e atritos da jornada.',
    icone: 'chart',
    para: '/dashboard',
  },
  {
    titulo: 'Visão dos clientes',
    descricao: 'Perfil 360°, explicação do modelo e recomendação personalizada gerada pela IA.',
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
          <div>
            <h1>CRM de Alto Valor</h1>
            <p style={{ marginTop: 10 }}>
              Ferramenta interna para as equipes de CRM, Fidelidade e Relacionamento identificarem, priorizarem e
              reterem os clientes estratégicos da Azul.
            </p>
          </div>
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

        
      </main>

      <footer className="menu__footer">
        <SeloDadosSinteticos /> &nbsp;Protótipo com base sintética calibrada por dados públicos. Pronto para receber
        dados reais via backend.
      </footer>
    </div>
  );
}
