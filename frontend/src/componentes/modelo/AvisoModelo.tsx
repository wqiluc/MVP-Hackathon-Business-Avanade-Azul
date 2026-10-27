import { useBuscaAssincrona } from '../../hooks/useBuscaAssincrona';
import { servicoCrm } from '../../servicos/servicoCrm';
import { Icone } from '../ui/Icone';

/** Transparência: modelos utilizados no scoring exibido pelo CRM. */
export function AvisoModelo() {
  const { data: modelo, erro } = useBuscaAssincrona(
    () => servicoCrm.obterModelo(),
    [],
  );

  if (erro) {
    return (
      <div className="note note--warning" role="alert">
        Não foi possível consultar os modelos: {erro.message}
      </div>
    );
  }

  if (!modelo) return null;

  return (
    <div className="note">
      <Icone name="shield" size={16} />

      <span>
        <strong>Modelos de ML ativos no CRM</strong>
        {' · '}Churn e CLV avaliados com artefatos MLflow
        {' · '}contrato de 52 features
        {' · '}resultados utilizados na priorização e nas recomendações do CRM.
      </span>
    </div>
  );
}