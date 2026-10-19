import { useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { SegmentosPersona } from '../componentes/dashboard/SegmentosPersona';
import { TabelaPrioritarios } from '../componentes/dashboard/TabelaPrioritarios';
import { BarrasRanking } from '../componentes/graficos/BarrasRanking';
import { CartaoGrafico } from '../componentes/graficos/CartaoGrafico';
import { ComposicaoCategorias } from '../componentes/graficos/ComposicaoCategorias';
import { GraficoReceitaMensal } from '../componentes/graficos/GraficoReceitaMensal';
import { Legenda } from '../componentes/graficos/Legenda';
import { MatrizValorRisco } from '../componentes/graficos/MatrizValorRisco';
import { AvisoModelo } from '../componentes/modelo/AvisoModelo';
import { Cartao } from '../componentes/ui/Cartao';
import { Indicador } from '../componentes/ui/Indicador';
import { SeloDadosSinteticos } from '../componentes/ui/Selos';
import { RISCO_ALTO, SCORE_ALTO_VALOR, TIERS } from '../configuracao/fidelidade';
import { PERSONAS, PERSONA_IDS } from '../configuracao/personas';
import { useBuscaAssincrona } from '../hooks/useBuscaAssincrona';
import { servicoCrm } from '../servicos/servicoCrm';
import type { FiltroClientes, PersonaId, Tier } from '../tipos/crm';
import {
  formatBRL,
  formatBRLCompacto,
  formatData,
  formatNumero,
  formatPercentual,
} from '../utilitarios/formatacao';

function rotuloSentimento(score: number): string {
  if (score <= -0.2) return 'Negativo';
  if (score >= 0.3) return 'Positivo';
  return 'Neutro';
}

/** Percentil simples para o corte de "alto CLV" da matriz. */
function percentil(valores: number[], p: number): number {
  if (!valores.length) return 0;
  const ordenados = [...valores].sort((a, b) => a - b);
  return ordenados[Math.min(ordenados.length - 1, Math.floor(p * ordenados.length))];
}

export function PaginaDashboard() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const filtro: FiltroClientes = {
    persona: (params.get('persona') as PersonaId | null) ?? undefined,
    tier: (params.get('categoria') as Tier | null) ?? undefined,
  };

  const { data: resumo, carregando, erro } = useBuscaAssincrona(
    () => servicoCrm.obterResumoDashboard(filtro),
    [filtro.persona, filtro.tier],
  );

  const atualizarFiltro = (chave: 'persona' | 'categoria', valor?: string) => {
    const proximo = new URLSearchParams(params);
    if (valor) proximo.set(chave, valor);
    else proximo.delete(chave);
    setParams(proximo, { replace: true });
  };

  const corteClv = useMemo(
    () => percentil(resumo?.matriz.map((c) => c.clvProjetado) ?? [], 0.75),
    [resumo],
  );

  const temFiltro = Boolean(filtro.persona || filtro.tier);

  return (
    <>
      <div className="page-header">
        <div>
          <div className="eyebrow">Visão executiva</div>
          <h1>Clientes de alto valor</h1>
          <p>
            Onde está o valor da base, como se distribui o score high_risk_flag e qual ação revisar primeiro.
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
              label="Share com score high_risk_flag ≥ 0,5"
              value={formatPercentual(resumo.percentualRiscoAlto)}
              hint="Percentual dos clientes com score disponível; não é taxa de churn observado"
            />
            <Indicador
              label="Sentimento médio"
              value={rotuloSentimento(resumo.sentimentoMedio)}
              hint={`Índice ${resumo.sentimentoMedio.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} (−1 a +1)`}
            />
          </div>

          <div className="grid grid--3-2">
            <CartaoGrafico
              title="Matriz de valor × score high_risk_flag"
              subtitle={`Cada ponto com score disponível é um cliente. Prioridade: CLV acima de ${formatBRLCompacto(corteClv)} e score ≥ ${formatPercentual(RISCO_ALTO)}.`}
              legend={
                <Legenda
                  itens={[
                    { rotulo: 'Prioridade de retenção', cor: 'var(--series-1)', forma: 'ponto' },
                    { rotulo: 'Demais clientes', cor: 'var(--deemphasis)', forma: 'ponto' },
                  ]}
                />
              }
              tabela={{
                colunas: [
                  { rotulo: 'Cliente' },
                  { rotulo: 'CLV 24m', numerica: true },
                  { rotulo: 'Score high_risk_flag', numerica: true },
                ],
                linhas: resumo.prioritarios.map((c) => [
                  c.nome,
                  formatBRL(c.clvProjetado),
                  formatPercentual(c.riscoEvasao),
                ]),
              }}
            >
              <MatrizValorRisco
                clientes={resumo.matriz}
                corteClv={corteClv}
                onSelecionar={(id) => navigate(`/clientes/${id}`)}
              />
            </CartaoGrafico>

            <Cartao title="Segmentação por persona" subtitle="CLV total projetado por segmento. Clique para filtrar.">
              <SegmentosPersona
                dados={resumo.porPersona}
                selecionada={filtro.persona}
                onSelecionar={(p) => atualizarFiltro('persona', p)}
              />
              <p className="regras" style={{ marginTop: 12 }}>
                Segmentação apenas por comportamento de voo e relacionamento. Nenhum atributo sensível (LGPD) é usado.
              </p>
            </Cartao>
          </div>

          <div className="grid grid--3-2">
            <CartaoGrafico
              title="Receita mensal da base"
              subtitle="Últimos 12 meses"
              tabela={{
                colunas: [{ rotulo: 'Mês' }, { rotulo: 'Voos', numerica: true }, { rotulo: 'Receita', numerica: true }],
                linhas: resumo.receitaMensal.map((m) => [m.mes, formatNumero(m.voos), formatBRL(m.receita)]),
              }}
            >
              <GraficoReceitaMensal dados={resumo.receitaMensal} />
            </CartaoGrafico>

            <div className="stack-v" style={{ gap: 16 }}>
              <Cartao title="Composição por categoria" subtitle="Clientes por categoria do Azul Fidelidade">
                <ComposicaoCategorias dados={resumo.porTier} />
              </Cartao>
              <Cartao title="Atritos na jornada" subtitle="Menções negativas por tema (avaliações e atendimento)">
                <BarrasRanking
                  itens={resumo.atritos.slice(0, 6).map((a) => ({ rotulo: a.tema, valor: a.mencoes }))}
                />
              </Cartao>
            </div>
          </div>

          <Cartao
            title="Fila de prioridade de relacionamento"
            subtitle="Ordenada por CLV × score de classificação (heurística de priorização, não perda observada). Clique para revisar a recomendação."
          >
            <TabelaPrioritarios clientes={resumo.prioritarios} />
          </Cartao>
        </div>
      )}

      {!resumo && carregando && <p className="empty">Carregando dashboard…</p>}
    </>
  );
}
