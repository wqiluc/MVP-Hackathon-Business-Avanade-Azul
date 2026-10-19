import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Icone } from '../componentes/ui/Icone';
import { useAutenticacao } from '../hooks/useAutenticacao';
import logo from '../imagens/logo-azul.jpg';
import { usandoDadosSinteticos } from '../servicos/configuracaoApi';
import './PaginaLogin.css';

const DESTAQUES = [
  { icone: 'chart', texto: 'Quem são os clientes de alto valor e quanto valem em 24 meses' },
  { icone: 'alert', texto: 'Classificação de high_risk_flag — não representa churn observado' },
  { icone: 'sparkles', texto: 'OpenAI estruturada quando configurada; regras como fallback' },
] as const;

export function PaginaLogin() {
  const { usuario, entrar } = useAutenticacao();
  const navigate = useNavigate();
  const location = useLocation();
  const destino = (location.state as { de?: string } | null)?.de ?? '/';

  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  if (usuario) return <Navigate to={destino} replace />;

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !senha) {
      setErro('Informe e-mail e senha.');
      return;
    }
    setEnviando(true);
    setErro(null);
    try {
      await entrar(email, senha);
      navigate(destino, { replace: true });
    } catch (falha) {
      setErro((falha as Error).message);
      setEnviando(false);
    }
  };

  return (
    <div className="login">
      <aside className="login__marca">
        <div className="login__marca-conteudo">
          <img className="login__logo" src={logo} alt="Azul Linhas Aéreas Brasileiras" />
          <h1>CRM de Alto Valor</h1>
          <p>Ferramenta interna para as equipes de CRM, Fidelidade e Relacionamento.</p>
          <ul className="login__destaques">
            {DESTAQUES.map((d) => (
              <li key={d.texto}>
                <span className="login__destaque-icone">
                  <Icone name={d.icone} size={18} />
                </span>
                {d.texto}
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="login__painel">
        <form className="login__form" onSubmit={enviar} noValidate>
          <div>
            <h2>Entrar</h2>
            <p className="login__subtitulo">Acesso restrito às equipes internas da Azul.</p>
          </div>

          <label className="login__campo">
            E-mail corporativo
            <span className="login__entrada">
              <Icone name="mail" />
              <input
                type="email"
                name="email"
                autoComplete="username"
                placeholder="nome@empresa.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-invalid={Boolean(erro)}
                autoFocus
              />
            </span>
          </label>

          <label className="login__campo">
            Senha
            <span className="login__entrada">
              <Icone name="lock" />
              <input
                type={mostrarSenha ? 'text' : 'password'}
                name="senha"
                autoComplete="current-password"
                placeholder="Sua senha"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                aria-invalid={Boolean(erro)}
              />
              <button
                type="button"
                className="login__olho"
                onClick={() => setMostrarSenha((v) => !v)}
                aria-label={mostrarSenha ? 'Ocultar senha' : 'Mostrar senha'}
                aria-pressed={mostrarSenha}
              >
                <Icone name={mostrarSenha ? 'eyeOff' : 'eye'} />
              </button>
            </span>
          </label>

          {erro && (
            <div className="note note--warning" role="alert">
              <Icone name="alert" size={16} />
              <span>{erro}</span>
            </div>
          )}

          <button type="submit" className="btn btn--primary login__botao" disabled={enviando}>
            {enviando ? 'Entrando…' : 'Entrar'}
            {!enviando && <Icone name="arrowRight" size={16} />}
          </button>

          {usandoDadosSinteticos && (
            <div className="login__demo">
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <strong>Ambiente de demonstração</strong>
              </div>
              <p>
                Os dados são sintéticos e a autenticação é simulada localmente. Informe um e-mail e uma senha
                não vazios; isso não autentica uma conta real.
              </p>
            </div>
          )}
        </form>
      </main>
    </div>
  );
}
