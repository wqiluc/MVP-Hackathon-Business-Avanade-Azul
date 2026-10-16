/**
 * AeroShield AI — Universal Environment Setup & One-Command Runner
 * Detecta OS, valida ferramentas (Python, Node, npm), configura .venv,
 * instala dependências ausentes e sobe Backend + Frontend em paralelo.
 */

const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Cores para o terminal
const colors = {
  reset: '\x1b[0m',
  cyan: '\x1b[36m',
  yellow: '\x1b[33m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  gray: '\x1b[90m'
};

function log(msg, color = colors.cyan) {
  console.log(`${color}${msg}${colors.reset}`);
}

const isWindows = os.platform() === 'win32';
const backendDir = path.join(__dirname, 'backend');
const frontendDir = path.join(__dirname, 'frontend');
const venvDir = path.join(backendDir, '.venv');
const venvPython = isWindows 
  ? path.join(venvDir, 'Scripts', 'python.exe')
  : path.join(venvDir, 'bin', 'python');

// 1. Validar Ferramentas do Sistema Operacional
function checkRequirement(command, name) {
  try {
    execSync(command, { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

log(`\n🚀 AeroShield AI — Iniciando Verificação Universal [OS: ${os.platform()}]...`);

// Checar Python
let pythonCmd = 'python3';
if (!checkRequirement('python3 --version', 'Python 3')) {
  if (checkRequirement('python --version', 'Python')) {
    pythonCmd = 'python';
  } else {
    log('❌ Erro: Python não encontrado no sistema. Por favor, instale o Python 3.12+.', colors.red);
    process.exit(1);
  }
}

// Checar Node / npm
if (!checkRequirement('node --version', 'Node.js') || !checkRequirement('npm --version', 'npm')) {
  log('❌ Erro: Node.js ou npm não encontrados. Por favor, instale o Node.js v18+.', colors.red);
  process.exit(1);
}

log('✅ Pré-requisitos de sistema verificados (Python & Node.js).', colors.green);

// 2. Configurar Backend (.venv e dependências)
log('\n📦 [1/2] Verificando e Configurando o Backend (Python)...', colors.yellow);

if (!fs.existsSync(venvDir)) {
  log('   -> Criando ambiente virtual Python (.venv)...', colors.gray);
  execSync(`${pythonCmd} -m venv "${venvDir}"`, { stdio: 'inherit' });
}

log('   -> Verificando e instalando dependências do Python...', colors.gray);
const pipCmd = `"${venvPython}" -m pip`;
execSync(`${pipCmd} install --upgrade pip --quiet`, { stdio: 'inherit' });
execSync(`${pipCmd} install -r "${path.join(backendDir, 'requirements.txt')}"`, { stdio: 'inherit' });

// 3. Configurar Frontend (node_modules)
log('\n🎨 [2/2] Verificando e Configurando o Frontend (Node.js)...', colors.yellow);

const frontendNodeModules = path.join(frontendDir, 'node_modules');
if (!fs.existsSync(frontendNodeModules)) {
  log('   -> Instalando dependências npm no frontend...', colors.gray);
  execSync('npm install', { cwd: frontendDir, stdio: 'inherit' });
} else {
  log('   -> Dependências do frontend já instaladas.', colors.gray);
}

// 4. Iniciar os Serviços em Paralelo
log('\n⚡ Subindo a aplicação completa...', colors.green);
log('   -> Backend FastAPI : http://localhost:8000', colors.cyan);
log('   -> Swagger UI Docs  : http://localhost:8000/docs', colors.cyan);
log('   -> Frontend React   : http://localhost:5173\n', colors.cyan);

// Rodar Backend
const backendProcess = spawn(`"${venvPython}"`, ['run.py'], {
  cwd: backendDir,
  shell: true,
  stdio: 'inherit'
});

// Rodar Frontend
const frontendProcess = spawn('npm', ['run', 'dev'], {
  cwd: frontendDir,
  shell: true,
  stdio: 'inherit'
});

// Encerrar ambos os processos graciosamente no CTRL+C
process.on('SIGINT', () => {
  log('\n🛑 Encerrando todos os serviços...', colors.yellow);
  backendProcess.kill();
  frontendProcess.kill();
  process.exit(0);
});
