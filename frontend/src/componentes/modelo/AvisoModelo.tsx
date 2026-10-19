import { useBuscaAssincrona } from '../../hooks/useBuscaAssincrona';
import { servicoCrm } from '../../servicos/servicoCrm';
import { formatData, formatPercentual } from '../../utilitarios/formatacao';
import { Icone } from '../ui/Icone';

/** Transparência: qual modelo gerou os scores exibidos e como ele performa. */
export function AvisoModelo() {
  const { data: modelo } = useBuscaAssincrona(() => servicoCrm.obterModelo(), []);
  if (!modelo) return null;

  const registrado = modelo.status !== 'aguardando-registro';
  const servingConfigurado = modelo.status === 'serving-configurado';
  return (
    <div className={`note ${servingConfigurado ? '' : 'note--warning'}`}>
      <Icone name={servingConfigurado ? 'shield' : 'info'} size={16} />
      <span>
        <strong>{modelo.nome}</strong>
        {registrado ? (
          <>
            {' '}
            · versão {modelo.versao} registrada no {modelo.plataforma}
            {modelo.acuracia !== null && <> · acurácia {formatPercentual(modelo.acuracia, 1)}</>}
            {modelo.auc !== null && <> · AUC {modelo.auc.toLocaleString('pt-BR', { maximumFractionDigits: 3 })}</>}
            {modelo.treinadoEm && <> · treinado em {formatData(modelo.treinadoEm)}</>}
            {servingConfigurado
              ? ' · URL de Serving configurada (disponibilidade não verificada)'
              : ' · aguardando configuração do MLflow Serving'}
          </>
        ) : (
          <>
            {' '}
            · aguardando registro do modelo no {modelo.plataforma}. Os scores ficam indisponíveis até o treino e o
            Serving.
          </>
        )}
        {' '}O alvo é high_risk_flag derivado por regras, não churn observado.
      </span>
    </div>
  );
}
