import { useNavigate } from 'react-router-dom';
import { useAutenticacao } from '../../hooks/useAutenticacao';
import { iniciais } from '../../utilitarios/formatacao';
import { Icone } from '../ui/Icone';

const ROTULO_PERFIL = { analista: 'Analista', gestor: 'Gestor', admin: 'Administrador' } as const;

/** Usuário logado + botão de sair. `variante="escura"` para fundos azul-marinho. */
export function MenuUsuario({ variante = 'escura' }: { variante?: 'escura' | 'clara' }) {
  const { usuario, sair } = useAutenticacao();
  const navigate = useNavigate();
  if (!usuario) return null;

  return (
    <div className={`usuario usuario--${variante}`}>
      <span className="usuario__avatar" aria-hidden="true">
        {iniciais(usuario.nome)}
      </span>
      <span className="usuario__dados">
        <strong>{usuario.nome}</strong>
        <span>
          {ROTULO_PERFIL[usuario.perfil]} · {usuario.equipe}
        </span>
      </span>
      <button
        type="button"
        className="usuario__sair"
        onClick={() => {
          sair();
          navigate('/login', { replace: true });
        }}
        aria-label="Sair"
        title="Sair"
      >
        <Icone name="logout" size={18} />
      </button>
    </div>
  );
}
