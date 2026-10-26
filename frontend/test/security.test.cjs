const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const src = path.resolve(__dirname, '../src');

// Transpile the actual service modules with the existing compiler, without a browser or network.
function ambiente(overrides = {}) {
  const storage = new Map();
  const window = new EventTarget();
  window.location = { pathname: '/dashboard', assign: () => {} };
  const avisos = [];
  const globals = {
    window, Event, AbortController, Headers, FormData, URLSearchParams,
    console: { warn: (message) => avisos.push(message) },
    setTimeout, clearTimeout,
    sessionStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    },
    fetch: () => { throw new Error('Unexpected network call'); },
    ...overrides,
  };
  const cache = new Map();
  function load(file) {
    if (file.endsWith('/configuracaoApi.ts')) {
      return { apiUrl: 'https://api.test/api/v1', configuracaoAusente: false };
    }
    if (cache.has(file)) return cache.get(file).exports;
    const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023 },
    }).outputText;
    const module = { exports: {} };
    cache.set(file, module);
    const requireSource = (specifier) => {
      assert.ok(specifier.startsWith('.'), `Unexpected dependency: ${specifier}`);
      return load(path.resolve(path.dirname(file), `${specifier}.ts`));
    };
    vm.runInNewContext(`(function(require, module, exports) { ${compiled}\n})`, globals)(
      requireSource, module, module.exports,
    );
    return module.exports;
  }
  return {
    load: (file) => load(path.resolve(src, file)),
    globals, storage, window, avisos,
  };
}

function sessao(expiraEm = new Date(Date.now() + 60_000).toISOString()) {
  return {
    token: 'unit-test-token',
    expiraEm,
    usuario: { id: 'u-test', nome: 'Test', email: 'user@example.test', perfil: 'analista', equipe: 'CRM' },
  };
}

test('HTTP preserves successful JSON and forwards caller cancellation', async () => {
  let request;
  const env = ambiente({ fetch: async (_url, init) => {
    request = init;
    return new Response(JSON.stringify({ ok: true }));
  } });
  const http = env.load('servicos/http.ts');
  const controller = new AbortController();
  const result = await http.requisitarJson('https://api.test', { signal: controller.signal });
  assert.equal(result.ok, true);
  assert.ok(request.signal);
});

for (const status of [401, 403, 429, 500, 502, 503, 504]) {
  test(`HTTP ${status} is explicit, safe, and never retried`, async () => {
    let calls = 0;
    let unauthorized = 0;
    const env = ambiente({ fetch: async () => {
      calls += 1;
      return new Response(JSON.stringify({ message: 'internal stack /private/path credentials' }), {
        status, headers: { 'Retry-After': '45' },
      });
    } });
    const { requisitarJson, ErroHttpApi } = env.load('servicos/http.ts');
    await assert.rejects(requisitarJson('https://api.test', {}, {
      onUnauthorized: () => { unauthorized += 1; },
    }), (error) => {
      assert.ok(error instanceof ErroHttpApi);
      assert.equal(error.status, status);
      assert.ok(!error.message.includes('/private/path'));
      if (status === 429) {
        assert.equal(error.retryAfterSeconds, 45);
        assert.match(error.message, /45 segundos/);
      }
      return true;
    });
    assert.equal(calls, 1);
    assert.equal(unauthorized, status === 401 ? 1 : 0);
  });
}

for (const header of [null, 'invalid', '-1', new Date(Date.now() + 60_000).toUTCString()]) {
  test(`429 Retry-After handles ${header === null ? 'absence' : header}`, async () => {
    const env = ambiente({ fetch: async () => new Response('not JSON', {
      status: 429, headers: header === null ? {} : { 'Retry-After': header },
    }) });
    const { requisitarJson } = env.load('servicos/http.ts');
    await assert.rejects(requisitarJson('https://api.test'), (error) => {
      if (header && header.includes('GMT')) assert.ok(error.retryAfterSeconds > 0 && error.retryAfterSeconds <= 60);
      else assert.equal(error.retryAfterSeconds, null);
      assert.match(error.message, /Limite/);
      return true;
    });
  });
}

test('HTTP preserves useful upload contract errors', async () => {
  const env = ambiente({ fetch: async () => new Response(JSON.stringify({
    message: 'Arquivo incompatível.', missing_columns: ['tier'], invalid_columns: ['gasto_total'],
  }), { status: 422 }) });
  await assert.rejects(env.load('servicos/http.ts').requisitarJson('https://api.test'), (error) => {
    assert.match(error.message, /Colunas ausentes: tier/);
    assert.match(error.message, /Colunas inválidas: gasto_total/);
    return true;
  });
});

test('network error is safe and distinct from HTTP errors', async () => {
  const env = ambiente({ fetch: async () => { throw new TypeError('sensitive URL'); } });
  await assert.rejects(env.load('servicos/http.ts').requisitarJson('https://api.test'), (error) => {
    assert.equal(error.tipo, 'network');
    assert.ok(!error.message.includes('sensitive'));
    return true;
  });
});

test('HTTP timeout aborts the request and cleans its timer', async () => {
  let cleared = false;
  const env = ambiente({
    setTimeout: (callback, ms) => {
      assert.equal(ms, 60_000);
      queueMicrotask(callback);
      return 1;
    },
    clearTimeout: () => { cleared = true; },
    fetch: async (_url, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
    }),
  });
  await assert.rejects(env.load('servicos/http.ts').requisitarJson('https://api.test'), (error) => {
    assert.equal(error.tipo, 'timeout');
    return true;
  });
  assert.equal(cleared, true);
});

test('caller can cancel an in-flight HTTP request', async () => {
  const controller = new AbortController();
  const env = ambiente({ fetch: async (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
  }) });
  const pending = env.load('servicos/http.ts').requisitarJson('https://api.test', { signal: controller.signal });
  controller.abort();
  await assert.rejects(pending, (error) => error.tipo === 'cancelled');
});

test('invalid successful JSON is reported without leaking the response', async () => {
  const env = ambiente({ fetch: async () => new Response('internal debug text') });
  await assert.rejects(env.load('servicos/http.ts').requisitarJson('https://api.test'), (error) => {
    assert.equal(error.tipo, 'invalid-response');
    assert.ok(!error.message.includes('debug'));
    return true;
  });
});

test('session round trip and logout stay consistent', () => {
  const env = ambiente();
  const api = env.load('servicos/sessao.ts');
  const value = sessao();
  let events = 0;
  env.window.addEventListener(api.EVENTO_SESSAO, () => { events += 1; });
  api.gravarSessao(value);
  assert.equal(api.lerSessao().token, value.token);
  api.limparSessao();
  assert.equal(api.lerSessao(), null);
  assert.equal(env.storage.size, 0);
  assert.equal(events, 2);
});

test('failed session persistence rejects login instead of keeping an in-memory token', () => {
  const env = ambiente();
  const api = env.load('servicos/sessao.ts');
  env.globals.sessionStorage.setItem = () => { throw new Error('storage blocked'); };
  assert.throws(() => api.gravarSessao(sessao()), /Não foi possível salvar a sessão/);
  assert.equal(api.lerSessao(), null);
});

test('a silently discarded storage write is also rejected', () => {
  const env = ambiente();
  const api = env.load('servicos/sessao.ts');
  env.globals.sessionStorage.setItem = () => {};
  assert.throws(() => api.gravarSessao(sessao()), /Não foi possível salvar a sessão/);
  assert.equal(api.lerSessao(), null);
});

test('blocked session reads fail closed without exposing storage errors', () => {
  const env = ambiente();
  env.globals.sessionStorage.getItem = () => { throw new Error('private details'); };
  assert.equal(env.load('servicos/sessao.ts').lerSessao(), null);
  assert.ok(env.avisos.every((message) => !message.includes('private details')));
});

test('a previously valid session is cleared at expiry and notifies authentication', () => {
  let now = Date.now();
  const env = ambiente({ Date: { now: () => now, parse: Date.parse } });
  const api = env.load('servicos/sessao.ts');
  api.gravarSessao(sessao(new Date(now + 1_000).toISOString()));
  let events = 0;
  env.window.addEventListener(api.EVENTO_SESSAO, () => { events += 1; });
  now += 1_001;
  assert.equal(api.lerSessao(), null);
  assert.equal(events, 1);
});

test('upload uses the longer bounded timeout without changing the multipart contract', async () => {
  let timeout;
  const env = ambiente({
    setTimeout: (_callback, ms) => { timeout = ms; return 1; },
    clearTimeout: () => {},
    fetch: async (_url, init) => {
      assert.equal(init.method, 'POST');
      assert.ok(init.body.get('arquivo'));
      return new Response(JSON.stringify({ status: 'recebido' }));
    },
  });
  env.load('servicos/sessao.ts').gravarSessao(sessao());
  const api = env.load('servicos/fonteApi.ts').criarFonteApi('https://api.test');
  await api.enviarBaseClientes(new Blob(['canonical fixture']));
  assert.equal(timeout, 120_000);
});

for (const value of [
  sessao(new Date(Date.now() - 10_000).toISOString()),
  sessao('invalid-date'),
  { ...sessao(), token: '' },
  { ...sessao(), usuario: null },
  { ...sessao(), usuario: {} },
]) {
  test('invalid or expired stored sessions are cleared', () => {
    const env = ambiente();
    env.storage.set('crm-alto-valor:sessao', JSON.stringify(value));
    assert.equal(env.load('servicos/sessao.ts').lerSessao(), null);
    assert.equal(env.storage.size, 0);
  });
}

test('failed logout storage removal never resurrects the token in this page', () => {
  const env = ambiente();
  const api = env.load('servicos/sessao.ts');
  api.gravarSessao(sessao());
  env.globals.sessionStorage.removeItem = () => { throw new Error('storage blocked'); };
  api.limparSessao();
  assert.equal(api.lerSessao(), null);
  assert.equal(env.avisos.length, 1);
});

test('API source sends JWT, preserves 429 details, and clears session on 401', async () => {
  let status = 429;
  let redirects = 0;
  const env = ambiente({ fetch: async (_url, init) => {
    assert.equal(init.headers.Authorization, 'Bearer unit-test-token');
    return new Response('{}', { status, headers: { 'Retry-After': '20' } });
  } });
  env.window.location.assign = () => { redirects += 1; };
  const session = env.load('servicos/sessao.ts');
  session.gravarSessao(sessao());
  const api = env.load('servicos/fonteApi.ts').criarFonteApi('https://api.test');
  await assert.rejects(api.gerarRecomendacao('AZ-test'), (error) => error.retryAfterSeconds === 20);
  status = 401;
  await assert.rejects(api.listarClientes(), (error) => error.status === 401);
  assert.equal(session.lerSessao(), null);
  assert.equal(redirects, 1);
});

test('login uses the shared HTTP client and keeps invalid-credentials semantics', async () => {
  const env = ambiente({ fetch: async () => new Response('{}', { status: 401 }) });
  const api = env.load('servicos/servicoAutenticacao.ts');
  await assert.rejects(api.servicoAutenticacao.entrar('user@example.test', 'unit-test'), (error) => error instanceof api.ErroCredenciais);
});
