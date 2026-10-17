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
 * O backend combina o modelo (MLflow) com IA generativa; aqui o analista
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

  const bloqueada = acao.canal.startsWith('Bloqueado');

  const regenerar = async () => {
    setGerando(true);
    setAprovada(false);
    try {
      const nova = await servicoCrm.gerarRecomendacao(cliente.id);
      setAcao(nova);
      setTexto(aplicarTom(nova.mensagem, tom));
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
          Recomendação da IA
        </span>
      }
      subtitle="Sugestão para a equipe de relacionamento. Revise antes de aprovar."
      actions={
        <span className="badge badge--synthetic">
          {acao.origem === 'ia-generativa' ? 'IA generativa' : 'Simulação local'}
        </span>
      }
    >
      <div className={`acao-ia ${gerando ? 'is-refreshing' : ''}`}>
        <h3 className="acao-ia__titulo">{acao.titulo}</h3>

        <div className="acao-ia__metricas">
          <div>
            <span>Canal</span>
            <strong>{bloqueada ? 'Bloqueado' : acao.canal}</strong>
          </div>
          <div>
            <span>Confiança</span>
            <strong className="tabular">{formatPercentual(acao.confianca)}</strong>
          </div>
          <div>
            <span>Efeito no risco</span>
            <strong className="tabular">{formatSinal(-acao.impactoEstimado.reducaoRiscoPp, ' p.p.')}</strong>
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
              Cliente sem consentimento de marketing (LGPD). A mensagem promocional só pode ser enviada após opt-in;
              até lá, use apenas contato de serviço.
            </span>
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
          <strong>Base de conhecimento consultada</strong> (regulamento público do Azul Fidelidade, premissas a
          validar):
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
