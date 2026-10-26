import { useRef, useState } from 'react';
import { servicoCrm } from '../../servicos/servicoCrm';
import type { ReciboIngestao } from '../../tipos/crm';
import { Icone } from '../ui/Icone';

const FORMATOS = '.xlsx,.xls,.csv,.json';

/** Envia uma base de clientes ao backend. */
export function EnvioBaseClientes() {
  const entrada = useRef<HTMLInputElement>(null);
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [recibo, setRecibo] = useState<ReciboIngestao | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const enviar = async () => {
    if (!arquivo) return;
    setEnviando(true);
    setErro(null);
    setRecibo(null);
    try {
      setRecibo(await servicoCrm.enviarBaseClientes(arquivo));
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="modulo">
      <span className="modulo__icon">
        <Icone name="database" size={20} />
      </span>
      <h3>Enviar base de clientes</h3>
      <p>
        CSV, Excel ou JSON (máximo 10 MB). Colunas fora dos contratos aceitos são descartadas antes da Bronze.
        O upload canônico tem seis campos e não fornece as 52 features dos modelos; score e CLV ficam indisponíveis
        até uma origem compatível fornecer o contrato completo.
      </p>

      <input
        ref={entrada}
        type="file"
        accept={FORMATOS}
        className="sr-only"
        onChange={(e) => {
          setArquivo(e.target.files?.[0] ?? null);
          setRecibo(null);
          setErro(null);
        }}
      />
      <div className="row">
        <button type="button" className="btn" onClick={() => entrada.current?.click()}>
          {arquivo ? 'Trocar arquivo' : 'Escolher arquivo'}
        </button>
        <button type="button" className="btn btn--primary" disabled={!arquivo || enviando} onClick={enviar}>
          <Icone name="send" size={16} />
          {enviando ? 'Enviando…' : 'Enviar'}
        </button>
      </div>
      {arquivo && !recibo && (
        <small className="muted">
          {arquivo.name} · {(arquivo.size / 1024).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} KB
        </small>
      )}
      {recibo && (
        <div className={`note ${recibo.status === 'simulado' ? 'note--warning' : ''}`} role="status">
          <Icone name={recibo.status === 'simulado' ? 'info' : 'check'} size={16} />
          <span>
            <strong>{recibo.arquivo}</strong> — {recibo.mensagem}
          </span>
        </div>
      )}
      {erro && (
        <div className="note note--warning" role="alert">
          <Icone name="alert" size={16} />
          <span>{erro}</span>
        </div>
      )}
    </div>
  );
}
