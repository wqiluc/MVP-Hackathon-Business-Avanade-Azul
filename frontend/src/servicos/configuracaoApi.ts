// Defina VITE_API_URL (ver .env.example) para usar o backend real.
// Sem ela, a base sintética só é usada em desenvolvimento ou quando
// VITE_ENABLE_DEMO_MODE=true for definido explicitamente; em produção
// o frontend falha de forma fechada. Nunca coloque chaves de API aqui.
export const apiUrl = (import.meta.env.VITE_API_URL as string | undefined)?.trim() || undefined;

const demoExplicito = (import.meta.env.VITE_ENABLE_DEMO_MODE as string | undefined)?.trim() === 'true';

export const usandoDadosSinteticos = !apiUrl && (import.meta.env.DEV || demoExplicito);

export const configuracaoAusente = !apiUrl && !usandoDadosSinteticos;

export const MENSAGEM_CONFIGURACAO_AUSENTE =
  'Backend não configurado: defina VITE_API_URL ou habilite explicitamente VITE_ENABLE_DEMO_MODE=true.';
