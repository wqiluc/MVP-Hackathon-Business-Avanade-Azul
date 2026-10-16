import { apiUrl } from './configuracaoApi';
import { criarFonteApi } from './fonteApi';
import type { FonteDeDadosCrm } from './fonteDeDados';
import { fonteSintetica } from './fonteSintetica';

export { usandoDadosSinteticos } from './configuracaoApi';

export const servicoCrm: FonteDeDadosCrm = apiUrl ? criarFonteApi(apiUrl) : fonteSintetica;
