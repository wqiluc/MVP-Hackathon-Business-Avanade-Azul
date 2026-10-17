import { useBuscaAssincrona } from '../../hooks/useBuscaAssincrona';
import { servicoCrm } from '../../servicos/servicoCrm';
import { formatData, formatPercentual } from '../../utilitarios/formatacao';
import { Icone } from '../ui/Icone';

/** Transparência: qual modelo gerou os scores exibidos e como ele performa. */
export function AvisoModelo() {
  const { data: modelo } = useBuscaAssincrona(() => servicoCrm.obterModelo(), []);
  if (!modelo) return null;

  const emProducao = modelo.status === 'em-producao';
  return (
    <div className={`note ${emProducao ? '' : 'note--warning'}`}>
      <Icone name={emProducao ? 'shield' : 'info'} size={16} />
      <span>
        <strong>{modelo.nome}</strong>
        {emProducao ? (
          <>
            {' '}
            · versão {modelo.versao} no {modelo.plataforma}
            {modelo.acuracia !== null && <> · acurácia {formatPercentual(modelo.acuracia, 1)}</>}
            {modelo.auc !== null && <> · AUC {modelo.auc.toLocaleString('pt-BR', { maximumFractionDigits: 3 })}</>}
            {modelo.treinadoEm && <> · treinado em {formatData(modelo.treinadoEm)}</>}
          </>
        ) : (
          <>
            {' '}
            · aguardando modelo registrado no {modelo.plataforma}. Meta de acurácia:{' '}
            {formatPercentual(modelo.metaAcuracia)} ou mais.
          </>
        )}
      </span>
    </div>
  );
}
