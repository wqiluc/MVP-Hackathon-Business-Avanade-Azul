import { useEffect, useState } from 'react';

interface EstadoAsync<T> {
  data: T | undefined;
  carregando: boolean;
  erro: Error | undefined;
}

/**
 * Executa uma busca assíncrona e mantém o último resultado enquanto recarrega,
 * para que filtros não causem "piscar" de tela.
 */
export function useBuscaAssincrona<T>(buscar: () => Promise<T>, deps: unknown[]): EstadoAsync<T> {
  const [estado, setEstado] = useState<EstadoAsync<T>>({ data: undefined, carregando: true, erro: undefined });

  // As dependências vêm do chamador, como em useEffect.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    let ativo = true;
    setEstado((anterior) => ({ ...anterior, carregando: true, erro: undefined }));
    buscar()
      .then((data) => ativo && setEstado({ data, carregando: false, erro: undefined }))
      .catch((erro: Error) => ativo && setEstado((anterior) => ({ ...anterior, carregando: false, erro })));
    return () => {
      ativo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return estado;
}
