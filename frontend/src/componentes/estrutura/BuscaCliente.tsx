import { useId, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useBuscaAssincrona } from '../../hooks/useBuscaAssincrona';
import { servicoCrm } from '../../servicos/servicoCrm';
import { SeloCategoria } from '../ui/Selos';
import { Icone } from '../ui/Icone';

const semAcento = (texto: string) =>
  texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

export function BuscaCliente({ placeholder = 'Buscar cliente por nome ou ID' }: { placeholder?: string }) {
  const navigate = useNavigate();
  const listaId = useId();
  const { data: clientes = [] } = useBuscaAssincrona(() => servicoCrm.listarClientes(), []);
  const [termo, setTermo] = useState('');
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(0);

  const resultados = useMemo(() => {
    const t = semAcento(termo.trim());
    if (!t) return [];
    return clientes.filter((c) => semAcento(c.nome).includes(t) || c.id.toLowerCase().includes(t)).slice(0, 8);
  }, [clientes, termo]);

  const abrir = (id: string) => {
    setTermo('');
    setAberto(false);
    navigate(`/clientes/${id}`);
  };

  const mostrarLista = aberto && resultados.length > 0;

  return (
    <div className="search">
      <label className="search__input">
        <Icone name="search" />
        <span className="sr-only">{placeholder}</span>
        <input
          type="search"
          role="combobox"
          aria-expanded={mostrarLista}
          aria-controls={listaId}
          aria-autocomplete="list"
          aria-activedescendant={mostrarLista ? `${listaId}-${ativo}` : undefined}
          placeholder={placeholder}
          value={termo}
          onChange={(e) => {
            setTermo(e.target.value);
            setAtivo(0);
            setAberto(true);
          }}
          onFocus={() => setAberto(true)}
          onBlur={() => setTimeout(() => setAberto(false), 120)}
          onKeyDown={(e) => {
            if (!mostrarLista) return;
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              setAtivo((i) => (i + 1) % resultados.length);
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              setAtivo((i) => (i - 1 + resultados.length) % resultados.length);
            } else if (e.key === 'Enter') {
              e.preventDefault();
              abrir(resultados[ativo].id);
            } else if (e.key === 'Escape') {
              setAberto(false);
            }
          }}
        />
      </label>
      {mostrarLista && (
        <ul className="search__list" id={listaId} role="listbox">
          {resultados.map((c, i) => (
            <li
              key={c.id}
              id={`${listaId}-${i}`}
              role="option"
              aria-selected={i === ativo}
              className="search__option"
              onMouseDown={(e) => {
                e.preventDefault();
                abrir(c.id);
              }}
              onMouseEnter={() => setAtivo(i)}
            >
              <span>
                {c.nome} <span className="muted tabular">· {c.id}</span>
              </span>
              <SeloCategoria tier={c.tier} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
