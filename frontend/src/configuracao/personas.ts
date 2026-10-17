import type { Persona, PersonaId } from '../tipos/crm';

// Personas resultantes da segmentação comportamental (clusterização sobre
// frequência, ticket, recência, tendência e perfil de rota). Nenhum atributo
// sensível (gênero, idade, renda, etnia) entra na segmentação.
export const PERSONAS: Record<PersonaId, Persona> = {
  'executivo-frequente': {
    id: 'executivo-frequente',
    nome: 'Executivo frequente',
    descricao:
      'Voa a trabalho várias vezes ao mês em rotas de negócios. Alta receita e alta influência sobre a escolha da empresa.',
    necessidades: ['Pontualidade', 'Flexibilidade de remarcação', 'Conforto a bordo'],
    acaoRecomendada: 'Upgrade de assento e benefícios de categoria',
  },
  'lazer-premium': {
    id: 'lazer-premium',
    nome: 'Lazer premium',
    descricao:
      'Viaja poucas vezes ao ano, mas com ticket alto, em família e para destinos turísticos e internacionais.',
    necessidades: ['Ofertas antecipadas', 'Pacotes completos', 'Bagagem e assentos juntos'],
    acaoRecomendada: 'Oferta personalizada para a rota favorita',
  },
  'regional-conectado': {
    id: 'regional-conectado',
    nome: 'Regional conectado',
    descricao:
      'Mora em cidade onde a Azul é a principal conexão aérea. Frequência média e alta dependência da malha regional.',
    necessidades: ['Conexões confiáveis', 'Informação proativa', 'Reconhecimento da fidelidade'],
    acaoRecomendada: 'Comunicação personalizada e bônus de pontos',
  },
  'potencial-ascensao': {
    id: 'potencial-ascensao',
    nome: 'Potencial em ascensão',
    descricao:
      'Frequência crescendo nos últimos meses e perto de subir de categoria. Maior potencial de CLV futuro.',
    necessidades: ['Clareza sobre a próxima categoria', 'Incentivo para concentrar voos', 'Primeiros benefícios'],
    acaoRecomendada: 'Desafio de categoria com bônus de pontos',
  },
};

export const PERSONA_IDS = Object.keys(PERSONAS) as PersonaId[];
