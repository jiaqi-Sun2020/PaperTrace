"""Save public evidence from an existing byte stream/file, never inline prose.

Successful persistence proves exact bytes only. Discovery/article validators and
actual reviews retain authority. No browser, transport, credentials or retry.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,os,re,stat,tempfile
from datetime import date,timedelta
from pathlib import Path
from source_pool import checked_path,PoolConflict

MAX_BYTES=32_000_000

def evidence_target(output,news_root,day):
    date.fromisoformat(day)
    root=Path(news_root).absolute()/'_collection'/day
    output=checked_path(output)
    try:relative=output.relative_to(root)
    except ValueError:raise PoolConflict('evidence_output_outside_issue')
    if (len(relative.parts)!=1 or output.suffix!='.json'
            or re.search(r'cookie|credential|secret|token|password|session',output.name,re.I)):
        raise PoolConflict('evidence_output_invalid')
    return output

def install_absent(staged, target):
    # Windows rename preserves absent-only installation without requiring a hard link.
    if os.name == 'nt':
        os.rename(staged, target)
    else:
        os.link(staged, target)


def probe_evidence_directory(news_root,day):
    target=evidence_target(Path(news_root)/'_collection'/day/'capability-probe.json',news_root,day)
    target.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.evidence-probe-',dir=target.parent)
    linked=Path(name+'.linked')
    installed=False
    try:
        with os.fdopen(fd,'wb') as out:out.write(b'public-evidence-capability');out.flush();os.fsync(out.fileno())
        install_absent(name,linked)
        installed=True
        if linked.read_bytes()!=b'public-evidence-capability':raise PoolConflict('evidence_probe_integrity_failed')
    finally:
        if installed and linked.exists():linked.unlink()
        if Path(name).exists():Path(name).unlink()
    return {'status':'evidence_persistence_available','scope':str(target.parent),'proves':'write, fsync and no-clobber installation; not browser/HTTP access'}

def validate_public_http_receipt(raw,day):
    from daily_coverage_evidence import HTTP_RECEIPT_KEYS,_public_url,_http_record,_day_bounds
    value=json.loads(raw.decode('utf-8'));coverage=(date.fromisoformat(day)-timedelta(days=1)).isoformat()
    start,end=_day_bounds(coverage)
    if (not isinstance(value,dict) or set(value)!=HTTP_RECEIPT_KEYS
            or not _public_url(value.get('query_url')) or not _public_url(value.get('final_url'))
            or not _http_record(value,start,end) or value.get('hash_scope')!='raw_http_bytes'
            or not isinstance(value.get('body_base64'),str) or len(value['body_base64'])>1400000):
        raise PoolConflict('public_http_receipt_invalid')
    body=base64.b64decode(value['body_base64'],validate=True)
    if not body or hashlib.sha256(body).hexdigest()!=value['response_hash']:
        raise PoolConflict('public_http_receipt_body_mismatch')

def validate_discovery_evidence(raw,day):
    from daily_coverage_evidence import validate_rendered_search_observation
    coverage=(date.fromisoformat(day)-timedelta(days=1)).isoformat()
    if validate_rendered_search_observation(json.loads(raw.decode('utf-8')),coverage):
        raise PoolConflict('discovery_evidence_invalid')


def persist_public_evidence(source,output,news_root,day,expected_sha256,expected_bytes,*,validator=None,fault=lambda boundary:None):
    if (not re.fullmatch('[0-9a-f]{64}',str(expected_sha256))
            or type(expected_bytes) is not int or not 0<expected_bytes<=MAX_BYTES):
        raise PoolConflict('evidence_integrity_binding_required')
    output=evidence_target(output,news_root,day);source=checked_path(source)
    if re.search(r'cookie|credential|secret|token|password|session',source.name,re.I):raise PoolConflict('evidence_input_not_public')
    fault('before_read')
    with source.open('rb') as stream:raw=stream.read(MAX_BYTES+1)
    if len(raw)!=expected_bytes or hashlib.sha256(raw).hexdigest()!=expected_sha256:
        raise PoolConflict('evidence_source_changed_or_truncated')
    json.loads(raw.decode('utf-8'))
    if validator:validator(raw,day)
    fault('after_read')
    def existing():
        checked_path(output)  # Recheck a path that may have appeared after the first validation.
        if output.is_file():
            before=output.stat()
            with output.open('rb') as stream:
                opened=os.fstat(stream.fileno())
                same=(opened.st_dev,opened.st_ino)==(before.st_dev,before.st_ino)
                valid=stat.S_ISREG(opened.st_mode) and opened.st_nlink==1 and opened.st_size==len(raw)
                body=stream.read(len(raw)+1) if same and valid else None
            checked_path(output)
            after=output.stat()
            if same and valid and (after.st_dev,after.st_ino)==(opened.st_dev,opened.st_ino) and body==raw:return True
        raise PoolConflict('evidence_unknown_output_preserved')
    if output.exists():existing();return {'status':'reused','sha256':expected_sha256,'bytes':expected_bytes}
    output.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.evidence-',suffix='.tmp',dir=output.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        fault('before_install')
        try:install_absent(name,output)
        except FileExistsError:
            existing()
            return {'status':'reused','sha256':expected_sha256,'bytes':expected_bytes}
        fault('after_install')
    finally:
        if Path(name).exists():Path(name).unlink()
    return {'status':'saved','sha256':expected_sha256,'bytes':expected_bytes,'publication_approved':False}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('probe','save','save-discovery'));p.add_argument('--news-root',type=Path,required=True)
    p.add_argument('--date',required=True);p.add_argument('--input',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--expected-sha256');p.add_argument('--expected-bytes',type=int)
    a=p.parse_args(argv)
    try:
        result=probe_evidence_directory(a.news_root,a.date) if a.action=='probe' else persist_public_evidence(
            a.input,a.output,a.news_root,a.date,a.expected_sha256,a.expected_bytes,validator=validate_discovery_evidence if a.action=='save-discovery' else validate_public_http_receipt)
        print(json.dumps(result));return 0
    except (OSError,ValueError,TypeError,AttributeError) as e:
        print(json.dumps({'status':'evidence_persistence_failed','code':str(e) if isinstance(e,PoolConflict) else type(e).__name__,'operation':a.action,'exception_type':type(e).__name__,'errno':getattr(e,'errno',None),'winerror':getattr(e,'winerror',None)}));return 2

if __name__=='__main__':raise SystemExit(main())
