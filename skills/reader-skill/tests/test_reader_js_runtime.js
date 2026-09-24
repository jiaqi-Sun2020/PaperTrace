#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "..", "..", "..");
const readerDir = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(root, "2026", "7", "CTQWformer A CTQW-based Transformer_reader");
const htmlPath = path.join(readerDir, "reader_interactive.html");
const html = fs.readFileSync(htmlPath, "utf8");

function extractFunction(source, name) {
  const start = source.indexOf(`function ${name}`);
  if (start < 0) throw new Error(`missing function ${name}`);
  const open = source.indexOf("{", start);
  let depth = 0;
  for (let idx = open; idx < source.length; idx += 1) {
    const ch = source[idx];
    if (ch === "{") depth += 1;
    if (ch === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(start, idx + 1);
    }
  }
  throw new Error(`unterminated function ${name}`);
}

function testInlineScriptSyntax() {
  const scripts = Array.from(html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g));
  for (const [index, match] of scripts.entries()) {
    if (/type=["']application\/json["']/.test(match[1])) continue;
    if (!match[2].trim()) continue;
    try {
      new vm.Script(match[2]);
    } catch (error) {
      throw new Error(`inline script ${index + 1} has invalid JavaScript: ${error.message}`);
    }
  }
}

function testAutosavePersistsWithoutClosingReader() {
  const closePanel = extractFunction(html, "closePanel");
  const saveCurrent = extractFunction(html, "saveCurrent");
  const script = `
    const feedback = new Map();
    const dock = { hidden: false };
    const autosave = { flush() {} };
    const conceptInput = { value: "Hamiltonian" };
    const note = { value: "" };
    const question = { value: "" };
    const context = { value: "" };
    const confusionType = { value: "" };
    const explanationStyle = { value: "" };
    const needsExplanation = { checked: false };
    let currentConcept = "Hamiltonian";
    let currentBlock = "S001";
    let currentKind = "concept";
    let currentSourceExcerpt = "source excerpt";
    let currentSelectedText = "";
    let currentKey = null;
    let currentSelectionMeta = {};
    let currentConceptMeta = { source_anchor: "S001", concept_type: "math_object", alias_zh: "哈密顿量", concept_id: "hamiltonian" };
    let draftDirty = true;
    let persistedRecovery = false;
    function feedbackKey(concept, blockId, kind) { return [kind || "concept", concept || "", blockId || ""].join("::"); }
    function removeVisualFeedback() {}
    function showVisualFeedback() {}
    function refreshSummary() {}
    function getStatus() { return "learning"; }
    function currentReadingAnchor() { return null; }
    function restoreVerticalReadingPosition() {}
    function announceSaved(item) { saveStatus.textContent = item.concept; saveStatus.hidden = false; }
    function persistRecoveryNow() { persistedRecovery = true; return true; }
    const saveStatus = { hidden: true, textContent: "" };
    const bodyClasses = new Set(["feedback-open"]);
    const document = {
      body: { classList: { remove(name) { bodyClasses.delete(name); } } },
      querySelectorAll() { return []; },
    };
    ${closePanel}
    ${saveCurrent}
    saveCurrent();
    if (dock.hidden !== false) throw new Error("autosave unexpectedly closed the panel");
    if (!bodyClasses.has("feedback-open")) throw new Error("autosave unexpectedly changed docked reader layout");
    if (feedback.size !== 1) throw new Error("autosave did not persist feedback item");
    if (!persistedRecovery || draftDirty) throw new Error("autosave did not commit browser-local recovery");
    if (saveStatus.hidden || saveStatus.textContent !== "Hamiltonian") throw new Error("autosave did not announce an in-place save");
    closePanel();
    if (dock.hidden !== true || bodyClasses.has("feedback-open")) throw new Error("Close did not release the docked feedback layout");
  `;
  vm.runInNewContext(script, {}, { timeout: 1000 });
}

function testBlankPageClickDoesNotDismissFeedback() {
  if (/document\.addEventListener\(['"]pointerdown['"][\s\S]{0,800}?closePanel\(\)/.test(html)) {
    throw new Error("blank-page pointerdown still dismisses feedback");
  }
  if (!html.includes("--utility-pane-width: var(--feedback-dock-width)")) {
    throw new Error("wide reader does not reserve a stable utility lane");
  }
  if (/body\.feedback-open\s+\.layout(?:\.[^{\s]+)?\s*\{[^}]*(?:grid-template-columns|padding-right)/i.test(html)) {
    throw new Error("feedback-open still mutates the wide reader grid");
  }
}

function testAutosaveRestoresReadingPosition() {
  const restoreVerticalReadingPosition = extractFunction(html, "restoreVerticalReadingPosition");
  const script = `
    const scrollCalls = [];
    const window = { scrollBy(x, y) { scrollCalls.push([x, y]); } };
    const anchor = { getBoundingClientRect() { return { top: 134 }; } };
    ${restoreVerticalReadingPosition}
    restoreVerticalReadingPosition(anchor, 100);
    if (scrollCalls.length !== 1 || scrollCalls[0][0] !== 0 || scrollCalls[0][1] !== 34) {
      throw new Error("autosave did not restore the reading position after marker insertion");
    }
    restoreVerticalReadingPosition(anchor, 133.8);
    if (scrollCalls.length !== 1) throw new Error("sub-pixel marker movement should not scroll the reader");
  `;
  vm.runInNewContext(script, { Number, Math }, { timeout: 1000 });
}

function extractFeedbackUXScript(source) {
  const match = source.match(/<script data-papertrace-feedback-ux="v1">([\s\S]*?)<\/script>/);
  if (!match) throw new Error("missing shared feedback UX runtime");
  return match[1];
}

function testFeedbackUXAutosaveRuntime() {
  const script = extractFeedbackUXScript(html);
  const queue = [];
  const states = [];
  const window = {
    setTimeout(fn) { queue.push(fn); return queue.length; },
    clearTimeout() {},
  };
  vm.runInNewContext(script, { window, globalThis: window, Object, Date }, { timeout: 1000 });
  const api = window.PaperTraceFeedbackUX;
  if (!api || api.version !== 1) throw new Error("shared feedback UX API was not installed");
  let saves = 0;
  const autosave = api.createAutosave({ commit() { saves += 1; return { saves }; }, onState(event) { states.push(event.state); } });
  autosave.flush("empty");
  if (saves !== 0) throw new Error("empty autosave flush created a feedback record");
  autosave.schedule("input");
  autosave.schedule("input");
  autosave.flush("pagehide");
  if (saves !== 1) throw new Error("debounced autosave did not collapse rapid changes into one commit");
  if (!states.includes("saving") || !states.includes("saved")) throw new Error("autosave state was not announced");
  if (html.includes('id="saveFeedback"') || html.includes("Save mark")) throw new Error("legacy Save mark UI is still rendered");
  for (const token of ['id="readerSelectionToolbar"', "data-inline-status=\"mastered\"", "data-selection-details"]) {
    if (!html.includes(token)) throw new Error(`inline selection toolbar is missing: ${token}`);
  }
}

function testSelectionToolbarDismissesWhenSelectionClears() {
  const script = extractFeedbackUXScript(html);
  let timerId = 0;
  const timers = new Map();
  function setTimeoutFake(fn) { timerId += 1; timers.set(timerId, fn); return timerId; }
  function clearTimeoutFake(id) { timers.delete(id); }
  function drainTimers() {
    while (timers.size) {
      const [id, fn] = timers.entries().next().value;
      timers.delete(id);
      fn();
    }
  }
  function eventTarget(extra) {
    const listeners = new Map();
    return Object.assign({
      addEventListener(name, fn) {
        if (!listeners.has(name)) listeners.set(name, []);
        listeners.get(name).push(fn);
      },
      emit(name, event) {
        for (const fn of listeners.get(name) || []) fn(event || { target: this });
      },
    }, extra || {});
  }

  const selectedElement = { nodeType: 1, closest() { return null; } };
  let selectedText = "selected phrase";
  const selection = {
    rangeCount: 1,
    toString() { return selectedText; },
    getRangeAt() {
      return {
        commonAncestorContainer: selectedElement,
        getBoundingClientRect() { return { left: 100, top: 80, bottom: 100, width: 120 }; },
      };
    },
  };
  const statusButton = eventTarget({ dataset: { inlineStatus: "known" } });
  const toolbar = eventTarget({
    hidden: true,
    style: {},
    offsetWidth: 500,
    offsetHeight: 50,
    setAttribute() {},
    removeAttribute() {},
    contains(target) { return target === this || target === statusButton; },
    querySelectorAll() { return [statusButton]; },
    querySelector() { return null; },
  });
  const rootElement = eventTarget({
    contains(target) { return target === this || target === selectedElement; },
  });
  const document = eventTarget({ activeElement: null });
  const window = {
    document,
    innerWidth: 1200,
    innerHeight: 800,
    getSelection() { return selection; },
    setTimeout: setTimeoutFake,
    clearTimeout: clearTimeoutFake,
  };
  vm.runInNewContext(script, { window, globalThis: window, Object, Date }, { timeout: 1000 });
  let committed = null;
  const controller = window.PaperTraceFeedbackUX.createSelectionToolbar({
    toolbar,
    root: rootElement,
    onStatus(status, payload) { committed = { status, text: payload.text }; },
  });

  rootElement.emit("pointerdown", { target: selectedElement });
  rootElement.emit("pointerup", { target: selectedElement });
  drainTimers();
  if (toolbar.hidden || !controller.current() || controller.current().text !== "selected phrase") {
    throw new Error("valid selection did not open the contextual toolbar");
  }

  selectedText = "";
  rootElement.emit("pointerdown", { target: selectedElement });
  rootElement.emit("pointerup", { target: selectedElement });
  drainTimers();
  if (!toolbar.hidden || controller.current() !== null) {
    throw new Error("clearing the selection left a stale toolbar or payload");
  }

  selectedText = "drag outside";
  document.emit("selectionchange", { target: document });
  drainTimers();
  rootElement.emit("pointerdown", { target: selectedElement });
  selectedText = "";
  document.emit("pointercancel", { target: document });
  drainTimers();
  if (!toolbar.hidden || controller.current() !== null) {
    throw new Error("pointer cancellation outside the annotation root left stale contextual state");
  }

  selectedText = "keyboard selection";
  document.emit("selectionchange", { target: document });
  drainTimers();
  if (toolbar.hidden || controller.current().text !== "keyboard selection") {
    throw new Error("selectionchange did not reveal a keyboard-created selection");
  }
  selectedText = "";
  document.emit("selectionchange", { target: document });
  drainTimers();
  if (!toolbar.hidden || controller.current() !== null) {
    throw new Error("selectionchange did not dismiss a collapsed keyboard selection");
  }

  selectedText = "commit me";
  document.emit("selectionchange", { target: document });
  drainTimers();
  toolbar.emit("pointerdown", { target: statusButton });
  selectedText = "";
  document.emit("selectionchange", { target: document });
  toolbar.emit("pointerup", { target: statusButton });
  statusButton.emit("click", { target: statusButton });
  drainTimers();
  if (!committed || committed.status !== "known" || committed.text !== "commit me") {
    throw new Error("transient selection loss while clicking the toolbar discarded the intended payload");
  }
  if (!toolbar.hidden || controller.current() !== null) {
    throw new Error("committing a toolbar action did not clear the contextual state");
  }
}

function extractFeedbackRecoveryScript(source) {
  const match = source.match(/<script data-papertrace-feedback-recovery="v1">([\s\S]*?)<\/script>/);
  if (!match) throw new Error("missing shared feedback recovery runtime");
  return match[1];
}

function testFeedbackRecoveryRoundTripAndIsolation() {
  const script = extractFeedbackRecoveryScript(html);
  const store = new Map();
  const storage = {
    getItem(key) { return store.has(key) ? store.get(key) : null; },
    setItem(key, value) { store.set(key, value); },
    removeItem(key) { store.delete(key); },
  };
  const window = {
    localStorage: storage,
    setTimeout(fn) { fn(); return 1; },
    clearTimeout() {},
  };
  const context = { window, globalThis: window, Object, Array, JSON, Date, Number, String };
  vm.runInNewContext(script, context, { timeout: 1000 });
  const api = window.PaperTraceFeedbackRecovery;
  if (!api || api.version !== 1) throw new Error("shared feedback recovery API was not installed");
  const statuses = [];
  const recovery = api.create({ onStatus(event) { statuses.push(event); } });
  if (!/^paper\.reader\.feedback-draft\.v1:[0-9a-f]{64}$/.test(recovery.storageKey)) {
    throw new Error("feedback recovery key is not isolated by a paper SHA-256");
  }
  const saved = recovery.persist({
    exported_at: null,
    items: [{ feedback_id: "concept::Hamiltonian::S001", concept: "Hamiltonian", block_id: "S001" }],
    draft: { dirty: true, form: { concept: "open system", note: "unfinished" } },
  });
  if (!saved) throw new Error("feedback recovery did not persist a valid envelope");
  const restored = api.create().load();
  if (!restored || restored.items.length !== 1 || !restored.draft || restored.draft.form.note !== "unfinished") {
    throw new Error("saved mark and unfinished form draft did not survive a reload");
  }

  const otherFingerprint = "b".repeat(64);
  const otherKey = `paper.reader.feedback-draft.v1:${otherFingerprint}`;
  store.set(otherKey, JSON.stringify(Object.assign({}, restored, { paper_fingerprint: "a".repeat(64) })));
  if (api.create({ paper_fingerprint: otherFingerprint, storage_key: otherKey }).load() !== null) {
    throw new Error("feedback recovery accepted a draft from another paper");
  }

  store.set(recovery.storageKey, "{broken-json");
  if (api.create().load() !== null) throw new Error("corrupt feedback recovery data was not ignored");
  store.set(recovery.storageKey, "x".repeat(4 * 1024 * 1024 + 1));
  if (api.create().load() !== null) throw new Error("oversize feedback recovery data was not ignored");

  recovery.persist({ items: [], draft: null });
  recovery.clear();
  if (store.has(recovery.storageKey)) throw new Error("local feedback recovery clear did not remove the paper key");

  const failing = api.create({
    storage: { getItem() { return null; }, setItem() { throw new Error("quota"); }, removeItem() {} },
    storage_key: `paper.reader.feedback-draft.v1:${"c".repeat(64)}`,
    paper_fingerprint: "c".repeat(64),
  });
  if (failing.persist({ items: [], draft: null }) !== false || !failing.hasUnsafeChanges()) {
    throw new Error("storage failure did not leave an unsafe-change warning state");
  }
  if (!statuses.some((event) => event.kind === "saved")) throw new Error("local recovery save status was not announced");
}

function testFeedbackRecoveryIntegration() {
  const deleteFeedbackItem = extractFunction(html, "deleteFeedbackItem");
  if (!deleteFeedbackItem.includes("persistRecoveryNow();")) {
    throw new Error("deleting a saved annotation does not immediately persist recovery state");
  }
  for (const token of [
    "function draftSnapshot()",
    "function restoreLocalRecovery()",
    "recovery.schedule(recoveryEnvelope, 250)",
    "window.addEventListener('pagehide'",
    "window.addEventListener('beforeunload'",
    "field.addEventListener('input', markDraftDirty)",
    "field.addEventListener('change', markDraftDirty)",
  ]) {
    if (!html.includes(token)) throw new Error(`missing feedback recovery integration: ${token}`);
  }
  const restoreLocalRecovery = extractFunction(html, "restoreLocalRecovery");
  for (const token of ["feedback.set(key, item)", "showVisualFeedback(key, item)", "openPanel({", "draftDirty = true"]) {
    if (!restoreLocalRecovery.includes(token)) throw new Error(`reload does not restore reader state: ${token}`);
  }
  const downloadFeedback = extractFunction(html, "downloadFeedback");
  if (!downloadFeedback.includes("afterSuccessfulExport();")) {
    throw new Error("download export does not ask whether to clear local recovery");
  }
  const copyFeedback = extractFunction(html, "copyFeedback");
  const successIndex = copyFeedback.indexOf("afterSuccessfulExport();");
  const catchIndex = copyFeedback.indexOf("catch (err)");
  if (successIndex < 0 || catchIndex < 0 || successIndex > catchIndex) {
    throw new Error("copy export can clear local recovery after clipboard failure");
  }

  const confirmAndClear = extractFunction(html, "confirmAndClearLocalRecovery");
  const afterExport = extractFunction(html, "afterSuccessfulExport");
  const script = `
    let allowClear = false;
    let persisted = 0;
    let cleared = 0;
    let lastExportedAt = null;
    const window = { confirm() { return allowClear; } };
    function persistRecoveryNow() { persisted += 1; return true; }
    function clearLocalRecovery() { cleared += 1; }
    ${confirmAndClear}
    ${afterExport}
    afterSuccessfulExport();
    if (persisted !== 1 || cleared !== 0 || !lastExportedAt) throw new Error("Cancel did not keep the local recovery copy");
    allowClear = true;
    afterSuccessfulExport();
    if (persisted !== 2 || cleared !== 1) throw new Error("Confirm did not clear the local recovery copy after export");
  `;
  vm.runInNewContext(script, { Date }, { timeout: 1000 });
}

function extractThemeScript(source) {
  const scripts = Array.from(source.matchAll(/<script>([\s\S]*?)<\/script>/g))
    .map((match) => match[1])
    .filter((script) => script.includes("paper.reader.theme"));
  if (!scripts.length) throw new Error("missing theme script");
  return scripts[scripts.length - 1];
}

function testThemePersists() {
  const themeScript = extractThemeScript(html);
  const select = {
    value: "",
    listener: null,
    addEventListener(type, fn) {
      if (type === "change") this.listener = fn;
    },
  };
  const store = new Map([["paper.reader.theme", "dark"]]);
  const documentElement = {
    attrs: {},
    setAttribute(name, value) {
      this.attrs[name] = value;
    },
  };
  const context = {
    document: {
      documentElement,
      getElementById(id) {
        return id === "readerThemeSelect" ? select : null;
      },
    },
    localStorage: {
      getItem(key) {
        return store.get(key) || null;
      },
      setItem(key, value) {
        store.set(key, value);
      },
    },
  };
  vm.runInNewContext(themeScript, context, { timeout: 1000 });
  if (documentElement.attrs["data-theme"] !== "dark") throw new Error("saved dark theme was not restored");
  if (select.value !== "dark") throw new Error("theme select was not synchronized");
  select.value = "contrast";
  select.listener();
  if (documentElement.attrs["data-theme"] !== "contrast") throw new Error("theme change did not update data-theme");
  if (store.get("paper.reader.theme") !== "contrast") throw new Error("theme change was not persisted");
}

function extractReaderViewScript(source) {
  const scripts = Array.from(source.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))
    .map((match) => match[1])
    .filter((script) => script.includes("paper.reader.view."));
  if (!scripts.length) throw new Error("missing reader view-control script");
  return scripts[scripts.length - 1];
}

function testReaderViewControlsPersist() {
  const viewScript = extractReaderViewScript(html);
  const sourceJson = html.match(/<script id="readerSourcePages" type="application\/json">([\s\S]*?)<\/script>/);
  if (!sourceJson) throw new Error("missing source-page JSON");
  const pages = JSON.parse(sourceJson[1].replace(/<\\\//g, "</"));
  if (!pages.length) throw new Error("source-page JSON is empty");

  function button() {
    return {
      attrs: {}, textContent: "", disabled: false, listener: null,
      setAttribute(name, value) { this.attrs[name] = value; },
      addEventListener(type, fn) { if (type === "click") this.listener = fn; },
    };
  }
  const originalButton = button();
  const sourceButton = button();
  const contentsButton = button();
  const sourcePaneButton = button();
  const contentsPaneButton = button();
  const previousButton = button();
  const nextButton = button();
  const sourceViewer = { attrs: {}, setAttribute(name, value) { this.attrs[name] = value; } };
  const sourceImage = { src: "", alt: "" };
  const sourceOpen = { href: "" };
  const sourceCounter = { textContent: "" };
  const contentsPane = { attrs: {}, setAttribute(name, value) { this.attrs[name] = value; } };
  const contentsContent = { attrs: {}, setAttribute(name, value) { this.attrs[name] = value; } };
  const layoutStyles = new Map();
  const layout = {
    style: {
      setProperty(name, value) { layoutStyles.set(name, value); },
      removeProperty(name) { layoutStyles.delete(name); },
    },
  };
  const elements = {
    toggleOriginal: originalButton,
    toggleSourcePages: sourceButton,
    toggleContents: contentsButton,
    sourcePaneToggle: sourcePaneButton,
    contentsPaneToggle: contentsPaneButton,
    tableOfContents: contentsPane,
    tableOfContentsContent: contentsContent,
    sourcePageViewer: sourceViewer,
    sourcePageImage: sourceImage,
    sourcePageOpen: sourceOpen,
    sourcePageCounter: sourceCounter,
    sourcePagePrevious: previousButton,
    sourcePageNext: nextButton,
    readerSourcePages: { textContent: sourceJson[1] },
  };
  const bodyClasses = new Set();
  const store = new Map();
  const storageKeyMatch = viewScript.match(/const storageKey = '([^']+)'/);
  if (!storageKeyMatch) throw new Error("missing namespaced reader view storage key");
  store.set(storageKeyMatch[1], JSON.stringify({
    originalCollapsed: true,
    sourcePagesCollapsed: true,
    contentsCollapsed: true,
    currentPage: pages[0].page,
  }));
  const context = {
    document: {
      body: {
        classList: { toggle(name, enabled) { if (enabled) bodyClasses.add(name); else bodyClasses.delete(name); } },
        style: { setProperty() {} },
      },
      getElementById(id) { return elements[id] || null; },
      addEventListener() {},
      querySelector(selector) { return selector === ".layout" ? layout : null; },
      querySelectorAll() { return []; },
    },
    window: { innerWidth: 1920, matchMedia() { return { matches: false }; }, addEventListener() {} },
    localStorage: {
      getItem(key) { return store.get(key) || null; },
      setItem(key, value) { store.set(key, value); },
    },
    Element: function Element() {},
    Map,
    JSON,
  };
  vm.runInNewContext(viewScript, context, { timeout: 1000 });
  if (!bodyClasses.has("original-collapsed") || !bodyClasses.has("source-pages-collapsed") || !bodyClasses.has("toc-collapsed")) {
    throw new Error("saved reader view state was not restored");
  }
  if (originalButton.textContent !== "Show Original" || sourceButton.textContent !== "Show Source Pages") {
    throw new Error("reader view button text did not reflect collapsed state");
  }
  if (originalButton.attrs["aria-expanded"] !== "false" || sourceButton.attrs["aria-expanded"] !== "false") {
    throw new Error("reader view controls did not expose collapsed ARIA state");
  }
  if (contentsButton.textContent !== "Show Contents" || contentsButton.attrs["aria-expanded"] !== "false") {
    throw new Error("Contents collapse state was not restored accessibly");
  }
  originalButton.listener();
  sourceButton.listener();
  contentsButton.listener();
  if (bodyClasses.has("original-collapsed") || bodyClasses.has("source-pages-collapsed") || bodyClasses.has("toc-collapsed")) {
    throw new Error("reader view controls did not restore visible state");
  }
  if (originalButton.attrs["aria-expanded"] !== "true" || sourceButton.attrs["aria-expanded"] !== "true") {
    throw new Error("reader view controls did not expose expanded ARIA state");
  }
  if (sourceImage.src !== pages[0].src || !sourceCounter.textContent.includes("Page")) {
    throw new Error("source-page viewer did not render the selected page");
  }
  if (!layoutStyles.has("--toc-pane-width")) throw new Error("responsive pane width was not applied");
  if (pages.length > 1) {
    nextButton.listener();
    if (sourceImage.src !== pages[1].src) throw new Error("source-page Next control did not advance the image");
  }
}

testInlineScriptSyntax();
testAutosavePersistsWithoutClosingReader();
testBlankPageClickDoesNotDismissFeedback();
testAutosaveRestoresReadingPosition();
testFeedbackUXAutosaveRuntime();
testSelectionToolbarDismissesWhenSelectionClears();
testFeedbackRecoveryRoundTripAndIsolation();
testFeedbackRecoveryIntegration();
testThemePersists();
testReaderViewControlsPersist();
console.log("reader JS runtime passed: selection dismissal, inline selection, debounced autosave, recovery/isolation, export retention, explicit dismissal, stable layout, theme, view state, and source pages.");
