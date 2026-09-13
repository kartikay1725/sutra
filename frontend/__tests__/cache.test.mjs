import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import vm from 'node:vm';

function loadTsModule(relPath) {
  const fullPath = path.resolve(process.cwd(), relPath);
  const code = fs.readFileSync(fullPath, 'utf8');
  const transpiled = ts.transpileModule(code, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;

  const mod = { exports: {} };
  const fn = vm.runInThisContext(
    '(function(exports, require, module, __filename, __dirname) { ' + transpiled + '\n})',
    { filename: fullPath }
  );
  fn(mod.exports, (id) => {
    if (id === 'react') {
      return {
        useState: () => [null, () => {}],
        useEffect: () => {},
        useCallback: (fn) => fn,
        useRef: (val) => ({ current: val }),
      };
    }
    return {};
  }, mod, fullPath, path.dirname(fullPath));
  return mod.exports;
}

test('SUTRA Client Cache: in-memory hit and miss', async () => {
  const { clientCache } = loadTsModule('lib/cache.ts');
  clientCache.clear();

  let fetchCount = 0;
  const fetcher = async () => {
    fetchCount++;
    return { id: 1, name: 'repo-test' };
  };

  // 1. Initial fetch (miss)
  const result1 = await clientCache.fetch('test:key', fetcher, { staleMs: 1000, ttlMs: 5000 });
  assert.equal(fetchCount, 1);
  assert.deepEqual(result1, { id: 1, name: 'repo-test' });

  // 2. Immediate second fetch (fresh hit)
  const result2 = await clientCache.fetch('test:key', fetcher, { staleMs: 1000, ttlMs: 5000 });
  assert.equal(fetchCount, 1, 'Fetcher must not be called again on fresh cache hit');
  assert.deepEqual(result2, { id: 1, name: 'repo-test' });
});

test('SUTRA Client Cache: in-flight request deduplication', async () => {
  const { clientCache } = loadTsModule('lib/cache.ts');
  clientCache.clear();

  let fetchCount = 0;
  const slowFetcher = async () => {
    fetchCount++;
    await new Promise((r) => setTimeout(r, 50));
    return { timestamp: Date.now(), data: 'deduped' };
  };

  // Launch 3 simultaneous requests for the same key
  const [res1, res2, res3] = await Promise.all([
    clientCache.fetch('test:dedup', slowFetcher, { staleMs: 5000 }),
    clientCache.fetch('test:dedup', slowFetcher, { staleMs: 5000 }),
    clientCache.fetch('test:dedup', slowFetcher, { staleMs: 5000 }),
  ]);

  assert.equal(fetchCount, 1, 'In-flight deduplication must coalesce 3 concurrent calls into 1');
  assert.equal(res1.data, 'deduped');
  assert.equal(res2.data, 'deduped');
  assert.equal(res3.data, 'deduped');
});

test('SUTRA Client Cache: TTL expiration', async () => {
  const { clientCache } = loadTsModule('lib/cache.ts');
  clientCache.clear();

  let counter = 0;
  const fetcher = async () => ++counter;

  // Set with 20ms TTL
  await clientCache.fetch('test:expiring', fetcher, { staleMs: 10, ttlMs: 30 });
  assert.equal(counter, 1);

  // Wait 40ms to exceed TTL
  await new Promise((r) => setTimeout(r, 45));

  const afterExpire = await clientCache.fetch('test:expiring', fetcher, { staleMs: 10, ttlMs: 30 });
  assert.equal(counter, 2, 'Fetcher must be invoked again after TTL expiration');
  assert.equal(afterExpire, 2);
});

test('SUTRA Client Cache: forceRefresh bypass', async () => {
  const { clientCache } = loadTsModule('lib/cache.ts');
  clientCache.clear();

  let counter = 0;
  const fetcher = async () => ++counter;

  await clientCache.fetch('test:bypass', fetcher, { staleMs: 60000, ttlMs: 120000 });
  assert.equal(counter, 1);

  // Normal fetch returns cached value
  await clientCache.fetch('test:bypass', fetcher);
  assert.equal(counter, 1);

  // forceRefresh bypasses cache
  const refreshed = await clientCache.fetch('test:bypass', fetcher, { forceRefresh: true });
  assert.equal(counter, 2);
  assert.equal(refreshed, 2);
});

test('SUTRA Client Cache: prefix invalidation', async () => {
  const { clientCache } = loadTsModule('lib/cache.ts');
  clientCache.clear();

  clientCache.set('repo:user/alpha', { name: 'alpha' });
  clientCache.set('repo:user/alpha:branches', ['main', 'dev']);
  clientCache.set('repo:user/beta', { name: 'beta' });

  assert.ok(clientCache.get('repo:user/alpha'));
  assert.ok(clientCache.get('repo:user/alpha:branches'));
  assert.ok(clientCache.get('repo:user/beta'));

  // Invalidate all alpha keys
  clientCache.invalidatePrefix('repo:user/alpha');

  assert.equal(clientCache.get('repo:user/alpha'), null);
  assert.equal(clientCache.get('repo:user/alpha:branches'), null);
  assert.ok(clientCache.get('repo:user/beta'), 'Other prefixes must remain intact');
});

test('SUTRA Client Cache: sessionStorage cache hit', async () => {
  const mockStorage = {};
  global.window = {
    sessionStorage: {
      getItem: (k) => mockStorage[k] || null,
      setItem: (k, v) => { mockStorage[k] = String(v); },
      removeItem: (k) => { delete mockStorage[k]; },
      get length() { return Object.keys(mockStorage).length; },
      key: (i) => Object.keys(mockStorage)[i] || null,
    },
  };

  const { clientCache } = loadTsModule('lib/cache.ts');
  clientCache.clear();

  let fetchCount = 0;
  const fetcher = async () => {
    fetchCount++;
    return { repo: 'alpha', owner: 'org' };
  };

  // First fetch populates sessionStorage
  const res1 = await clientCache.fetch('session:hit:test', fetcher, { persistSession: true, ttlMs: 60000 });
  assert.equal(fetchCount, 1);
  assert.equal(res1.repo, 'alpha');

  // Verify it exists in sessionStorage
  assert.ok(mockStorage['sutra_cache:session:hit:test']);

  // Re-instantiate cache to simulate page refresh / new component loading from sessionStorage
  const { clientCache: freshCache } = loadTsModule('lib/cache.ts');
  const res2 = await freshCache.fetch('session:hit:test', fetcher, { persistSession: true, ttlMs: 60000 });
  assert.equal(fetchCount, 1, 'Fetcher must not be called when sessionStorage cache hits');
  assert.equal(res2.repo, 'alpha');

  delete global.window;
});

test('SUTRA Client Cache: repository navigation does not duplicate repository request', async () => {
  const { clientCache } = loadTsModule('lib/cache.ts');
  clientCache.clear();

  let repoNetworkCalls = 0;
  const getRepositoryNetwork = async (slug) => {
    repoNetworkCalls++;
    return { id: 'repo-1', name: slug, slug };
  };

  // User navigates to /repositories/sutra (Screen 1)
  const repoScreen1 = await clientCache.fetch('repo:sutra', () => getRepositoryNetwork('sutra'), {
    staleMs: 120000,
    ttlMs: 300000,
  });
  assert.equal(repoNetworkCalls, 1);
  assert.equal(repoScreen1.slug, 'sutra');

  // User navigates to /repositories/sutra/code (Screen 2)
  const repoScreen2 = await clientCache.fetch('repo:sutra', () => getRepositoryNetwork('sutra'), {
    staleMs: 120000,
    ttlMs: 300000,
  });
  assert.equal(repoNetworkCalls, 1, 'Screen 2 must reuse cached repository without new network request');
  assert.equal(repoScreen2.slug, 'sutra');

  // User navigates to /repositories/sutra/issues (Screen 3)
  const repoScreen3 = await clientCache.fetch('repo:sutra', () => getRepositoryNetwork('sutra'), {
    staleMs: 120000,
    ttlMs: 300000,
  });
  assert.equal(repoNetworkCalls, 1, 'Screen 3 must reuse cached repository without new network request');
  assert.equal(repoScreen3.slug, 'sutra');
});

test('SUTRA Client Cache: issues navigation does not repeat auth/repo fetch unnecessarily', async () => {
  const { clientCache } = loadTsModule('lib/cache.ts');
  clientCache.clear();

  let authCalls = 0;
  let repoCalls = 0;
  let issuesCalls = 0;

  const fetchAuth = async () => { authCalls++; return { id: 'user-1', username: 'dev' }; };
  const fetchRepo = async () => { repoCalls++; return { id: 'repo-1', name: 'sutra' }; };
  const fetchIssues = async () => { issuesCalls++; return [{ id: 'iss-1', title: 'Test issue' }]; };

  // Initial navigation to issues page
  const [auth1, repo1, issues1] = await Promise.all([
    clientCache.fetch('auth:me', fetchAuth, { staleMs: 300000, ttlMs: 900000 }),
    clientCache.fetch('repo:sutra', fetchRepo, { staleMs: 120000, ttlMs: 300000 }),
    clientCache.fetch('issues:sutra:all', fetchIssues, { staleMs: 60000, ttlMs: 180000 }),
  ]);
  assert.equal(authCalls, 1);
  assert.equal(repoCalls, 1);
  assert.equal(issuesCalls, 1);

  // Navigating back and forth between issues tabs or screens
  const [auth2, repo2, issues2] = await Promise.all([
    clientCache.fetch('auth:me', fetchAuth, { staleMs: 300000, ttlMs: 900000 }),
    clientCache.fetch('repo:sutra', fetchRepo, { staleMs: 120000, ttlMs: 300000 }),
    clientCache.fetch('issues:sutra:all', fetchIssues, { staleMs: 60000, ttlMs: 180000 }),
  ]);

  assert.equal(authCalls, 1, 'auth/me must not be re-requested');
  assert.equal(repoCalls, 1, 'repository metadata must not be re-requested');
  assert.equal(issuesCalls, 1, 'issues list within TTL must not be re-requested');
});

test('SUTRA Client Cache: sessionStorage persistence & recovery', async () => {
  const mockStorage = {};
  global.window = {
    sessionStorage: {
      getItem: (k) => mockStorage[k] || null,
      setItem: (k, v) => { mockStorage[k] = String(v); },
      removeItem: (k) => { delete mockStorage[k]; },
      get length() { return Object.keys(mockStorage).length; },
      key: (i) => Object.keys(mockStorage)[i] || null,
    },
  };

  const { clientCache } = loadTsModule('lib/cache.ts');
  clientCache.clear();

  clientCache.set('session:test', { value: 42 }, { persistSession: true, ttlMs: 60000 });

  assert.ok(mockStorage['sutra_cache:session:test'], 'Must serialize to sessionStorage with prefix');

  // Corrupt sessionStorage with malformed JSON
  mockStorage['sutra_cache:corrupted'] = '{not: valid: json}';

  // Re-instantiate cache to test hydration and recovery
  const { clientCache: freshCache } = loadTsModule('lib/cache.ts');
  assert.equal(freshCache.get('corrupted'), null, 'Corrupt sessionStorage entry must be cleanly recovered and dropped');

  delete global.window;
});
