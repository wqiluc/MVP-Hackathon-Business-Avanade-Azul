import { Link, useParams } from 'react-router-dom';
import { CartaoRecomendacaoIA } from '../componentes/cliente/CartaoRecomendacaoIA';
import { BarrasRanking } from '../componentes/graficos/BarrasRanking';
import { CartaoGrafico } from '../componentes/graficos/CartaoGrafico';
import { Explicabilidade } from '../componentes/graficos/Explicabilidade';
import { GraficoVoosMensais } from '../componentes/graficos/GraficoVoosMensais';
import { AvisoModelo } from '../componentes/modelo/AvisoModelo';
import { Cartao } from '../componentes/ui/Cartao';
import { COR_STATUS_RISCO } from '../componentes/ui/cores';
import { Icone } from '../componentes/ui/Icone';
import { Indicador } from '../componentes/ui/Indicador';
import { Medidor } from '../componentes/ui/Medidor';
import {
  SeloCategoria,
  SeloDadosSinteticos,
  SeloPersona,
  SeloRisco,
  SeloSentimento,
} from '../componentes/ui/Selos';
import { PONTOS_QUALIFICAVEIS_POR_TIER, nivelRisco, proximoTier } from '../configuracao/fidelidade';
import { PERSONAS } from '../configuracao/personas';
import { cidade } from '../configuracao/aeroportos';
import { useBuscaAssincrona } from '../hooks/useBuscaAssincrona';
import { servicoCrm } from '../servicos/servicoCrm';
import type { Cliente } from '../tipos/crm';
import {
  formatBRL,
  formatBRLCompacto,
  formatData,
  formatNumero,
  formatPercentual,
  iniciais,
} from '../utilitarios/formatacao';

function Cabecalho({ cliente }: { cliente: Cliente }) {
  return (
    <Cartao>
      <div className="perfil">
        <div className="avatar" aria-hidden="true">
          {iniciais(cliente.nome)}
        </div>
        <div style={{ flex: 1, minWidth: 220 }}>
          <h1>{cliente.nome}</h1>
          <div className="perfil__meta tabular">
            {cliente.id} · Base {cliente.cidadeBase} ({cliente.aeroportoBase}) · Cliente desde{' '}
            {new Date(`${cliente.membroDesde}T12:00:00`).getFullYear()}
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <SeloCategoria tier={cliente.tier} />
            <SeloPersona persona={cliente.persona} />
            {cliente.consentimentoMarketing ? (
              <span className="badge badge--status badge--good">
                <Icone name="shield" size={14} />
                Consentimento de marketing
              </span>
            ) : (
              <span className="badge badge--status badge--warning">
                <Icone name="lock" size={14} />
                Sem consentimento de marketing
              </span>
            )}
            <SeloDadosSinteticos />
          </div>
        </div>
        <Link to="/dashboard" className="btn">
          <Icone name="arrowLeft" size={16} />
          Dashboard
        </Link>
      </div>
      <hr className="divider" />
      <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
        <strong style={{ color: 'var(--text-primary)' }}>{PERSONAS[cliente.persona].nome}:</strong>{' '}
        {PERSONAS[cliente.persona].descricao} Precisa de: {PERSONAS[cliente.persona].necessidades.join(', ').toLowerCase()}.
      </p>
    </Cartao>
  );
}

function Indicadores({ cliente }: { cliente: Cliente }) {
  const prox = proximoTier(cliente.tier);
  const alvo = prox ? PONTOS_QUALIFICAVEIS_POR_TIER[prox] : PONTOS_QUALIFICAVEIS_POR_TIER[cliente.tier];
  const faltam = Math.max(0, alvo - cliente.pontosQualificaveis);

  return (
    <div className="grid grid--kpi">
      <Indicador label="CLV projetado (24 meses)" value={formatBRLCompacto(cliente.clvProjetado)} hint={formatBRL(cliente.clvProjetado)} />
      <Indicador label="Score de alto valor" value={`${cliente.scoreValor}/100`} hint="Valor, frequência, recência e potencial">
        <Medidor value={cliente.scoreValor / 100} label="Score de alto valor" />
      </Indicador>
      <Indicador
        label="Risco de evasão (6 meses)"
        value={formatPercentual(cliente.riscoEvasao)}
        hint={<SeloRisco risco={cliente.riscoEvasao} mostrarValor={false} />}
      >
        <Medidor value={cliente.riscoEvasao} label="Risco de evasão" fill={COR_STATUS_RISCO[nivelRisco(cliente.riscoEvasao)]} />
      </Indicador>
      <Indicador
        label="Voos nos últimos 12 meses"
        value={formatNumero(cliente.voos12m)}
        hint={`Última viagem há ${cliente.recenciaDias} dias · ticket médio ${formatBRLCompacto(cliente.ticketMedio)}`}
      />
      <Indicador
        label={`Categoria ${cliente.tier}`}
        value={`${formatNumero(cliente.saldoPontos)} pts`}
        hint={prox ? `Faltam ${formatNumero(faltam)} pontos qualificáveis para ${prox}` : 'Categoria máxima do programa'}
      >
        <Medidor value={alvo ? cliente.pontosQualificaveis / alvo : 1} label={`Progresso para ${prox ?? cliente.tier}`} />
      </Indicador>
    </div>
  );
}

export function PaginaCliente() {
  const { id = '' } = useParams();
  const { data: cliente, carregando, erro } = useBuscaAssincrona(() => servicoCrm.obterCliente(id), [id]);

  if (erro) {
    return (
      <div className="note note--warning" role="alert">
        Não foi possível carregar o cliente: {erro.message}
      </div>
    );
  }

  if (!cliente) {
    return carregando ? (
      <p className="empty">Carregando cliente…</p>
    ) : (
      <Cartao>
        <div className="empty">
          <p>Cliente {id} não encontrado.</p>
          <Link to="/dashboard">Voltar ao dashboard</Link>
        </div>
      </Cartao>
    );
  }

  return (
    <div className={`stack-v ${carregando ? 'is-refreshing' : ''}`} style={{ gap: 24 }}>
      <Cabecalho cliente={cliente} />
      <Indicadores cliente={cliente} />
      <AvisoModelo />

      <div className="grid grid--3-2">
        {/* key: reinicia rascunho e tom ao trocar de cliente */}
        <CartaoRecomendacaoIA key={cliente.id} cliente={cliente} />
        <Cartao
          title="Por que este risco de evasão?"
          subtitle={`Taxa base de 18% + contribuição de cada fator = ${formatPercentual(cliente.riscoEvasao)}`}
        >
          <Explicabilidade
            fatores={cliente.explicacaoRisco}
            unidade="p.p."
            positivoEhBom={false}
            rotulos={{ bom: 'Reduz o risco', ruim: 'Aumenta o risco' }}
          />
        </Cartao>
      </div>

      <div className="grid grid--2">
        <Cartao
          title="Como o score de valor foi formado"
          subtitle={`Média da base (50) + contribuição de cada fator = ${cliente.scoreValor}`}
        >
          <Explicabilidade
            fatores={cliente.explicacaoValor}
            unidade="pts"
            positivoEhBom
            rotulos={{ bom: 'Aumenta o valor', ruim: 'Reduz o valor' }}
          />
        </Cartao>
        <CartaoGrafico
          title="Voos por mês"
          subtitle={`Últimos 12 meses · receita de ${formatBRL(cliente.receita12m)}`}
          tabela={{
            colunas: [{ rotulo: 'Mês' }, { rotulo: 'Voos', numerica: true }, { rotulo: 'Receita', numerica: true }],
            linhas: cliente.historico.map((m) => [m.mes, m.voos, formatBRL(m.receita)]),
          }}
        >
          <GraficoVoosMensais dados={cliente.historico} />
        </CartaoGrafico>
      </div>

      <div className="grid grid--2-3">
        <Cartao title="Rotas favoritas" subtitle="Voos nos últimos 12 meses">
          <BarrasRanking
            itens={cliente.rotasFavoritas.map((r) => ({
              rotulo: `${r.origem} → ${r.destino}`,
              descricao: `${cidade(r.origem)} → ${cidade(r.destino)}`,
              valor: r.voos12m,
              valorFormatado: `${r.voos12m} voos`,
            }))}
          />
        </Cartao>
        <Cartao title="Interações e sentimento" subtitle="Atendimento, pesquisas e avaliações públicas">
          <ul className="interacoes">
            {cliente.interacoes.map((i) => (
              <li key={`${i.data}-${i.tema}`} className="interacao">
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <span className="row">
                    <strong style={{ fontSize: 14 }}>{i.tema}</strong>
                    <span className="muted" style={{ fontSize: 12 }}>
                      {i.canal} · {formatData(i.data)}
                    </span>
                  </span>
                  <SeloSentimento sentimento={i.sentimento} />
                </div>
                <p>{i.texto}</p>
              </li>
            ))}
          </ul>
        </Cartao>
      </div>
    </div>
  );
}
