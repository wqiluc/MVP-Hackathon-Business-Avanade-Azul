import { PERSONAS } from '../../configuracao/personas';
import type { PersonaId, ResumoDashboard } from '../../tipos/crm';
import { formatBRLCompacto } from '../../utilitarios/formatacao';
import { SeloRisco } from '../ui/Selos';

interface SegmentosPersonaProps {
  dados: ResumoDashboard['porPersona'];
  selecionada?: PersonaId;
  onSelecionar: (persona: PersonaId | undefined) => void;
}

/** CLV total por persona (barra de série única) + tamanho e risco médio do segmento. */
export function SegmentosPersona({ dados, selecionada, onSelecionar }: SegmentosPersonaProps) {
  const max = Math.max(1, ...dados.map((d) => d.clvTotal));
  return (
    <div className="segmentos">
      {dados.map((d) => {
        const persona = PERSONAS[d.persona];
        const ativa = selecionada === d.persona;
        return (
          <button
            key={d.persona}
            type="button"
            className={`segmento ${ativa ? 'segmento--ativo' : ''}`}
            aria-pressed={ativa}
            onClick={() => onSelecionar(ativa ? undefined : d.persona)}
            title={ativa ? 'Remover filtro de persona' : `Filtrar por ${persona.nome}`}
          >
            <div className="segmento__topo">
              <strong>{persona.nome}</strong>
              <span className="muted tabular">{d.clientes} clientes</span>
            </div>
            <div className="hbar" style={{ gridTemplateColumns: '1fr auto' }}>
              <div className="hbar__track">
                <div className="hbar__fill" style={{ width: `${(d.clvTotal / max) * 100}%` }} />
              </div>
              <span className="hbar__value">{formatBRLCompacto(d.clvTotal)}</span>
            </div>
            <div className="segmento__rodape">
              <span className="muted">Risco médio</span>
              <SeloRisco risco={d.riscoMedio} />
              <span className="muted segmento__acao">→ {persona.acaoRecomendada}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
