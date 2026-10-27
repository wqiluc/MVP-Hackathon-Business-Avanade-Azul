import { useBuscaAssincrona } from '../../hooks/useBuscaAssincrona';
import { servicoCrm } from '../../servicos/servicoCrm';
import { formatData, formatPercentual } from '../../utilitarios/formatacao';
import { Icone } from '../ui/Icone';

/** Transparência: qual modelo gerou os scores exibidos e como ele performa. */
export function AvisoModelo() {
  const { data: modelo, erro } = useBuscaAssincrona(() => servicoCrm.obterModelo(), []);
  if (erro) {
    return (
      <div className="note note--warning" role="alert">
        Não foi possível consultar o modelo: {erro.message}
      </div>
    );
  }
  if (!modelo) return null;

  const registrado = modelo.status === 'serving-configurado' || modelo.status === 'aguardando-serving';
  const servingConfigurado = modelo.status === 'serving-configurado';
  return (
    <div className={`note ${servingConfigurado ? '' : 'note--warning'}`}>
      <Icone name={servingConfigurado ? 'shield' : 'info'} size={16} />
      <span>
        <strong>Treino legado: {modelo.nome}</strong>
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
        ) : modelo.status === 'aguardando-configuracao' ? (
          <> · integração MLflow de treinamento não configurada.</>
        ) : (
          <>
            {' '}
            · aguardando registro do modelo de treinamento no {modelo.plataforma}.
          </>
        )}
        {' '}Este fluxo treina o alvo high_risk_flag derivado por regras; o scoring do CRM usa artefatos separados
        com contratos de 52 features.
      </span>
    </div>
  );
}
