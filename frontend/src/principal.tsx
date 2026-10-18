import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Aplicacao } from './Aplicacao';
import './estilos/global.css';

const temaSalvo = window.localStorage.getItem('azul-crm-theme');
const temaInicial =
  temaSalvo === 'light' || temaSalvo === 'dark'
    ? temaSalvo
    : window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light';
document.documentElement.dataset.theme = temaInicial;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Aplicacao />
  </StrictMode>,
);
