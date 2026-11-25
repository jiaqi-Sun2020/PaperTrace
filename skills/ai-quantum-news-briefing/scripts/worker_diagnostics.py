"""Bounded metadata only. Never a review, HTTP receipt or workflow authority."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time

from source_pool import checked_path

PHASES = {'prepared', 'process_starting', 'process_started', 'progress', 'process_exited',
          'cleanup_started', 'cleanup_complete', 'cleanup_unconfirmed', 'output_first_byte',
          'receipt_read', 'receipt_valid', 'receipt_missing', 'receipt_invalid',
          'input_write_failed', 'receipt_read_failed', 'timeout', 'completed', 'blocked',
          'worker_session_started', 'inference_started', 'inference_finished',
          'worker_error_hint', 'tool_started', 'tool_finished', 'unknown_phase'}
CATEGORIES = {'command_execution': 'command', 'mcp_tool_call': 'mcp', 'web_search': 'web_search',
              'file_change': 'file_write', 'agent_message': 'agent_output', 'reasoning': 'reasoning'}
SAFE_ERRORS = {'PermissionError', 'FileNotFoundError', 'OSError', 'ValueError', 'TypeError',
               'RuntimeError', 'JSONDecodeError', 'UnicodeDecodeError', 'RecursionError'}


def error_metadata(exc):
    name = type(exc).__name__
    return {'type': name if name in SAFE_ERRORS else 'Exception',
            'errno': exc.errno if type(getattr(exc, 'errno', None)) is int else None,
            'winerror': exc.winerror if type(getattr(exc, 'winerror', None)) is int else None}


def install_new_json(path, value):
    """Immutable absent-only metadata admission. Never replace unknown files."""
    path = checked_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode()
    fd, name = tempfile.mkstemp(prefix='.worker-metadata-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(name, path)  # atomic no-overwrite; a denial has no alternative path
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return hashlib.sha256(data).hexdigest()


class WorkerTrace:
    MAX_EVENTS = 96
    MAX_CHECKPOINTS = 128
    MAX_LINE = 65536

    def __init__(self, work, *, job, date, role, input_sha256):
        if not re.fullmatch('[0-9a-f]{32}', job) or not re.fullmatch('[0-9a-f]{64}', input_sha256):
            raise ValueError('diagnostic_binding_invalid')
        if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', date):
            raise ValueError('diagnostic_date_invalid')
        self.work = Path(work)
        self.binding = {'job_id': job, 'date': date, 'input_sha256': input_sha256,
                        'role': role if role in {'discovery','qualification','author','repair','news_review','story_blind','story_review','display_review'} else 'unknown'}
        self.start = time.monotonic()
        self.lock = threading.RLock()
        self.events = []
        self.counts = {}
        self.dropped = 0
        self.errors = []
        self.lines = {'invalid': 0, 'oversized': 0, 'unknown': 0}
        self.buffer = bytearray()
        self.discard_line = False
        self.tools = {}
        self.index = 0
        self.final = None
        self.final_sha = None

    def _error(self, location, exc):
        with self.lock:
            if len(self.errors) < 4:
                self.errors.append({'location': location, **error_metadata(exc)})

    def observe(self, phase, **values):
        with self.lock:
            phase = phase if isinstance(phase,str) and phase in PHASES else 'unknown_phase'
            event = {'phase': phase, 'elapsed_ms': max(0, int((time.monotonic()-self.start)*1000))}
            for key in ('returncode', 'output_bytes', 'duration_ms'):
                if type(values.get(key)) is int:
                    event[key] = values[key]
            if isinstance(values.get('category'),str) and values['category'] in set(CATEGORIES.values()) | {'unknown'}:
                event['category'] = values['category']
            self.counts[phase] = self.counts.get(phase, 0) + 1
            if len(self.events) < self.MAX_EVENTS:
                self.events.append(event)
            else:
                self.dropped += 1

    def feed(self, data):
        """Parse optional JSONL event hints; discard all text, args and tool data."""
        with self.lock:
            for offset in range(0, len(data), 8192):
                chunk = data[offset:offset+8192]
                for part_index, part in enumerate(chunk.split(b'\n')):
                    if part_index:
                        if not self.discard_line:
                            self._line(bytes(self.buffer))
                        self.buffer.clear()
                        self.discard_line = False
                    if not self.discard_line:
                        if len(self.buffer) + len(part) > self.MAX_LINE:
                            self.buffer.clear()
                            self.discard_line = True
                            self.lines['oversized'] += 1
                        else:
                            self.buffer.extend(part)

    def _line(self, line):
        if not line.strip():
            return
        try:
            value = json.loads(line)
        except (ValueError, UnicodeError, RecursionError):
            self.lines['invalid'] += 1
            return
        if not isinstance(value, dict):
            self.lines['unknown'] += 1
            return
        event = value.get('type')
        simple = {'thread.started':'worker_session_started', 'turn.started':'inference_started',
                  'turn.completed':'inference_finished', 'turn.failed':'worker_error_hint', 'error':'worker_error_hint'}
        if isinstance(event, str) and event in simple:
            self.observe(simple[event])
        elif event in ('item.started', 'item.completed') and isinstance(value.get('item'), dict):
            item = value['item']
            category = CATEGORIES.get(item.get('type'), 'unknown') if isinstance(item.get('type'), str) else 'unknown'
            identifier = item.get('id')
            duration = None
            if isinstance(identifier, str) and len(identifier) <= 128:
                if event == 'item.started' and len(self.tools) < 64:
                    self.tools[identifier] = time.monotonic()
                elif identifier in self.tools:
                    duration = int((time.monotonic()-self.tools.pop(identifier))*1000)
            self.observe('tool_started' if event == 'item.started' else 'tool_finished',
                         category=category, **({'duration_ms':duration} if duration is not None else {}),
                         **({'returncode':item['exit_code']} if category=='command' and type(item.get('exit_code')) is int else {}))
        else:
            self.lines['unknown'] += 1

    def _snapshot(self):
        with self.lock:
            return {'version':1, 'binding':dict(self.binding), 'authority':'diagnostic_hints_only',
                    'events':list(self.events), 'phase_counts':dict(self.counts),
                    'dropped_events':self.dropped, 'line_counts':dict(self.lines),
                    'diagnostic_errors':list(self.errors), 'raw_text_retained':False}

    def checkpoint(self):
        with self.lock:
            if self.index >= self.MAX_CHECKPOINTS or self.final is not None:
                return
            index = self.index
            self.index += 1
        try:
            install_new_json(self.work/'worker-diagnostics'/('%04d.json' % index), self._snapshot())
        except Exception as exc:
            self._error('checkpoint', exc)

    def finish(self, *, outcome, output=None, cleanup_confirmed=None):
        if self.final is not None:
            return self.summary()
        # Only program-owned outcome enums; never echo a model-provided code.
        self.observe(outcome if outcome in {'completed','blocked','timeout'} else 'blocked')
        value = self._snapshot()
        value['outcome'] = outcome if outcome in {'completed','blocked','timeout'} else 'blocked'
        value['cleanup_confirmed'] = cleanup_confirmed if type(cleanup_confirmed) is bool else None
        value['process_output'] = {}
        for key in ('observed_bytes','complete','observer_failed','read_failed','returncode'):
            item = (output or {}).get(key)
            if type(item) in (bool,int) or item is None:
                value['process_output'][key] = item
        digest = (output or {}).get('sha256')
        if isinstance(digest,str) and re.fullmatch('[0-9a-f]{64}',digest):
            value['process_output']['sha256'] = digest
        self.final = value
        try:
            self.final_sha = install_new_json(self.work/'worker-diagnostics.json',value)
        except Exception as exc:
            self._error('finalize',exc)
        return self.summary()

    def summary(self):
        return {'status':'saved' if self.final_sha and not self.errors else 'incomplete',
                'artifact':'worker-diagnostics.json' if self.final_sha else None,
                'sha256':self.final_sha, 'errors':list(self.errors), 'raw_text_retained':False}
