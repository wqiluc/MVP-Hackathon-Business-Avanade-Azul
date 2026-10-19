import { useState } from 'react';
import { useAutenticacao } from '../../hooks/useAutenticacao';
import { servicoCrm } from '../../servicos/servicoCrm';
import type { Cliente, ProximaAcao } from '../../tipos/crm';
import { formatBRLCompacto, formatPercentual, formatSinal } from '../../utilitarios/formatacao';
import { Cartao } from '../ui/Cartao';
import { Icone } from '../ui/Icone';

type Tom = 'padrao' | 'formal' | 'curto';

const TONS: { id: Tom; rotulo: string }[] = [
  { id: 'padrao', rotulo: 'Próximo' },
  { id: 'formal', rotulo: 'Formal' },
  { id: 'curto', rotulo: 'Curto' },
];

function aplicarTom(mensagem: string, tom: Tom): string {
  if (tom === 'formal') {
    return `${mensagem.replace(/^Olá, ([^!]+)!/, 'Olá, $1.')}\n\nAtenciosamente,\nEquipe Azul Fidelidade`;
  }
  if (tom === 'curto') {
    return (mensagem.match(/[^.!?]+[.!?]+/g) ?? [mensagem]).slice(0, 2).join('').trim();
  }
  return mensagem;
}

/**
 * Recomendação de próxima melhor ação para a equipe de relacionamento.
 * O backend combina o score do modelo com um workflow determinístico; aqui o analista
 * revisa, ajusta e aprova — nada é enviado ao cliente sem aprovação humana.
 */
export function CartaoRecomendacaoIA({ cliente }: { cliente: Cliente }) {
  const { usuario } = useAutenticacao();
  const [acao, setAcao] = useState<ProximaAcao>(cliente.proximaAcao);
  const [tom, setTom] = useState<Tom>('padrao');
  const [texto, setTexto] = useState(cliente.proximaAcao.mensagem);
  const [gerando, setGerando] = useState(false);
  const [aprovada, setAprovada] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const bloqueada =
    acao.canal.startsWith('Bloqueado') || cliente.consentimentoMarketing !== true;
  const politicaVerificada = acao.regrasFidelidade.some((regra) =>
    regra.startsWith('Contexto de política marcado como verificado'),
  );

  const regenerar = async () => {
    setGerando(true);
    setAprovada(false);
    setErro(null);
    try {
      const nova = await servicoCrm.gerarRecomendacao(cliente.id);
      setAcao(nova);
      setTexto(aplicarTom(nova.mensagem, tom));
    } catch (falha) {
      setErro((falha as Error).message);
    } finally {
      setGerando(false);
    }
  };

  const trocarTom = (novo: Tom) => {
    setTom(novo);
    setTexto(aplicarTom(acao.mensagem, novo));
  };

  const copiar = async () => {
    await navigator.clipboard?.writeText(texto);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 1500);
  };

  return (
    <Cartao
      title={
        <span className="row">
          <Icone name="sparkles" />
          Recomendação assistida
        </span>
      }
      subtitle="Simulação para a equipe de relacionamento. Valide antes de comunicar ou aplicar."
      actions={
        <span className={`badge ${acao.origem === 'llm' ? 'badge--status' : 'badge--synthetic'}`}>
          {acao.origem === 'llm'
            ? 'OpenAI · formato validado (não política)'
            : acao.origem === 'regras'
              ? 'Fallback determinístico por regras'
              : acao.origem === 'llm-indisponivel'
                ? 'OpenAI indisponível · fallback por regras'
              : 'Simulação sintética'}
        </span>
      }
    >
      <div className={`acao-ia ${gerando ? 'is-refreshing' : ''}`}>
        <div className="note note--warning" role="note">
          <Icone name="alert" size={16} />
          <span>
            <strong>Recomendação demonstrativa — não é uma oferta confirmada.</strong>{' '}
            {politicaVerificada
              ? 'O contexto de política está marcado como verificado, mas esta proposta não confirma disponibilidade nem elegibilidade individual.'
              : 'O contexto de política não está verificado; confirme as regras vigentes, disponibilidade e elegibilidade individual.'}{' '}
            Valide com um analista antes de comunicar ou aplicar qualquer benefício.
          </span>
        </div>
        <h3 className="acao-ia__titulo">{acao.titulo}</h3>

        <div className="acao-ia__metricas">
          <div>
            <span>Canal</span>
            <strong>{bloqueada ? 'Bloqueado' : acao.canal}</strong>
          </div>
          <div>
            <span>Confiança calibrada</span>
            <strong className="tabular">{acao.confianca === null ? 'Não disponível' : formatPercentual(acao.confianca)}</strong>
          </div>
          <div>
            <span>Efeito causal estimado</span>
            <strong className="tabular">
              {acao.impactoEstimado.reducaoRiscoPp === null
                ? 'Não estimado'
                : formatSinal(-acao.impactoEstimado.reducaoRiscoPp, ' p.p.')}
            </strong>
          </div>
          <div>
            <span>Receita protegida</span>
            <strong className="tabular">{formatBRLCompacto(acao.impactoEstimado.receitaProtegida)}</strong>
          </div>
        </div>

        <div>
          <h4>Por que esta ação</h4>
          <ul>
            {acao.justificativa.map((j) => (
              <li key={j}>{j}</li>
            ))}
          </ul>
        </div>

        {bloqueada && (
          <div className="note note--warning">
            <Icone name="lock" size={16} />
            <span>
              {cliente.consentimentoMarketing === false
                ? 'Consentimento de marketing registrado como ausente. Não envie comunicação promocional.'
                : 'Consentimento de marketing não está disponível. Verifique a autorização antes de qualquer envio.'}
            </span>
          </div>
        )}
        {erro && (
          <div className="note note--warning" role="alert">
            <Icone name="alert" size={16} />
            <span>Não foi possível gerar nova recomendação: {erro}</span>
          </div>
        )}

        <div>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 6 }}>
            <h4 style={{ margin: 0 }}>Mensagem redigida</h4>
            <div className="segmented" role="group" aria-label="Tom da mensagem">
              {TONS.map((t) => (
                <button key={t.id} type="button" aria-pressed={tom === t.id} onClick={() => trocarTom(t.id)}>
                  {t.rotulo}
                </button>
              ))}
            </div>
          </div>
          <label className="sr-only" htmlFor={`mensagem-${cliente.id}`}>
            Mensagem para o cliente
          </label>
          <textarea
            id={`mensagem-${cliente.id}`}
            className="mensagem"
            value={texto}
            onChange={(e) => {
              setTexto(e.target.value);
              setAprovada(false);
            }}
          />
        </div>

        <div className="row">
          <button
            type="button"
            className="btn btn--primary"
            disabled={bloqueada || aprovada || gerando}
            onClick={() => setAprovada(true)}
          >
            <Icone name="check" size={16} />
            {aprovada ? 'Aprovada' : 'Aprovar ação'}
          </button>
          <button type="button" className="btn" disabled={gerando} onClick={regenerar}>
            <Icone name="refresh" size={16} />
            {gerando ? 'Gerando…' : 'Gerar nova recomendação'}
          </button>
          <button type="button" className="btn" onClick={copiar}>
            <Icone name="copy" size={16} />
            {copiado ? 'Copiado' : 'Copiar'}
          </button>
        </div>

        {aprovada && (
          <div className="note" role="status">
            <Icone name="check" size={16} />
            <span>
              Ação aprovada por <strong>{usuario?.nome ?? 'você'}</strong> e encaminhada para a fila de campanhas
              (simulação).
            </span>
          </div>
        )}

        <div className="regras">
          <strong>Contexto de política</strong>{' '}
          {politicaVerificada
            ? '(marcado como verificado; elegibilidade individual não confirmada):'
            : '(premissas ilustrativas não verificadas):'}
          <ul style={{ fontSize: 12, marginTop: 4 }}>
            {acao.regrasFidelidade.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      </div>
    </Cartao>
  );
}
