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
    const document = { querySelectorAll() { return []; } };
    ${closePanel}
    ${saveCurrent}
    saveCurrent();
    if (dock.hidden !== true) throw new Error("Save mark did not close panel");
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

testSaveMarkClosesPanel();
testThemePersists();
console.log("reader JS runtime passed: save mark closes panel and theme persists.");
