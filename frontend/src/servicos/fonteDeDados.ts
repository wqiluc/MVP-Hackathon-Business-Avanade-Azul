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
 * - fonteApi: backend integrado ao Snowflake (camada Ouro), MLflow e IA generativa
 */
export interface FonteDeDadosCrm {
  listarClientes(filtro?: FiltroClientes): Promise<ClienteResumo[]>;
  obterCliente(id: string): Promise<Cliente | null>;
  obterResumoDashboard(filtro?: FiltroClientes): Promise<ResumoDashboard>;
  /** Pede ao backend uma nova recomendação (modelo + IA generativa) para o cliente. */
  gerarRecomendacao(id: string): Promise<ProximaAcao>;
  /** Envia uma base de clientes (Excel, CSV ou JSON) para ingestão na camada Bronze. */
  enviarBaseClientes(arquivo: File): Promise<ReciboIngestao>;
  obterModelo(): Promise<ModeloInfo>;
}
