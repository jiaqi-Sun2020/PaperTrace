"""Short transactions in the existing workflow queue; no new scheduler/store."""
from __future__ import annotations
import time,uuid
from pathlib import Path
from collection_checkpoint import atomic_json
from release_lock import release_lock
from source_pool import PoolConflict,fingerprint,checked_path
import json,math

def _queue(root):
    path=checked_path(Path(root)/'_automation/workflow_queue.json')
    if path.is_file() and path.stat().st_size>32_000_000:raise PoolConflict('workflow_queue_too_large')
    value=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'version':1,'dates':[]}
    if not isinstance(value,dict) or type(value.get('version')) is not int or value.get('version')!=1 or not isinstance(value.get('dates'),list):
        raise PoolConflict('workflow_queue_invalid')
    records=value.get('daily_continuations',{})
    if not isinstance(records,dict):raise PoolConflict('daily_continuation_invalid')
    return path,value,records

def _record(day,value):
    if not isinstance(value,dict):raise PoolConflict('daily_continuation_invalid')
    if value and (type(value.get('version')) is not int or value['version']!=1 or value.get('date')!=day
                  or not isinstance(value.get('attempts',[]),list)):
        raise PoolConflict('daily_continuation_invalid')
    lease=value.get('lease')
    if lease is not None and (not isinstance(lease,dict) or set(lease)!={'id','expires_at'}
         or not isinstance(lease['id'],str) or len(lease['id'])!=32
         or type(lease['expires_at']) not in (int,float) or not math.isfinite(lease['expires_at'])):
        raise PoolConflict('daily_continuation_invalid')
    return value

def begin(root,day,*,now=None,policy=None):
    now=time.time() if now is None else now
    with release_lock(root):
        path,queue,records=_queue(root);record=_record(day,records.get(day,{}))
        lease=record.get('lease')
        if lease and lease['expires_at']>now:raise PoolConflict('daily_attempt_already_running')
        identity=uuid.uuid4().hex
        record={**record,'version':1,'date':day,'lease':{'id':identity,'expires_at':now+900},
                'policy_sha256':fingerprint(policy) if policy else None}
        records[day]=record;queue['daily_continuations']=records;atomic_json(path,queue)
        return identity

def finish(root,day,identity,result,*,now=None):
    now=time.time() if now is None else now
    with release_lock(root):
        path,queue,records=_queue(root);record=_record(day,records.get(day,{}))
        if (record.get('lease') or {}).get('id')!=identity:raise PoolConflict('daily_attempt_lease_lost')
        retry=result.get('recovery',{}).get('earliest_retry_at')
        transition={'observed_at':now,'phase':result.get('phase'),'run_outcome':result.get('run_outcome'),
                    'terminal_blocker':result.get('terminal_blocker'),'retry_at':retry}
        record.setdefault('attempts',[]).append(transition)
        record.update(lease=None,last_transition=transition,
                      continuation={'date':day,'earliest_retry_at':retry,'resume_commands':result.get('next_commands',[]),
                                    'automation_id':'ai','scheduling_status':'not_scheduled_by_code',
                                    'notification_status':'reviewable_handoff_only'})
        records[day]=record;queue['daily_continuations']=records;atomic_json(path,queue)
        return record['continuation']
