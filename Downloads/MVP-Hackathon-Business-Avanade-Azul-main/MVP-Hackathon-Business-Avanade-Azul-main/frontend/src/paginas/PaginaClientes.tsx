import { useSearchParams } from 'react-router-dom';
import { TabelaPrioritarios } from '../componentes/dashboard/TabelaPrioritarios';
import { AvisoModelo } from '../componentes/modelo/AvisoModelo';
import { Cartao } from '../componentes/ui/Cartao';
import { nivelRisco, TIERS } from '../configuracao/fidelidade';
import { PERSONAS, PERSONA_IDS } from '../configuracao/personas';
import { useBuscaAssincrona } from '../hooks/useBuscaAssincrona';
import { servicoCrm } from '../servicos/servicoCrm';
import { usandoDadosSinteticos } from '../servicos/configuracaoApi';
import { formatNumero } from '../utilitarios/formatacao';

const FILTROS_SCORE = [
  { id: 'alto', rotulo: 'Alto / crítico (≥ 0,5)' },
  { id: 'moderado', rotulo: 'Moderado (≥ 0,3 e < 0,5)' },
  { id: 'baixo', rotulo: 'Baixo (< 0,3)' },
  { id: 'indisponivel', rotulo: 'Score indisponível' },
] as const;

export function PaginaClientes() {
  const [params, setParams] = useSearchParams();
  const persona = PERSONA_IDS.find((id) => id === params.get('persona'));
  const tier = TIERS.find((categoria) => categoria === params.get('categoria'));
  const score = FILTROS_SCORE.find((opcao) => opcao.id === params.get('risco'))?.id;
  const { data, carregando, erro } = useBuscaAssincrona(() => servicoCrm.listarClientes(), []);

  const clientes = (data ?? [])
    .filter((cliente) => {
      if (persona && cliente.persona !== persona) return false;
      if (tier && cliente.tier !== tier) return false;
      if (!score) return true;
      if (cliente.riscoEvasao === null) return score === 'indisponivel';
      if (score === 'indisponivel') return false;
      const nivel = nivelRisco(cliente.riscoEvasao);
      return score === 'alto' ? nivel === 'alto' || nivel === 'critico' : nivel === score;
    })
    .sort((a, b) => {
      if (a.riscoEvasao === null) return b.riscoEvasao === null ? a.id.localeCompare(b.id) : 1;
      if (b.riscoEvasao === null) return -1;
      return (
        (b.clvProjetado ?? 0) * b.riscoEvasao -
        (a.clvProjetado ?? 0) * a.riscoEvasao ||
        a.id.localeCompare(b.id)
      );
    });

  function atualizarFiltro(chave: string, valor: string) {
    const proximo = new URLSearchParams(params);
    if (valor) proximo.set(chave, valor);
    else proximo.delete(chave);
    setParams(proximo, { replace: true });
  }

  return (
    <>
      <div className="page-header">
        <div>
          <div className="eyebrow">Base de clientes</div>
          <h1>Clientes</h1>
          <p>
            {usandoDadosSinteticos
              ? 'Score sintético demonstrativo; não representa churn observado.'
              : 'Score de churn disponível quando a origem fornece todas as features exigidas pelo modelo.'}
          </p>
        </div>
      </div>

      <div className="filters">
        <label className="field">
          Persona
          <select className="select" value={persona ?? ''} onChange={(e) => atualizarFiltro('persona', e.target.value)}>
            <option value="">Todas as personas</option>
            {PERSONA_IDS.map((id) => <option key={id} value={id}>{PERSONAS[id].nome}</option>)}
          </select>
        </label>
        <label className="field">
          Categoria Azul Fidelidade
          <select className="select" value={tier ?? ''} onChange={(e) => atualizarFiltro('categoria', e.target.value)}>
            <option value="">Todas as categorias</option>
            {TIERS.map((categoria) => <option key={categoria} value={categoria}>{categoria}</option>)}
          </select>
        </label>
        <label className="field">
          Faixa do {usandoDadosSinteticos ? 'score sintético' : 'score de churn'}
          <select className="select" value={score ?? ''} onChange={(e) => atualizarFiltro('risco', e.target.value)}>
            <option value="">Todos os scores</option>
            {FILTROS_SCORE.map((opcao) => <option key={opcao.id} value={opcao.id}>{opcao.rotulo}</option>)}
          </select>
        </label>
        {(persona || tier || score) && (
          <button type="button" className="btn" onClick={() => setParams({}, { replace: true })}>
            Limpar filtros
          </button>
        )}
      </div>

      <AvisoModelo />
      {erro && <div className="note note--warning" role="alert">Não foi possível carregar os clientes: {erro.message}</div>}
      {carregando && <p className="empty" role="status">Carregando clientes…</p>}
      {data && !erro && (
        <Cartao
          title="Clientes da base"
          subtitle="Ordenados por CLV × score disponível. Clientes sem score ficam ao final, sem prioridade calculada."
        >
          <p role="status">{formatNumero(clientes.length)} de {formatNumero(data.length)} clientes para os filtros selecionados.</p>
          <TabelaPrioritarios clientes={clientes} />
        </Cartao>
      )}
    </>
  );
}
