/**
 * CRM de Alto Valor — Universal Environment Setup & One-Command Runner
 * Detecta OS, valida ferramentas (Python, Node, npm), configura .venv,
 * instala dependências ausentes e sobe Backend + Frontend em paralelo.
 */

const { execSync, execFileSync, spawn } = require('child_process');
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
const mlflowDataDir = path.join(__dirname, 'infrastructure', 'mlflow', 'data');
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

log(`\n🚀 CRM de Alto Valor — Iniciando Verificação Universal [OS: ${os.platform()}]...`);

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

const pythonVersion = execFileSync(
  pythonCmd,
  ['-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'],
  { encoding: 'utf8' }
).trim();
const [pythonMajor, pythonMinor] = pythonVersion.split('.').map(Number);
if (pythonMajor < 3 || (pythonMajor === 3 && pythonMinor < 12)) {
  log(`❌ Erro: Python 3.12+ é necessário. Versão encontrada: ${pythonVersion}.`, colors.red);
  process.exit(1);
}

// Checar Node / npm
if (!checkRequirement('node --version', 'Node.js') || !checkRequirement('npm --version', 'npm')) {
  log('❌ Erro: Node.js ou npm não encontrados. Use Node.js 22.12+ ou 24 LTS.', colors.red);
  process.exit(1);
}

const [nodeMajor, nodeMinor] = process.versions.node.split('.').map(Number);
if (!((nodeMajor === 20 && nodeMinor >= 19) || (nodeMajor === 22 && nodeMinor >= 12) || nodeMajor >= 23)) {
  log('❌ Vite exige Node.js 20.19+, 22.12+ ou 24+. Recomendado: 24 LTS.', colors.red);
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
execSync(`${pipCmd} install --no-deps -e "${__dirname}"`, { stdio: 'inherit' });

// 3. Configurar Frontend (node_modules)
log('\n🎨 [2/2] Verificando e Configurando o Frontend (Node.js)...', colors.yellow);

const frontendNodeModules = path.join(frontendDir, 'node_modules');
if (!fs.existsSync(frontendNodeModules)) {
  log('   -> Instalando dependências npm no frontend...', colors.gray);
  execSync('npm install', { cwd: frontendDir, stdio: 'inherit' });
} else {
  log('   -> Dependências do frontend já instaladas.', colors.gray);
}

// Integração: aponta o front para a API real (sem sobrescrever um .env existente)
const frontendEnv = path.join(frontendDir, '.env');
if (!fs.existsSync(frontendEnv)) {
  fs.writeFileSync(frontendEnv, 'VITE_API_URL=http://localhost:8000/api/v1\n');
  log('   -> frontend/.env criado (VITE_API_URL=http://localhost:8000/api/v1).', colors.gray);
}
if (
  !fs.existsSync(path.join(backendDir, '.env')) &&
  !fs.existsSync(path.join(__dirname, '.env')) &&
  fs.existsSync(path.join(backendDir, '.env.example'))
) {
  fs.copyFileSync(path.join(backendDir, '.env.example'), path.join(backendDir, '.env'));
}

function readConfiguredEnv(name, fallback) {
  if (process.env[name] !== undefined) return process.env[name];
  for (const envPath of [
    path.join(backendDir, '.env'),
    path.join(__dirname, '.env'),
  ]) {
    if (!fs.existsSync(envPath)) continue;
    const line = fs.readFileSync(envPath, 'utf8')
      .split(/\r?\n/)
      .find(entry => entry.trim().startsWith(`${name}=`));
    if (line) {
      return line.slice(line.indexOf('=') + 1).trim().replace(/^['"]|['"]$/g, '');
    }
  }
  return fallback;
}

// 4. Iniciar MLflow Tracking quando a URI apontar para o serviço local padrão
const trackingUri = readConfiguredEnv('MLFLOW_TRACKING_URI', '');
let mlflowProcess = null;
try {
  const trackingUrl = trackingUri.trim() ? new URL(trackingUri) : null;
  const isLocalTracking =
    trackingUrl !== null &&
    trackingUrl.protocol === 'http:' &&
    ['localhost', '127.0.0.1', '::1'].includes(trackingUrl.hostname) &&
    (trackingUrl.pathname === '/' || trackingUrl.pathname === '');
  if (isLocalTracking) {
    const trackingPort = trackingUrl.port || '80';
    fs.mkdirSync(path.join(mlflowDataDir, 'artifacts'), { recursive: true });
    const trackingDb = path.join(mlflowDataDir, 'tracking.db').replace(/\\/g, '/');
    const artifactsUri = require('url').pathToFileURL(
      path.join(mlflowDataDir, 'artifacts')
    ).href;
    mlflowProcess = spawn(venvPython, [
      '-m', 'mlflow', 'server',
      '--backend-store-uri', `sqlite:///${path.resolve(trackingDb)}`,
      '--artifacts-destination', artifactsUri,
      '--host', trackingUrl.hostname === 'localhost' ? '127.0.0.1' : trackingUrl.hostname,
      '--port', trackingPort,
      '--workers', '1'
    ], {
      cwd: __dirname,
      stdio: 'inherit'
    });
    log('   -> MLflow Tracking local habilitado.', colors.cyan);
  } else if (trackingUrl) {
    log('   -> MLflow Tracking externo configurado (disponibilidade não verificada).', colors.cyan);
  } else {
    log('   -> MLflow desabilitado; desenvolvimento local sem scores de modelo.', colors.gray);
  }
} catch {
  log('❌ MLFLOW_TRACKING_URI inválida. Verifique a configuração.', colors.red);
  process.exit(1);
}

// 5. Iniciar os Serviços da aplicação em paralelo
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
  if (mlflowProcess) mlflowProcess.kill();
  backendProcess.kill();
  frontendProcess.kill();
  process.exit(0);
});
