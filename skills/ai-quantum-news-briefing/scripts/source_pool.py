"""Local acquisition transactions. This store never approves or publishes a daily run.

SQLite owns acquisition leases/results and material revisions only. Existing
capture bytes, daily_revisions, semantic reviews and OSS receipts keep their
existing authority. No network call belongs inside a database transaction.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import sqlite3
import time
import tempfile
import uuid
from contextlib import contextmanager, nullcontext
from datetime import date
from pathlib import Path

MAX_JSON_BYTES = 32_000_000
KINDS = {'academic', 'aihot', 'discovery', 'capture'}
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}\Z')
STATES = {'pending', 'running', 'retry_wait', 'succeeded', 'blocked', 'exhausted'}


class PoolConflict(ValueError):
    pass


def encoded(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(raw) > MAX_JSON_BYTES:
        raise PoolConflict('payload_too_large')
    return raw


def fingerprint(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def task_spec(kind, source_id, coverage_date, inputs, config):
    if kind not in KINDS or not ID.fullmatch(source_id):
        raise PoolConflict('task_kind_or_source_invalid')
    if date.fromisoformat(coverage_date).isoformat() != coverage_date:
        raise PoolConflict('task_date_invalid')
    if not isinstance(inputs, dict) or not isinstance(config, dict):
        raise PoolConflict('task_binding_invalid')
    return {'version': 1, 'kind': kind, 'source_id': source_id, 'coverage_date': coverage_date,
            'inputs': json.loads(encoded(inputs)), 'config': json.loads(encoded(config))}


def checked_path(value):
    p = Path(value).absolute()
    for part in [p] + list(p.parents):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), 'st_file_attributes', 0) & 0x400):
            raise PoolConflict('pool_reparse_path')
    if p.exists() and (not p.is_file() or p.stat().st_nlink > 1):
        raise PoolConflict('pool_not_private_regular_file')
    return p


class SourcePool:
    def __init__(self, database, *, read_only=False):
        self.path = checked_path(database)
        self.news_root = self.path.parent.parent if self.path.parent.name == '_sources' and self.path.name == 'pool.sqlite' else None
        if not read_only:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path.as_uri()+'?mode=ro' if read_only else str(self.path),
                                  uri=read_only, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA foreign_keys=ON')
        try:
            if read_only:
                self.db.execute('PRAGMA query_only=ON')
                if self.db.execute('PRAGMA user_version').fetchone()[0] != 1:
                    raise PoolConflict('pool_schema_incompatible')
                self._initialize()
                self.db.execute('BEGIN')
            else:
                with self.transaction():
                    self._initialize()
        except BaseException:
            self.close()
            raise

    def _initialize(self):
        # Schema validation/creation shares the same writer transaction. Two
        # new workers cannot mistake each other's committed schema for damage.
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, 1):
            raise PoolConflict('pool_schema_incompatible')
        if version == 0:
            existing = self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if existing:
                raise PoolConflict('unknown_database_preserved')
        elif {row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")} != {
                'tasks', 'events', 'materials', 'material_revisions', 'preparation_bindings'}:
            raise PoolConflict('pool_schema_changed')
        if version == 1:
            return
        self.db.execute('''CREATE TABLE IF NOT EXISTS tasks (
              task_id TEXT PRIMARY KEY, spec BLOB NOT NULL, state TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL,
              lease TEXT, lease_until REAL, retry_at REAL, result BLOB, result_sha TEXT,
              checkpoint BLOB, failure BLOB)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS events (
              sequence INTEGER PRIMARY KEY, task_id TEXT NOT NULL, state TEXT NOT NULL,
              observed_at REAL NOT NULL, detail BLOB NOT NULL)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS materials (
              material_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, original_url TEXT NOT NULL,
              current_revision TEXT NOT NULL)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS material_revisions (
              material_id TEXT NOT NULL, revision TEXT NOT NULL, payload BLOB NOT NULL,
              PRIMARY KEY(material_id, revision), FOREIGN KEY(material_id) REFERENCES materials(material_id))''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS preparation_bindings (
              binding_id TEXT PRIMARY KEY, scope BLOB NOT NULL, dependencies BLOB NOT NULL)''')
        self.db.execute('PRAGMA user_version=1')

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def _event(self, task_id, state, now, detail):
        self.db.execute('INSERT INTO events(task_id,state,observed_at,detail) VALUES(?,?,?,?)',
                        (task_id, state, now, encoded(detail)))

    def enqueue(self, spec, *, max_attempts=3):
        normalized = task_spec(spec['kind'], spec['source_id'], spec['coverage_date'], spec['inputs'], spec['config'])
        if normalized != spec or type(spec.get('version')) is not int or type(max_attempts) is not int or not 1 <= max_attempts <= 3:
            raise PoolConflict('task_contract_invalid')
        key = fingerprint(spec)
        with self.transaction():
            row = self.db.execute('SELECT max_attempts FROM tasks WHERE task_id=?', (key,)).fetchone()
            if row and row['max_attempts'] != max_attempts:
                raise PoolConflict('retry_policy_drift')
            if not row:
                self.db.execute('INSERT INTO tasks(task_id,spec,state,max_attempts) VALUES(?,?,?,?)',
                                (key, encoded(spec), 'pending', max_attempts))
                self._event(key, 'pending', time.time(), {})
        return key

    def get(self, task_id):
        row = self.db.execute('SELECT * FROM tasks WHERE task_id=?', (task_id,)).fetchone()
        if not row:
            raise PoolConflict('unknown_task')
        value = dict(row)
        for key in ('spec', 'result', 'checkpoint', 'failure'):
            value[key] = json.loads(value[key]) if value[key] is not None else None
        if fingerprint(value['spec']) != task_id or value['state'] not in STATES:
            raise PoolConflict('task_storage_binding_invalid')
        if (type(value['attempts']) is not int or type(value['max_attempts']) is not int
                or not 0 <= value['attempts'] <= value['max_attempts'] <= 3
                or value['state'] == 'succeeded' and value['result'] is None):
            raise PoolConflict('task_storage_state_invalid')
        if value['result'] is not None and fingerprint(value['result']) != value['result_sha']:
            raise PoolConflict('task_result_corrupt')
        return value

    def claim(self, *, task_id=None, now=None, lease_seconds=300):
        now = time.time() if now is None else now
        if not 1 <= lease_seconds <= 900:
            raise PoolConflict('lease_bound_invalid')
        with self.transaction():
            expired = self.db.execute("SELECT task_id,attempts,max_attempts FROM tasks WHERE state='running' AND lease_until<=?", (now,)).fetchall()
            for row in expired:
                self.get(row['task_id'])  # Corruption is not a resumable worker interruption.
                state = 'exhausted' if row['attempts'] >= row['max_attempts'] else 'retry_wait'
                self.db.execute('UPDATE tasks SET state=?,lease=NULL,lease_until=NULL,retry_at=?,failure=? WHERE task_id=?',
                                (state, now, encoded({'code': 'worker_interrupted', 'retryable': state != 'exhausted'}), row['task_id']))
                self._event(row['task_id'], state, now, {'code': 'worker_interrupted'})
            sql = "SELECT task_id FROM tasks WHERE (state='pending' OR (state='retry_wait' AND retry_at<=?)) AND attempts<max_attempts"
            params = [now]
            if task_id is not None:
                sql += ' AND task_id=?'
                params.append(task_id)
            row = self.db.execute(sql + ' ORDER BY rowid LIMIT 1', params).fetchone()
            if not row:
                return None
            token = uuid.uuid4().hex
            self.db.execute("UPDATE tasks SET state='running',attempts=attempts+1,lease=?,lease_until=?,retry_at=NULL WHERE task_id=?",
                            (token, now + lease_seconds, row['task_id']))
            self._event(row['task_id'], 'running', now, {'lease': token})
            return self.get(row['task_id'])

    def _owned(self, task_id, lease, now):
        row = self.get(task_id)
        if row['state'] != 'running' or row['lease'] != lease or row['lease_until'] <= now:
            raise PoolConflict('stale_or_expired_lease')
        return row

    def complete(self, task_id, lease, result, validator, *, now=None, checkpoint=None):
        body = encoded(result)
        result_sha = hashlib.sha256(body).hexdigest()
        from release_lock import release_lock
        promotes = self.get(task_id)['spec']['kind'] == 'capture'
        guard = release_lock(self.news_root) if promotes and self.news_root is not None else nullcontext()
        with guard, self.transaction():
            now = time.time() if now is None else now() if callable(now) else now
            row = self.get(task_id)
            if row['state'] == 'succeeded' and row['lease'] == lease and row['result_sha'] == result_sha:
                return row  # A committed write followed by lost acknowledgement.
            row = self._owned(task_id, lease, now)
            failures = validator(row['spec'], json.loads(body))
            if not isinstance(failures, list) or failures:
                raise PoolConflict('result_validation_failed')
            if promotes:
                from material_admission import admit_material
                item, capture = row['spec']['inputs']['item'], result['record']
                if not admit_material(row['spec']['source_id'], item, capture):
                    self._put_material(row['spec']['source_id'], item, capture)
            self.db.execute("UPDATE tasks SET state='succeeded',result=?,result_sha=?,checkpoint=?,failure=NULL,lease_until=NULL WHERE task_id=?",
                            (body, result_sha, encoded(checkpoint), task_id))
            self._event(task_id, 'succeeded', now, {'result_sha256': result_sha})
            return self.get(task_id)

    def fail(self, task_id, lease, diagnostic, *, now=None):
        allowed = {'code', 'retryable', 'retry_after_seconds', 'http_status'}
        if (not isinstance(diagnostic, dict) or set(diagnostic) - allowed
                or not ID.fullmatch(str(diagnostic.get('code', '')))
                or type(diagnostic.get('retryable')) is not bool):
            raise PoolConflict('failure_contract_invalid')
        delay = diagnostic.get('retry_after_seconds', 30)
        if type(delay) not in (int, float) or not 0 <= delay <= 86400:
            raise PoolConflict('retry_after_invalid')
        with self.transaction():
            now = time.time() if now is None else now() if callable(now) else now
            row = self._owned(task_id, lease, now)
            state = ('blocked' if not diagnostic['retryable'] else
                     'exhausted' if row['attempts'] >= row['max_attempts'] else 'retry_wait')
            self.db.execute('UPDATE tasks SET state=?,failure=?,lease=NULL,lease_until=NULL,retry_at=? WHERE task_id=?',
                            (state, encoded(diagnostic), now + delay if state == 'retry_wait' else None, task_id))
            self._event(task_id, state, now, diagnostic)
            return self.get(task_id)

    def tasks(self):
        return [self.get(row[0]) for row in self.db.execute('SELECT task_id FROM tasks ORDER BY rowid')]

    def put_material(self, source_id, item, capture):
        from material_admission import admit_material
        failures = admit_material(source_id, item, capture)
        if failures:
            raise PoolConflict('material_not_admitted:' + ','.join(failures))
        from release_lock import release_lock
        guard = release_lock(self.news_root) if self.news_root is not None else nullcontext()
        with guard, self.transaction():
            return self._put_material(source_id, item, capture)

    def _put_material(self, source_id, item, capture):
        url = item['source_url']
        key = fingerprint({'source_id': source_id, 'original_url': url})
        payload = {'item': item, 'capture': capture, 'semantic_review_status': 'not_reviewed'}
        row = self.db.execute('SELECT current_revision FROM materials WHERE material_id=?', (key,)).fetchone()
        previous = self.material(key) if row else None
        same = bool(previous and previous['item'] == item and previous['capture'] == capture)
        if same:
            return {'material_id': key, 'revision': row[0], 'changed': False,
                    'semantic_review_status': 'not_reviewed', 'publication_approved': False}
        generation = previous['generation'] + 1 if previous else 1
        stored = {'generation': generation, 'payload': payload}
        revision = fingerprint(stored)
        if not row:
            self.db.execute('INSERT INTO materials VALUES(?,?,?,?)', (key, source_id, url, revision))
        self.db.execute('INSERT INTO material_revisions VALUES(?,?,?)', (key, revision, encoded(stored)))
        self.db.execute('UPDATE materials SET current_revision=? WHERE material_id=?', (revision, key))
        return {'material_id': key, 'revision': revision, 'changed': not row or row[0] != revision,
                'semantic_review_status': 'not_reviewed', 'publication_approved': False}

    def material(self, key, revision=None):
        row = self.db.execute('SELECT current_revision,source_id FROM materials WHERE material_id=?', (key,)).fetchone()
        if not row:
            raise PoolConflict('unknown_material')
        revision = revision or row[0]
        payload = self.db.execute('SELECT payload FROM material_revisions WHERE material_id=? AND revision=?', (key, revision)).fetchone()
        if not payload or fingerprint(json.loads(payload[0])) != revision:
            raise PoolConflict('material_revision_corrupt')
        stored = json.loads(payload[0])
        return {'material_id': key, 'revision': revision, 'current': revision == row[0],
                'source_id': row['source_id'], 'generation': stored['generation'], **stored['payload']}

    def bind_preparation(self, scope, references):
        if not isinstance(references, list) or not references:
            raise PoolConflict('empty_preparation_dependencies')
        normalized = []
        with self.transaction():
            for ref in references:
                material = self.material(ref['material_id'], ref['revision'])
                if not material['current']:
                    raise PoolConflict('stale_preparation_dependency')
                normalized.append({k: ref[k] for k in ('material_id', 'revision')})
            if len({r['material_id'] for r in normalized}) != len(normalized):
                raise PoolConflict('duplicate_preparation_dependency')
            key = fingerprint({'scope': scope, 'dependencies': normalized})
            self.db.execute('INSERT OR IGNORE INTO preparation_bindings VALUES(?,?,?)',
                            (key, encoded(scope), encoded(normalized)))
        return key

    def validate_preparation(self, binding_id, scope):
        row = self.db.execute('SELECT scope,dependencies FROM preparation_bindings WHERE binding_id=?', (binding_id,)).fetchone()
        if not row or json.loads(row['scope']) != scope:
            return ['preparation_scope_changed']
        if fingerprint({'scope': scope, 'dependencies': json.loads(row['dependencies'])}) != binding_id:
            return ['preparation_binding_corrupt']
        return ['material_revision_changed:' + ref['material_id'] for ref in json.loads(row['dependencies'])
                if not self.material(ref['material_id'], ref['revision'])['current']]

    def backup(self, destination):
        target = checked_path(destination)
        if self.news_root is not None and self.news_root.parent in target.parents:
            raise PoolConflict('pool_backup_must_be_external')
        if target.exists():
            raise PoolConflict('backup_destination_exists')
        target.parent.mkdir(parents=True, exist_ok=True)
        # SQLite backup includes committed WAL content; copying only the .db is unsafe.
        with tempfile.TemporaryDirectory(prefix='.source-pool-backup-', dir=str(target.parent)) as temporary:
            staged = Path(temporary)/'snapshot.sqlite'
            copied = sqlite3.connect(str(staged))
            try:
                self.db.backup(copied)
                if copied.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise PoolConflict('backup_integrity_failed')
            finally:
                copied.close()  # Connection context managers do not close Windows file handles.
            os.link(str(staged), str(target))  # Atomic absent-only admission, never overwrite.
