/* Tests isolés des transitions de présentation, sans DOM/React ni vrai WebSocket.
 * Exécuter : node tests/test_presentation.cjs depuis frontend (TypeScript installé).
 */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { test } = require('node:test');
const ts = require('typescript');
const root = path.resolve(__dirname, '../src');

function setup() {
  let activities = [];
  let selected = null;
  let time = 0;
  const timers = new Map();
  const cache = new Map();
  const create = (initializer) => {
    let state;
    const set = (updater) => {
      const patch = typeof updater === 'function' ? updater(state) : updater;
      state = { ...state, ...patch };
    };
    state = initializer(set, () => state);
    const hook = (selector) => selector(state);
    hook.getState = () => state;
    return hook;
  };
  function load(relative) {
    const filename = path.resolve(root, relative);
    if (cache.has(filename)) return cache.get(filename);
    // import.meta représente la config Vite, pas le comportement testé.
    const source = fs.readFileSync(filename, 'utf8')
      .replaceAll('import.meta.env.VITE_ACTIVITY_FEED_DELAY_MS', '450')
      .replaceAll('import.meta.hot', 'undefined');
    const output = ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText;
    const module = { exports: {} };
    cache.set(filename, module.exports);
    const requireLocal = (name) => {
      if (name === 'zustand') return { create };
      if (name.endsWith('/activity.store')) return { useActivityStore: {
        getState: () => ({ addFromWebSocketEvent: (event) => activities.push(event) }),
      } };
      if (name.endsWith('/ui.store')) return { useUIStore: {
        getState: () => ({ selectedUserId: 'owner', selectedNegotiationId: selected,
          selectNegotiation: (id) => { selected = id; } }),
      } };
      if (name.startsWith('.')) return load(path.relative(root, path.resolve(path.dirname(filename), name + '.ts')));
      throw new Error('Unmocked dependency: ' + name);
    };
    vm.runInNewContext(output, { module, exports: module.exports, require: requireLocal,
      console, setTimeout: (callback) => { timers.set(++time, callback); return time; },
      clearTimeout: (id) => timers.delete(id) }, { filename });
    return module.exports;
  }
  const api = load('store/presentation.store.ts');
  const queueModule = load('websocket/activityQueue.ts');
  const queue = new queueModule.ActivityPresentationQueue(450);
  return { ...api, queue, activities, selected: () => selected,
    tick: () => {
      const entry = timers.entries().next().value;
      if (entry) { timers.delete(entry[0]); entry[1](); }
    },
  };
}

let sequence = 0;
const offer = { id: 'offer-a', sender_id: 'owner', receiver_id: 'partner',
  offered_resources: [], requested_resources: [], status: 'accepted', parent_offer_id: null };
const deal = (status = 'waiting_human') => ({ id: 'deal-a', participant_ids: ['owner','partner'],
  offers: [offer], current_round: 1, max_rounds: 10, status, accepted_offer_id: 'offer-a' });
const event = (type, negotiation = null) => ({ event_id: `event-${++sequence}`, type,
  timestamp: new Date().toISOString(), user_id: 'owner', entity_id: 'deal-a',
  payload: negotiation ? { negotiation } : {} });

test('le deal et son point de validation attendent la même horloge que le journal', () => {
  const x = setup();
  const start = event('negotiation_started', deal('negotiating'));
  const approval = event('human_approval_required', deal());
  x.usePresentationStore.getState().observe(start);
  assert.equal(x.displayedNegotiation(deal(), x.usePresentationStore.getState().tracked), null);
  x.queue.enqueue(start);
  x.usePresentationStore.getState().observe(approval);
  x.queue.enqueue(approval);
  assert.equal(x.approvalIsReady(deal(), x.usePresentationStore.getState().tracked), false);
  assert.equal(x.activities.length, 1);
  x.tick();
  assert.equal(x.activities[1].type, 'human_approval_required');
  assert.equal(x.approvalIsReady(deal(), x.usePresentationStore.getState().tracked), true);
});

test('un refus reçu bloque une ancienne validation encore dans la file', () => {
  const x = setup();
  const required = event('human_approval_required', deal());
  const rejected = event('human_rejected', deal('rejected'));
  x.usePresentationStore.getState().observe(rejected);
  x.usePresentationStore.getState().present(required);
  assert.equal(x.approvalIsReady(deal(), x.usePresentationStore.getState().tracked), false);
  assert.equal(x.displayedNegotiation(deal(), x.usePresentationStore.getState().tracked).status, 'rejected');
});

test('un deal réel rejeté prime même sur une projection WAIT_HUMAN', () => {
  const x = setup();
  x.usePresentationStore.getState().present(event('human_approval_required', deal()));
  assert.equal(x.approvalIsReady(deal('rejected'), x.usePresentationStore.getState().tracked), false);
  assert.equal(x.displayedNegotiation(deal('rejected'), x.usePresentationStore.getState().tracked).status, 'rejected');
});

test('le refus urgent rattrape le journal sans rouvrir la modal', () => {
  const x = setup();
  x.queue.enqueue(event('negotiation_started', deal('negotiating')));
  x.queue.enqueue(event('human_approval_required', deal()));
  const rejected = event('human_rejected', deal('rejected'));
  x.usePresentationStore.getState().observe(rejected);
  x.queue.enqueue(rejected, true);
  assert.equal(x.activities.length, 3);
  assert.equal(x.usePresentationStore.getState().pendingCount, 0);
  assert.equal(x.approvalIsReady(deal(), x.usePresentationStore.getState().tracked), false);
});

test('reset annule les temporisateurs et les anciens checkpoints', () => {
  const x = setup();
  x.queue.enqueue(event('negotiation_started', deal('negotiating')));
  x.queue.enqueue(event('human_approval_required', deal()));
  x.queue.clear();
  x.usePresentationStore.getState().reset();
  x.tick();
  assert.equal(x.activities.length, 1);
  assert.equal(Object.keys(x.usePresentationStore.getState().tracked).length, 0);
});

test('une nouvelle négociation du même initiateur remplace la sélection du deal refusé', () => {
  const x = setup();
  x.queue.enqueue(event('negotiation_started', deal('negotiating')));
  assert.equal(x.selected(), 'deal-a');
  const next = event('negotiation_started', { ...deal('negotiating'), id: 'deal-b' });
  x.queue.enqueue(next);
  assert.equal(x.selected(), 'deal-a');
  x.tick();
  assert.equal(x.selected(), 'deal-b');
});

test('syntaxe de tous les TS/TSX de cette mise à jour', () => {
  function walk(folder) {
    for (const item of fs.readdirSync(folder, { withFileTypes: true })) {
      const filename = path.join(folder, item.name);
      if (item.isDirectory()) walk(filename);
      else if (/\.tsx?$/.test(filename)) {
        const result = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
          compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022,
            jsx: ts.JsxEmit.ReactJSX }, reportDiagnostics: true, fileName: filename,
        });
        assert.equal((result.diagnostics ?? []).filter((d) => d.category === ts.DiagnosticCategory.Error).length,
          0, 'Syntax error: ' + filename);
      }
    }
  }
  walk(root);
});
