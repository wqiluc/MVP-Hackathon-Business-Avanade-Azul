import { useEffect, useState } from 'react';
import { lerPreferenciaTema, salvarPreferenciaTema, temaDoSistema } from '../../utilitarios/tema';
import type { Tema } from '../../utilitarios/tema';
import { Icone } from '../ui/Icone';

export function AlternadorTema({ lateral = false }: { lateral?: boolean }) {
  const [preferencia, setPreferencia] = useState(lerPreferenciaTema);
  const [tema, setTema] = useState<Tema>(() => preferencia ?? temaDoSistema());
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = tema;
  }, [tema]);

  useEffect(() => {
    if (preferencia !== null) return;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const atualizar = () => setTema(media.matches ? 'dark' : 'light');
    atualizar();
    media.addEventListener('change', atualizar);
    return () => media.removeEventListener('change', atualizar);
  }, [preferencia]);

  function alternar() {
    const proximo = tema === 'dark' ? 'light' : 'dark';
    setTema(proximo);
    setPreferencia(proximo);
    setErro(null);
    try {
      salvarPreferenciaTema(proximo);
    } catch (falha) {
      if (!(falha instanceof DOMException)) throw falha;
      console.warn('Não foi possível salvar a preferência de tema.', falha);
      setErro('Tema aplicado nesta página, mas não foi possível salvar a preferência.');
    }
  }

  return (
    <div>
      <button
        type="button"
        className={lateral ? 'nav-link theme-toggle' : 'btn'}
        aria-label="Modo escuro"
        aria-pressed={tema === 'dark'}
        onClick={alternar}
      >
        <Icone name={tema === 'dark' ? 'sun' : 'moon'} />
        Ativar modo {tema === 'dark' ? 'claro' : 'escuro'}
      </button>
      {erro && <small role="status">{erro}</small>}
    </div>
  );
}
