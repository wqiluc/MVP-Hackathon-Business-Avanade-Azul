import type {
  Cliente,
  ClienteResumo,
  FiltroClientes,
  ModeloInfo,
  ProximaAcao,
  ReciboIngestao,
  ResumoDashboard,
} from '../tipos/crm';

/**
 * Contrato entre o front-end e o backend.
 * - fonteSintetica: base sintética local (padrão do protótipo)
 * - fonteApi: backend integrado ao Data Lake, MLflow e workflow determinístico
 */
export interface FonteDeDadosCrm {
  listarClientes(filtro?: FiltroClientes): Promise<ClienteResumo[]>;
  obterCliente(id: string): Promise<Cliente | null>;
  obterResumoDashboard(filtro?: FiltroClientes): Promise<ResumoDashboard>;
  /** Pede ao backend uma nova recomendação baseada no score do modelo e em regras. */
  gerarRecomendacao(id: string): Promise<ProximaAcao>;
  /** Envia uma base de clientes (Excel, CSV ou JSON) para ingestão na camada Bronze. */
  enviarBaseClientes(arquivo: File): Promise<ReciboIngestao>;
  obterModelo(): Promise<ModeloInfo>;
}
