import { useNavigate } from 'react-router-dom';
import type { ClienteResumo } from '../../tipos/crm';
import { formatBRL } from '../../utilitarios/formatacao';
import { Icone } from '../ui/Icone';
import { SeloCategoria, SeloPersona, SeloRisco } from '../ui/Selos';
import { usandoDadosSinteticos } from '../../servicos/configuracaoApi';
import { RISCO_ALTO } from '../../configuracao/fidelidade';

/** Clientes ordenados pela prioridade heurística (CLV × score disponível). */
export function TabelaPrioritarios({ clientes }: { clientes: ClienteResumo[] }) {
  const navigate = useNavigate();

  if (!clientes.length) return <p className="empty">Nenhum cliente para os filtros selecionados.</p>;

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Cliente</th>
            <th>Persona</th>
            <th>Categoria</th>
            <th className="num">CLV 24m</th>
            <th className="num">Score</th>
            <th>Score de classificação</th>
            <th>Recomendação</th>
            <th aria-label="Abrir" />
          </tr>
        </thead>
        <tbody>
          {clientes.map((c) => (
            <tr
              key={c.id}
              className={`is-link${c.riscoEvasao !== null && c.riscoEvasao >= RISCO_ALTO ? ' is-priority' : ''}`}
              tabIndex={0}
              onClick={() => navigate(`/clientes/${c.id}`)}
              onKeyDown={(e) => e.key === 'Enter' && navigate(`/clientes/${c.id}`)}
            >
              <td>
                <div className="table-client">
                  <strong>{c.nome}</strong>
                  {c.riscoEvasao !== null && c.riscoEvasao >= RISCO_ALTO && (
                    <span className="table-priority">Prioridade</span>
                  )}
                  <div className="muted tabular table-client__meta">
                    {c.id} · {c.aeroportoBase}
                  </div>
                </div>
              </td>
              <td>
                <SeloPersona persona={c.persona} />
              </td>
              <td>
                <SeloCategoria tier={c.tier} />
              </td>
              <td className="num">{formatBRL(c.clvProjetado)}</td>
              <td className="num">{c.scoreValor}</td>
              <td>
                <SeloRisco
                  risco={c.riscoEvasao}
                  origem={usandoDadosSinteticos ? 'heuristica-sintetica' : 'classificador'}
                />
              </td>
              <td style={{ minWidth: 220 }}>{c.proximaAcao}</td>
              <td>
                <Icone name="arrowRight" size={16} className="muted" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
