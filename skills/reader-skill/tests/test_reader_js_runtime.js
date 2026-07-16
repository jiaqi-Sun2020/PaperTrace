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

function testSaveMarkClosesPanel() {
  const closePanel = extractFunction(html, "closePanel");
  const saveCurrent = extractFunction(html, "saveCurrent");
  const script = `
    const feedback = new Map();
    const dock = { hidden: false };
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
    function feedbackKey(concept, blockId, kind) { return [kind || "concept", concept || "", blockId || ""].join("::"); }
    function removeVisualFeedback() {}
    function showVisualFeedback() {}
    function refreshSummary() {}
    function getStatus() { return "learning"; }
    const bodyClasses = new Set(["feedback-open"]);
    const document = {
      body: { classList: { remove(name) { bodyClasses.delete(name); } } },
      querySelectorAll() { return []; },
    };
    ${closePanel}
    ${saveCurrent}
    saveCurrent();
    if (dock.hidden !== true) throw new Error("Save mark did not close panel");
    if (bodyClasses.has("feedback-open")) throw new Error("Save mark did not release docked feedback layout space");
    if (feedback.size !== 1) throw new Error("Save mark did not persist feedback item");
  `;
  vm.runInNewContext(script, {}, { timeout: 1000 });
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

testSaveMarkClosesPanel();
testThemePersists();
testReaderViewControlsPersist();
console.log("reader JS runtime passed: feedback docking, theme, collapsible panes, resize state, and source pages persist.");
