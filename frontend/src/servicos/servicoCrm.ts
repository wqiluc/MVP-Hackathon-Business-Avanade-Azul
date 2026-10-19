import { apiUrl, configuracaoAusente, MENSAGEM_CONFIGURACAO_AUSENTE } from './configuracaoApi';
import { criarFonteApi } from './fonteApi';
import type { FonteDeDadosCrm } from './fonteDeDados';
import { fonteSintetica } from './fonteSintetica';

export { usandoDadosSinteticos } from './configuracaoApi';

const rejeitar = (): Promise<never> => Promise.reject(new Error(MENSAGEM_CONFIGURACAO_AUSENTE));

const fonteIndisponivel: FonteDeDadosCrm = {
  listarClientes: rejeitar,
  obterCliente: rejeitar,
  obterResumoDashboard: rejeitar,
  gerarRecomendacao: rejeitar,
  enviarBaseClientes: rejeitar,
  obterModelo: rejeitar,
};

export const servicoCrm: FonteDeDadosCrm = apiUrl
  ? criarFonteApi(apiUrl)
  : configuracaoAusente
    ? fonteIndisponivel
    : fonteSintetica;
