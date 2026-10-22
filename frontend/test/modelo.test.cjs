const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const { renderToStaticMarkup } = require('react-dom/server');

function renderAviso(resultado) {
  const source = path.resolve(__dirname, '../src/componentes/modelo/AvisoModelo.tsx');
  const compiled = ts.transpileModule(fs.readFileSync(source, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2023,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
  const module = { exports: {} };
  const dependencies = {
    'react/jsx-runtime': require('react/jsx-runtime'),
    '../../hooks/useBuscaAssincrona': { useBuscaAssincrona: () => resultado },
    '../../servicos/servicoCrm': { servicoCrm: {} },
    '../../utilitarios/formatacao': {
      formatData: (value) => value,
      formatPercentual: (value) => `${value * 100}%`,
    },
    '../ui/Icone': { Icone: () => null },
  };
  const load = (name) => {
    assert.ok(Object.hasOwn(dependencies, name), `Unexpected dependency: ${name}`);
    return dependencies[name];
  };
  vm.runInNewContext(`(function(require, module, exports) { ${compiled}\n})`)(load, module, module.exports);
  return renderToStaticMarkup(module.exports.AvisoModelo());
}

for (const status of ['aguardando-configuracao', 'aguardando-registro']) {
  test(`model notice never claims a registered version for ${status}`, () => {
    const html = renderAviso({ data: {
      nome: 'Classificador high_risk_flag',
      plataforma: 'MLflow',
      versao: '—',
      status,
      acuracia: null,
      auc: null,
      treinadoEm: null,
    } });
    assert.doesNotMatch(html, /versão .* registrada/);
    assert.doesNotMatch(html, /acurácia|AUC/);
    assert.match(html, /scores ficam indisponíveis/);
  });
}

test('model notice reports configured Serving without claiming availability', () => {
  const html = renderAviso({ data: {
    nome: 'crm-test-model',
    plataforma: 'MLflow',
    versao: '3',
    status: 'serving-configurado',
    acuracia: 0.8,
    auc: null,
    treinadoEm: null,
  } });
  assert.match(html, /versão 3 registrada/);
  assert.match(html, /disponibilidade não verificada/);
});

test('model notice exposes a safe API error instead of silently disappearing', () => {
  const html = renderAviso({ erro: new Error('Serviço temporariamente indisponível.') });
  assert.match(html, /role="alert"/);
  assert.match(html, /Não foi possível consultar o modelo/);
});
