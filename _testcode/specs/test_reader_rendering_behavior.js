/*
 * Behavioral regression test for reader page swaps.
 * Run with: node _testcode/specs/test_reader_rendering_behavior.js
 */
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

class MockClassList {
    constructor() { this.values = new Set(); }
    add(...names) { names.forEach((name) => this.values.add(name)); }
    remove(...names) { names.forEach((name) => this.values.delete(name)); }
    contains(name) { return this.values.has(name); }
    toggle(name, force) {
        const enabled = force === undefined ? !this.values.has(name) : force;
        if (enabled) this.values.add(name); else this.values.delete(name);
        return enabled;
    }
}

class MockElement {
    constructor(tagName = 'div') {
        this.tagName = tagName.toUpperCase();
        this.children = [];
        this.dataset = {};
        this.style = {};
        this.classList = new MockClassList();
        this.clientWidth = 1000;
        this.clientHeight = 800;
        this.scrollTop = 0;
        this.scrollLeft = 0;
        this.value = '';
        this.checked = false;
        this.textContent = '';
        this.listeners = {};
    }
    addEventListener(type, handler) { this.listeners[type] = handler; }
    appendChild(child) { this.children.push(child); return child; }
    removeChild(child) { this.children = this.children.filter((item) => item !== child); }
    replaceChildren(...children) { this.children = children; }
    querySelectorAll(selector) {
        return selector === 'canvas' ? this.children.filter((item) => item.tagName === 'CANVAS') : [];
    }
    contains() { return false; }
    getBoundingClientRect() { return { left: 0, width: this.clientWidth }; }
    getContext() { return { drawImage() {} }; }
}

function deferred() {
    let resolve;
    const promise = new Promise((done) => { resolve = done; });
    return { promise, resolve };
}

function flush() {
    return new Promise((resolve) => setImmediate(resolve));
}

function createHarness() {
    const elements = new Map();
    const domListeners = {};
    const document = {
        body: { dataset: { fileId: '1', pdfUrl: '/pdfs/test.pdf', initialPage: '1' }, appendChild() {}, removeChild() {} },
        addEventListener(type, handler) { domListeners[type] = handler; },
        getElementById(id) {
            if (!elements.has(id)) elements.set(id, new MockElement());
            return elements.get(id);
        },
        createElement(tagName) { return new MockElement(tagName); },
        querySelector() { return new MockElement(); }
    };
    const localStorage = {
        values: new Map(),
        getItem(key) { return this.values.has(key) ? this.values.get(key) : null; },
        setItem(key, value) { this.values.set(key, String(value)); }
    };
    const window = {
        __READER_TEST_MODE__: true,
        devicePixelRatio: 3,
        innerWidth: 1000,
        innerHeight: 800,
        localStorage,
        addEventListener() {},
        open() {},
        // Keep navigation tests deterministic; the explicit preload test
        // below invokes preloadAdjacentPages() directly.
        requestIdleCallback() {}
    };
    const pendingRenders = new Map();
    let pageCalls = 0;
    const pdfDoc = {
        numPages: 20,
        getPage(pageNumber) {
            pageCalls += 1;
            return Promise.resolve({
                getViewport({ scale }) { return { width: 100 * scale, height: 200 * scale }; },
                render() {
                    const job = deferred();
                    pendingRenders.set(pageNumber, job);
                    return { promise: job.promise };
                }
            });
        }
    };
    const context = {
        window,
        document,
        localStorage,
        console,
        setTimeout,
        clearTimeout,
        setImmediate,
        fetch: async () => ({ ok: true, json: async () => ({ edits: [] }) }),
        pdfjsLib: { getDocument() { return { promise: new Promise(() => {}) }; } }
    };

    vm.runInNewContext(fs.readFileSync('static/js/reader.js', 'utf8'), context, { filename: 'reader.js' });
    domListeners.DOMContentLoaded();
    window.__readerTestHooks.setPdfDocument(pdfDoc);

    return {
        viewer: elements.get('pdf-viewer'),
        hooks: window.__readerTestHooks,
        pendingRenders,
        getPageCalls: () => pageCalls
    };
}

async function run() {
    {
        const { viewer, hooks, pendingRenders } = createHarness();
        const previous = new MockElement('canvas');
        previous.dataset.virtualPage = '1';
        viewer.replaceChildren(previous);

        hooks.renderOnePage(2);
        await flush();
        assert.deepStrictEqual(viewer.children, [previous], 'old page must remain while rendering');

        pendingRenders.get(2).resolve();
        await flush();
        assert.strictEqual(viewer.children.length, 1);
        assert.strictEqual(viewer.children[0].dataset.virtualPage, 2);
    }

    {
        const { viewer, hooks, pendingRenders } = createHarness();
        const previous = new MockElement('canvas');
        previous.dataset.virtualPage = '1';
        viewer.replaceChildren(previous);

        hooks.renderOnePage(2);
        await flush();
        hooks.renderOnePage(3);
        await flush();

        pendingRenders.get(2).resolve();
        await flush();
        assert.deepStrictEqual(viewer.children, [previous], 'stale page must not swap in');

        pendingRenders.get(3).resolve();
        await flush();
        assert.strictEqual(viewer.children[0].dataset.virtualPage, 3);
    }

    {
        const { viewer, hooks, pendingRenders } = createHarness();
        const previous = new MockElement('canvas');
        viewer.replaceChildren(previous);

        hooks.renderTwoPages(4, 'ltr');
        await flush();
        assert.deepStrictEqual(viewer.children, [previous]);
        pendingRenders.get(4).resolve();
        pendingRenders.get(5).resolve();
        await flush();
        assert.deepStrictEqual(viewer.children.map((canvas) => canvas.dataset.virtualPage), [4, 5]);

        hooks.renderTwoPages(6, 'rtl');
        await flush();
        pendingRenders.get(6).resolve();
        pendingRenders.get(7).resolve();
        await flush();
        assert.deepStrictEqual(viewer.children.map((canvas) => canvas.dataset.virtualPage), [7, 6]);
    }

    {
        const { viewer, hooks, pendingRenders, getPageCalls } = createHarness();
        hooks.setPageNum(1);

        const preloadPromise = hooks.preloadAdjacentPages();
        await flush();
        assert.strictEqual(getPageCalls(), 1, 'preload should start with the next page');
        assert.ok(pendingRenders.has(2), 'the next page should render off-screen');

        pendingRenders.get(2).resolve();
        await preloadPromise;
        assert.deepStrictEqual(Array.from(hooks.getCachedPageNumbers()), [2]);

        const callsBeforeCacheHit = getPageCalls();
        hooks.renderOnePage(2);
        await flush();
        assert.strictEqual(getPageCalls(), callsBeforeCacheHit, 'cached page should not render again');
        assert.strictEqual(viewer.children[0].dataset.virtualPage, 2);
    }

    {
        const { hooks, pendingRenders } = createHarness();
        hooks.setPageNum(1);

        const preloadPromise = hooks.preloadAdjacentPages();
        await flush();
        assert.ok(pendingRenders.has(2));

        hooks.clearPageRenderCache();
        pendingRenders.get(2).resolve();
        await preloadPromise;
        assert.deepStrictEqual(
            Array.from(hooks.getCachedPageNumbers()),
            [],
            'cancelled cache generation must not be repopulated by an old preload'
        );
    }

    console.log('reader rendering behavior: PASS');
}

run().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
