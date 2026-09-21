#!/usr/bin/env python3
"""Shared browser-local feedback recovery for standalone PaperTrace HTML."""

from __future__ import annotations

import json
import re


STORAGE_KEY_PREFIX = "paper.reader.feedback-draft.v1:"
RECOVERY_VERSION = 1
MAX_ITEMS = 500
MAX_BYTES = 4 * 1024 * 1024


def feedback_recovery_script(paper_fingerprint: str) -> str:
    """Return the shared feedback-recovery runtime for one paper fingerprint."""

    fingerprint = str(paper_fingerprint or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("paper_fingerprint must be a full SHA-256 hex digest")
    config = json.dumps(
        {
            "version": RECOVERY_VERSION,
            "storage_key": f"{STORAGE_KEY_PREFIX}{fingerprint}",
            "paper_fingerprint": fingerprint,
            "max_items": MAX_ITEMS,
            "max_bytes": MAX_BYTES,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    return f'''<script data-papertrace-feedback-recovery="v1">
(function (root) {{
  "use strict";
  const DEFAULTS = {config};

  function createFeedbackRecovery(options) {{
    const settings = Object.assign({{}}, DEFAULTS, options || {{}});
    let storage = settings.storage || null;
    if (!storage) {{
      try {{ storage = root.localStorage; }} catch (_error) {{ storage = null; }}
    }}
    let timer = null;
    let pendingFactory = null;
    let unsafeChanges = false;

    function notify(kind, message, savedAt) {{
      if (typeof settings.onStatus === 'function') {{
        settings.onStatus({{ kind, message, saved_at: savedAt || null }});
      }}
    }}

    function validEnvelope(value) {{
      return !!value
        && value.version === settings.version
        && value.paper_fingerprint === settings.paper_fingerprint
        && Array.isArray(value.items)
        && value.items.length <= settings.max_items
        && (value.draft === null || (value.draft && typeof value.draft === 'object'))
        && (value.exported_at === null || value.exported_at === undefined || typeof value.exported_at === 'string');
    }}

    function load() {{
      if (!storage) {{
        notify('warning', 'Local recovery is unavailable; export JSON before closing.');
        return null;
      }}
      try {{
        const raw = storage.getItem(settings.storage_key);
        if (!raw) return null;
        if (raw.length > settings.max_bytes) throw new Error('local recovery payload is too large');
        const value = JSON.parse(raw);
        if (!validEnvelope(value)) throw new Error('local recovery payload does not match this paper');
        notify('restored', 'Recovered local annotations and draft.', value.saved_at || null);
        return value;
      }} catch (_error) {{
        notify('warning', 'Local recovery data is invalid; it was ignored. Export JSON before closing.');
        return null;
      }}
    }}

    function persist(envelope) {{
      if (!storage) {{
        unsafeChanges = true;
        notify('warning', 'Local recovery is unavailable; export JSON before closing.');
        return false;
      }}
      try {{
        const items = Array.isArray(envelope && envelope.items) ? envelope.items : [];
        if (items.length > settings.max_items) throw new Error('too many local feedback items');
        const savedAt = new Date().toISOString();
        const normalized = {{
          version: settings.version,
          paper_fingerprint: settings.paper_fingerprint,
          saved_at: savedAt,
          exported_at: envelope && envelope.exported_at ? String(envelope.exported_at) : null,
          items,
          draft: envelope && envelope.draft && typeof envelope.draft === 'object' ? envelope.draft : null
        }};
        const serialized = JSON.stringify(normalized);
        if (serialized.length > settings.max_bytes) throw new Error('local recovery payload is too large');
        storage.setItem(settings.storage_key, serialized);
        unsafeChanges = false;
        notify('saved', 'Local recovery saved in this browser.', savedAt);
        return true;
      }} catch (_error) {{
        unsafeChanges = true;
        notify('warning', 'Local recovery failed; export JSON before closing.');
        return false;
      }}
    }}

    function schedule(factory, delay) {{
      pendingFactory = typeof factory === 'function' ? factory : null;
      if (timer !== null && typeof root.clearTimeout === 'function') root.clearTimeout(timer);
      if (!pendingFactory) return;
      if (typeof root.setTimeout !== 'function') {{ flush(); return; }}
      timer = root.setTimeout(flush, Number.isFinite(delay) ? delay : 250);
    }}

    function flush() {{
      if (timer !== null && typeof root.clearTimeout === 'function') root.clearTimeout(timer);
      timer = null;
      if (!pendingFactory) return !unsafeChanges;
      const factory = pendingFactory;
      pendingFactory = null;
      return persist(factory());
    }}

    function clear() {{
      if (timer !== null && typeof root.clearTimeout === 'function') root.clearTimeout(timer);
      timer = null;
      pendingFactory = null;
      if (!storage) {{
        unsafeChanges = false;
        notify('cleared', 'No browser recovery copy is stored.');
        return true;
      }}
      try {{
        storage.removeItem(settings.storage_key);
        unsafeChanges = false;
        notify('cleared', 'Local recovery copy cleared.');
        return true;
      }} catch (_error) {{
        unsafeChanges = true;
        notify('warning', 'The local recovery copy could not be cleared.');
        return false;
      }}
    }}

    return Object.freeze({{
      storageKey: settings.storage_key,
      paperFingerprint: settings.paper_fingerprint,
      load,
      persist,
      schedule,
      flush,
      clear,
      hasUnsafeChanges: () => unsafeChanges
    }});
  }}

  root.PaperTraceFeedbackRecovery = Object.freeze({{
    version: DEFAULTS.version,
    create: createFeedbackRecovery
  }});
}})(typeof window !== 'undefined' ? window : globalThis);
</script>'''

