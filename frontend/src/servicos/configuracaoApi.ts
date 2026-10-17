// Defina VITE_API_URL (ver .env.example) para trocar a base sintética e o
// login de demonstração pelo backend real sem alterar nenhuma tela.
export const apiUrl = (import.meta.env.VITE_API_URL as string | undefined) || undefined;

export const usandoDadosSinteticos = !apiUrl;
