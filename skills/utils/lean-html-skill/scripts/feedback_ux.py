#!/usr/bin/env python3
"""Shared browser interaction assets for PaperTrace feedback surfaces.

The generated HTML stays standalone: reader and briefing renderers embed these
assets instead of loading a runtime from disk.
"""

from __future__ import annotations


def feedback_ux_styles() -> str:
    return r'''<style data-papertrace-feedback-ux="v1">
.papertrace-selection-toolbar {
  position: fixed;
  z-index: 1000;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  max-width: min(620px, calc(100vw - 24px));
  padding: 8px;
  border: 1px solid var(--line, #cbd5e1);
  border-radius: 10px;
  background: var(--paper, var(--panel, #fff));
  color: var(--ink, #172033);
  box-shadow: 0 14px 38px rgba(15, 23, 42, .24);
}
.papertrace-selection-toolbar[hidden] { display: none !important; }
.papertrace-selection-toolbar button {
  min-height: 38px;
  border: 1px solid var(--line, #cbd5e1);
  border-radius: 8px;
  background: var(--reader-panel-bg, #f8fafc);
  color: inherit;
  padding: 6px 10px;
  font: inherit;
  cursor: pointer;
}
.papertrace-selection-toolbar button:hover,
.papertrace-selection-toolbar button:focus-visible {
  border-color: var(--accent, #0f766e);
  outline: 2px solid var(--accent-soft, rgba(15, 118, 110, .18));
  outline-offset: 1px;
}
.papertrace-selection-toolbar button[data-inline-status="mastered"] {
  border-color: var(--reader-status-saved-border, #15803d);
  background: var(--reader-status-saved-bg, color-mix(in srgb, var(--paper, var(--panel, #fff)) 88%, #16a34a));
  color: var(--reader-status-saved-text, var(--ink, #172033));
}
.papertrace-selection-toolbar button[data-inline-status="known"] {
  border-color: var(--reader-accent, var(--accent, #0f766e));
  background: var(--reader-accent-soft, var(--accent-soft, color-mix(in srgb, var(--paper, var(--panel, #fff)) 88%, #0f766e)));
  color: var(--ink, #172033);
}
.papertrace-selection-toolbar button[data-inline-status="learning"] {
  border-color: var(--reader-status-learning-border, #d97706);
  background: var(--reader-status-learning-bg, color-mix(in srgb, var(--paper, var(--panel, #fff)) 88%, #d97706));
  color: var(--ink, #172033);
}
.papertrace-selection-toolbar button[data-inline-status="unknown"] {
  border-color: var(--reader-status-unknown-border, #dc2626);
  background: var(--reader-status-unknown-bg, color-mix(in srgb, var(--paper, var(--panel, #fff)) 88%, #dc2626));
  color: var(--ink, #172033);
}
.papertrace-selection-toolbar button.papertrace-selection-details {
  background: color-mix(in srgb, var(--paper, var(--panel, #fff)) 72%, var(--accent, #0f766e));
  color: var(--ink, #172033);
  border-color: var(--accent, #0f766e);
}
.papertrace-save-indicator {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 1002;
  max-width: min(420px, calc(100vw - 36px));
  margin: 0;
  padding: 9px 12px;
  border: 1px solid var(--line, #cbd5e1);
  border-radius: 9px;
  background: var(--paper, var(--panel, #fff));
  color: var(--ink, #172033);
  box-shadow: 0 10px 28px rgba(15, 23, 42, .18);
  font-size: .88rem;
}
.papertrace-save-indicator[hidden] { display: none !important; }
.papertrace-save-indicator[data-state="saving"] { color: var(--muted, #64748b); }
.papertrace-save-indicator[data-state="failed"] {
  color: var(--reader-danger-text, var(--ink, #b91c1c));
  border-color: var(--reader-danger-border, #dc2626);
  background: var(--reader-danger-bg, color-mix(in srgb, var(--paper, var(--panel, #fff)) 90%, #dc2626));
}
.papertrace-save-indicator[data-state="saved"] {
  color: var(--reader-status-saved-text, var(--ink, #047857));
  border-color: var(--reader-status-saved-border, #16a34a);
  background: var(--reader-status-saved-bg, color-mix(in srgb, var(--paper, var(--panel, #fff)) 90%, #16a34a));
}
.papertrace-undo-indicator { bottom: 64px; }
.papertrace-undo {
  margin-left: 10px;
  border: 0;
  border-bottom: 1px solid currentColor;
  background: transparent;
  color: inherit;
  padding: 0;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}
@media (max-width: 720px) {
  .papertrace-selection-toolbar {
    left: 12px !important;
    right: 12px !important;
    bottom: 12px !important;
    top: auto !important;
    max-width: none;
  }
  .papertrace-selection-toolbar button { flex: 1 1 auto; min-height: 44px; }
  .papertrace-save-indicator { left: 12px; right: 12px; bottom: 72px; max-width: none; }
  .papertrace-undo-indicator { bottom: 122px; }
}
</style>'''


def feedback_ux_runtime_script() -> str:
    return r'''<script data-papertrace-feedback-ux="v1">
(function (root) {
  "use strict";

  function createAutosave(options) {
    const settings = Object.assign({ delay: 250 }, options || {});
    let timer = null;
    let pending = false;
    let pendingReason = "change";

    function announce(state, message, extra) {
      if (typeof settings.onState === "function") {
        settings.onState(Object.assign({ state, message: message || "" }, extra || {}));
      }
    }

    function flush(reason) {
      if (timer !== null && typeof root.clearTimeout === "function") root.clearTimeout(timer);
      timer = null;
      if (!pending) return null;
      pending = false;
      const activeReason = reason || pendingReason || "change";
      try {
        const result = typeof settings.commit === "function" ? settings.commit(activeReason) : null;
        const savedAt = new Date().toISOString();
        announce("saved", "已自动保存", { reason: activeReason, saved_at: savedAt, result });
        return result;
      } catch (error) {
        announce("failed", "自动保存失败，请先导出 JSON", { reason: activeReason, error });
        return null;
      }
    }

    function schedule(reason) {
      pendingReason = reason || "change";
      pending = true;
      announce("saving", "正在保存…", { reason: pendingReason });
      if (timer !== null && typeof root.clearTimeout === "function") root.clearTimeout(timer);
      if (typeof root.setTimeout !== "function") return flush(pendingReason);
      timer = root.setTimeout(function () { flush(pendingReason); }, settings.delay);
      return null;
    }

    function cancel() {
      if (timer !== null && typeof root.clearTimeout === "function") root.clearTimeout(timer);
      timer = null;
      pending = false;
    }

    return Object.freeze({ schedule, flush, cancel, hasPending: function () { return pending; } });
  }

  function createUndo(options) {
    const settings = Object.assign({ duration: 5000 }, options || {});
    const host = settings.host || null;
    let timer = null;
    let action = null;

    function clear() {
      if (timer !== null && typeof root.clearTimeout === "function") root.clearTimeout(timer);
      timer = null;
      action = null;
      if (host) {
        host.hidden = true;
        host.replaceChildren();
      }
    }

    function offer(label, callback) {
      clear();
      action = typeof callback === "function" ? callback : null;
      if (!host || !action) return;
      const text = host.ownerDocument.createElement("span");
      text.textContent = label || "已更新";
      const button = host.ownerDocument.createElement("button");
      button.type = "button";
      button.className = "papertrace-undo";
      button.textContent = "撤销";
      button.addEventListener("click", function () {
        const undo = action;
        clear();
        if (undo) undo();
      });
      host.append(text, button);
      host.hidden = false;
      if (typeof root.setTimeout === "function") timer = root.setTimeout(clear, settings.duration);
    }

    return Object.freeze({ offer, clear });
  }

  function createSelectionToolbar(options) {
    const settings = options || {};
    const toolbar = settings.toolbar;
    const rootElement = settings.root || (root.document && root.document.body);
    if (!toolbar || !rootElement) return Object.freeze({ hide: function () {}, show: function () {} });
    let current = null;
    let reconcileTimer = null;
    let selectingInRoot = false;
    let interactingWithToolbar = false;

    function hide() {
      if (reconcileTimer !== null && typeof root.clearTimeout === "function") root.clearTimeout(reconcileTimer);
      reconcileTimer = null;
      toolbar.hidden = true;
      toolbar.removeAttribute("data-open");
      current = null;
    }

    function place(rect) {
      const viewportWidth = root.innerWidth || 1024;
      const viewportHeight = root.innerHeight || 768;
      const width = Math.min(toolbar.offsetWidth || 520, viewportWidth - 24);
      const left = Math.max(12, Math.min(rect.left + (rect.width - width) / 2, viewportWidth - width - 12));
      const desiredTop = rect.bottom + 10;
      const height = toolbar.offsetHeight || 54;
      const top = desiredTop + height <= viewportHeight - 12 ? desiredTop : Math.max(12, rect.top - height - 10);
      toolbar.style.left = left + "px";
      toolbar.style.top = top + "px";
      toolbar.style.right = "auto";
      toolbar.style.bottom = "auto";
    }

    function show(payload) {
      if (!payload || !payload.text) return hide();
      current = payload;
      toolbar.hidden = false;
      toolbar.setAttribute("data-open", "true");
      place(payload.rect || { left: 12, top: 12, bottom: 12, width: 0 });
    }

    function capture() {
      const selection = root.getSelection ? root.getSelection() : null;
      if (!selection || selection.rangeCount === 0 || !selection.toString().trim()) return null;
      const range = selection.getRangeAt(0);
      const node = range.commonAncestorContainer;
      const element = node.nodeType === 1 ? node : node.parentElement;
      if (!element || !rootElement.contains(element)) return null;
      if (settings.ignoreSelector && element.closest && element.closest(settings.ignoreSelector)) return null;
      const base = typeof settings.capture === "function" ? settings.capture(selection, element) : {};
      const rect = range.getBoundingClientRect();
      return Object.assign({}, base || {}, { text: selection.toString().trim(), rect });
    }

    function reconcileFromSelection() {
      reconcileTimer = null;
      if (selectingInRoot || interactingWithToolbar) return;
      const payload = capture();
      if (payload) show(payload);
      else hide();
    }

    function scheduleReconcile() {
      if (selectingInRoot || interactingWithToolbar) return;
      if (reconcileTimer !== null && typeof root.clearTimeout === "function") root.clearTimeout(reconcileTimer);
      if (typeof root.setTimeout === "function") {
        reconcileTimer = root.setTimeout(reconcileFromSelection, 0);
      } else {
        reconcileFromSelection();
      }
    }

    function finishRootSelection() {
      if (!selectingInRoot) return;
      selectingInRoot = false;
      scheduleReconcile();
    }

    rootElement.addEventListener("pointerdown", function (event) {
      if (toolbar.contains(event.target)) return;
      selectingInRoot = true;
    });
    rootElement.addEventListener("pointerup", function (event) {
      if (toolbar.contains(event.target)) return;
      finishRootSelection();
    });
    rootElement.addEventListener("pointercancel", finishRootSelection);
    rootElement.addEventListener("keyup", function (event) {
      if (event.key === "Shift" || event.key.startsWith("Arrow")) scheduleReconcile();
    });
    toolbar.addEventListener("pointerdown", function () { interactingWithToolbar = true; });
    toolbar.addEventListener("pointerup", function () {
      if (typeof root.setTimeout === "function") root.setTimeout(function () { interactingWithToolbar = false; }, 0);
      else interactingWithToolbar = false;
    });
    toolbar.addEventListener("pointercancel", function () { interactingWithToolbar = false; });
    toolbar.addEventListener("focusout", function () {
      if (!toolbar.hidden) scheduleReconcile();
    });
    toolbar.querySelectorAll("[data-inline-status]").forEach(function (button) {
      button.addEventListener("click", function () {
        const payload = current;
        hide();
        if (payload && typeof settings.onStatus === "function") settings.onStatus(button.dataset.inlineStatus, payload);
      });
    });
    const details = toolbar.querySelector("[data-selection-details]");
    if (details) details.addEventListener("click", function () {
      const payload = current;
      hide();
      if (payload && typeof settings.onDetails === "function") settings.onDetails(payload);
    });
    if (root.document) root.document.addEventListener("pointerdown", function (event) {
      if (!toolbar.hidden && !toolbar.contains(event.target) && !rootElement.contains(event.target)) hide();
    });
    if (root.document) root.document.addEventListener("pointerup", finishRootSelection);
    if (root.document) root.document.addEventListener("pointercancel", finishRootSelection);
    if (root.document) root.document.addEventListener("selectionchange", scheduleReconcile);

    return Object.freeze({ hide, show, capture: reconcileFromSelection, current: function () { return current; } });
  }

  // Plain-text anchors live only in browser recovery, never feedback exports.
  function createAnnotationRenderer(options) {
    const settings = options || {};
    const article = settings.root;
    const excluded = 'script,style,textarea,pre,code,button,input,select,.math-inline,.math-display,mjx-container,.saved-feedback-tray';

    function index(scope) {
      const entries = [];
      let text = '';
      const walker = scope.ownerDocument.createTreeWalker(scope, 4);
      let node;
      while ((node = walker.nextNode())) {
        if (!node.parentElement || node.parentElement.closest(excluded)) {
          text += '\uFFFC';
          continue;
        }
        entries.push({ node, start: text.length, end: text.length + node.nodeValue.length });
        text += node.nodeValue;
      }
      return { text, entries };
    }

    function capture(range, scope) {
      if (!range || !scope || !scope.contains(range.commonAncestorContainer)) return null;
      const data = index(scope);
      const first = data.entries.find(e => e.node === range.startContainer);
      const last = data.entries.find(e => e.node === range.endContainer);
      if (!first || !last) return null;
      const start = first.start + range.startOffset;
      const end = last.start + range.endOffset;
      const exact = data.text.slice(start, end);
      if (!exact.trim() || exact.includes('\uFFFC')) return null;
      return { start, end, exact, prefix: data.text.slice(Math.max(0, start - 48), start),
        suffix: data.text.slice(end, end + 48) };
    }

    function locate(data, item, locator) {
      if (locator && Number.isInteger(locator.start) && Number.isInteger(locator.end)
          && locator.start >= 0 && locator.end > locator.start && locator.end <= data.text.length
          && data.text.slice(locator.start, locator.end) === locator.exact
          && (!locator.prefix || data.text.slice(Math.max(0, locator.start - locator.prefix.length), locator.start) === locator.prefix)
          && (!locator.suffix || data.text.slice(locator.end, locator.end + locator.suffix.length) === locator.suffix)) {
        return { start: locator.start, end: locator.end };
      }
      // Normalize whitespace with a map back to the original DOM offsets.
      const chars = [], offsets = [];
      for (let i = 0; i < data.text.length; i++) {
        const ch = /\s/.test(data.text[i]) ? ' ' : data.text[i];
        if (ch === ' ' && chars[chars.length - 1] === ' ') continue;
        chars.push(ch); offsets.push(i);
      }
      const needle = String((locator && locator.exact) || item.selected_text || '').replace(/\s+/g, ' ').trim();
      if (!needle || needle.includes('\uFFFC')) return null;
      const haystack = chars.join('');
      const matches = [];
      let from = 0, position;
      while ((position = haystack.indexOf(needle, from)) >= 0) {
        const start = offsets[position], end = offsets[position + needle.length - 1] + 1;
        const prefix = locator && locator.prefix, suffix = locator && locator.suffix;
        if ((!prefix || data.text.slice(Math.max(0, start - prefix.length), start) === prefix)
            && (!suffix || data.text.slice(end, end + suffix.length) === suffix)) matches.push({ start, end });
        from = position + 1;
      }
      return matches.length === 1 ? matches[0] : null;
    }

    function clear() {
      article.querySelectorAll('.saved-free-annotation').forEach(mark => {
        mark.replaceWith(mark.ownerDocument.createTextNode(mark.textContent || ''));
      });
      article.normalize();
    }

    function render(records) {
      clear();
      const groups = new Map(), unresolved = [];
      records.forEach(record => {
        const scope = settings.scopeForItem(record.item);
        if (!scope) { unresolved.push(record.key); return; }
        if (!groups.has(scope)) groups.set(scope, { data: index(scope), ranges: [] });
        const group = groups.get(scope);
        const found = locate(group.data, record.item, record.locator);
        if (!found) { unresolved.push(record.key); return; }
        group.ranges.push({ ...found, key: record.key, status: record.item.status || 'unrated' });
      });
      groups.forEach(group => group.data.entries.forEach(entry => {
        const ranges = group.ranges.filter(r => r.start < entry.end && r.end > entry.start);
        if (!ranges.length) return;
        const cuts = [...new Set([entry.start, entry.end, ...ranges.flatMap(r => [
          Math.max(entry.start, r.start), Math.min(entry.end, r.end)])])].sort((a, b) => a - b);
        const fragment = entry.node.ownerDocument.createDocumentFragment();
        for (let i = 0; i < cuts.length - 1; i++) {
          const start = cuts[i], end = cuts[i + 1];
          const active = ranges.filter(r => r.start < end && r.end > start);
          const text = entry.node.nodeValue.slice(start - entry.start, end - entry.start);
          if (!active.length) { fragment.appendChild(entry.node.ownerDocument.createTextNode(text)); continue; }
          const latest = active[active.length - 1];
          const mark = entry.node.ownerDocument.createElement('mark');
          mark.className = 'saved-free-annotation';
          mark.dataset.feedbackKey = latest.key;
          mark.dataset.feedbackKeys = JSON.stringify(active.map(r => r.key));
          mark.dataset.status = latest.status;
          mark.title = 'Saved annotation · ' + latest.status;
          mark.textContent = text;
          mark.tabIndex = 0;
          mark.addEventListener('click', event => {
            event.stopPropagation();
            if (settings.onOpen) settings.onOpen(latest.key);
          });
          mark.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              event.stopPropagation();
              if (settings.onOpen) settings.onOpen(latest.key);
            }
          });
          fragment.appendChild(mark);
        }
        entry.node.replaceWith(fragment);
      }));
      return unresolved;
    }
    return Object.freeze({ capture, render, clear });
  }

  root.PaperTraceFeedbackUX = Object.freeze({
    version: 1,
    createAutosave,
    createSelectionToolbar,
    createUndo,
    createAnnotationRenderer
  });
})(typeof window !== "undefined" ? window : globalThis);
</script>'''
