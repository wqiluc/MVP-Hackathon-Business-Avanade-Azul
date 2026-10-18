import { useSearchParams } from 'react-router-dom';
import { TabelaPrioritarios } from '../componentes/dashboard/TabelaPrioritarios';
import { BuscaCliente } from '../componentes/estrutura/BuscaCliente';
import { AvisoModelo } from '../componentes/modelo/AvisoModelo';
import { Cartao } from '../componentes/ui/Cartao';
import { Indicador } from '../componentes/ui/Indicador';
import { SeloDadosSinteticos } from '../componentes/ui/Selos';
import { nivelRisco, RISCO_ALTO, SCORE_ALTO_VALOR, TIERS } from '../configuracao/fidelidade';
import { PERSONAS, PERSONA_IDS } from '../configuracao/personas';
import { useBuscaAssincrona } from '../hooks/useBuscaAssincrona';
import { servicoCrm } from '../servicos/servicoCrm';
import type { FiltroClientes, PersonaId, Tier } from '../tipos/crm';
import {
  formatBRLCompacto,
  formatData,
  formatNumero,
  formatPercentual,
} from '../utilitarios/formatacao';

type FiltroRisco = 'alto' | 'moderado' | 'baixo';

function rotuloSentimento(score: number): string {
  if (score <= -0.2) return 'Negativo';
  if (score >= 0.3) return 'Positivo';
  return 'Neutro';
}

export function PaginaClientes() {
  const [params, setParams] = useSearchParams();
  const filtro: FiltroClientes = {
    persona: (params.get('persona') as PersonaId | null) ?? undefined,
    tier: (params.get('categoria') as Tier | null) ?? undefined,
  };
  const parametroRisco = params.get('risco');
  const riscoSelecionado: FiltroRisco | undefined =
    parametroRisco === 'alto' || parametroRisco === 'moderado' || parametroRisco === 'baixo'
      ? parametroRisco
      : undefined;

  const { data: resumo, carregando, erro } = useBuscaAssincrona(
    () => servicoCrm.obterResumoDashboard(filtro),
    [filtro.persona, filtro.tier],
  );

  const atualizarFiltro = (chave: 'persona' | 'categoria' | 'risco', valor?: string) => {
    const proximo = new URLSearchParams(params);
    if (valor) proximo.set(chave, valor);
    else proximo.delete(chave);
    setParams(proximo, { replace: true });
  };

  const temFiltro = Boolean(filtro.persona || filtro.tier || riscoSelecionado);
  const clientesOrdenados = (resumo?.matriz ?? [])
    .filter((cliente) => {
      if (!riscoSelecionado) return true;
      const nivel = nivelRisco(cliente.riscoEvasao);
      return riscoSelecionado === 'alto' ? nivel === 'alto' || nivel === 'critico' : nivel === riscoSelecionado;
    })
    .sort((a, b) => b.clvProjetado * b.riscoEvasao - a.clvProjetado * a.riscoEvasao);

  return (
    <>
      <div className="page-header">
        <div>
          <div className="eyebrow">Visão da página clientes</div>
          <h1>Clientes de alto valor</h1>
          <p>
            Onde está o valor da base, quem está em risco de evasão e qual ação tomar primeiro.
            {resumo && <> Dados até {formatData(resumo.dataReferencia)}.</>}
          </p>
        </div>
        <SeloDadosSinteticos />
      </div>

      <div className="filters">
        <label className="field">
          Persona
          <select
            className="select"
            value={filtro.persona ?? ''}
            onChange={(e) => atualizarFiltro('persona', e.target.value)}
          >
            <option value="">Todas as personas</option>
            {PERSONA_IDS.map((id) => (
              <option key={id} value={id}>
                {PERSONAS[id].nome}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Categoria Azul Fidelidade
          <select
            className="select"
            value={filtro.tier ?? ''}
            onChange={(e) => atualizarFiltro('categoria', e.target.value)}
          >
            <option value="">Todas as categorias</option>
            {TIERS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Risco de evasão
          <select
            className="select"
            value={riscoSelecionado ?? ''}
            onChange={(e) => atualizarFiltro('risco', e.target.value)}
          >
            <option value="">Todos os níveis</option>
            <option value="alto">Alto</option>
            <option value="moderado">Moderado</option>
            <option value="baixo">Baixo</option>
          </select>
        </label>
        <div className="field">
          <span>Buscar cliente</span>
          <BuscaCliente />
        </div>
        {temFiltro && (
          <button type="button" className="btn" onClick={() => setParams({}, { replace: true })}>
            Limpar filtros
          </button>
        )}
      </div>

      <AvisoModelo />

      {erro && (
        <div className="note note--warning" role="alert">
          Não foi possível carregar o dashboard: {erro.message}
        </div>
      )}

      {resumo && (
        <div className={`stack-v ${carregando ? 'is-refreshing' : ''}`} style={{ gap: 24 }}>
          <div className="grid grid--kpi">
            <Indicador
              label="Clientes monitorados"
              value={formatNumero(resumo.totalClientes)}
              hint={`${formatNumero(resumo.clientesAltoValor)} com score de valor ≥ ${SCORE_ALTO_VALOR}`}
            />
            <Indicador label="CLV médio projetado" value={formatBRLCompacto(resumo.clvMedio)} hint="Horizonte de 24 meses" />
            <Indicador
              label="Receita em risco"
              value={formatBRLCompacto(resumo.receitaEmRisco)}
              hint={`CLV de clientes com risco ≥ ${formatPercentual(RISCO_ALTO)}`}
            />
            <Indicador
              label="Clientes em risco alto"
              value={formatPercentual(resumo.percentualRiscoAlto)}
              hint="Probabilidade de evasão em 6 meses"
            />
            <Indicador
              label="Sentimento médio"
              value={rotuloSentimento(resumo.sentimentoMedio)}
              hint={`Índice ${resumo.sentimentoMedio.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} (−1 a +1)`}
            />
          </div>

          <Cartao
            title="Todos os clientes"
            subtitle="Ordenados pela perda esperada (CLV × risco de evasão). Clique em um cliente para ver a recomendação da IA."
          >
            <TabelaPrioritarios clientes={clientesOrdenados} />
          </Cartao>
        </div>
      )}

      {!resumo && carregando && <p className="empty">Carregando dashboard…</p>}
    </>
  );
}
