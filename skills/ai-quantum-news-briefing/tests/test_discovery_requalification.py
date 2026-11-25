"""Synthetic offline tests: repaired format evidence never resets a denial/budget."""
from copy import deepcopy
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
from source_pool import SourcePool,PoolConflict,task_spec,fingerprint
import source_worker as worker
from source_recovery import reconcile_saved_discovery
from discovery_navigation import navigation_request
from daily_delivery_policy import policy_snapshot
from daily_coverage_evidence import adapt_rendered_search_observation
from test_source_preparation_flow import discovery_fixture

LEGACY={'code':'rendered_search_evidence_invalid','retryable':False}

class DiscoveryRequalificationTests(unittest.TestCase):
    def setUp(self):
        (SCRIPTS.parents[2]/'.tmp').mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='discovery-requal-',dir=str(SCRIPTS.parents[2]/'.tmp'))
        self.addCleanup(self.tmp.cleanup)
        self.pool=SourcePool(Path(self.tmp.name)/'news/_sources/pool.sqlite')
        self.addCleanup(self.pool.close)
        self.code=worker.code_binding()
        self.request=navigation_request('executive_social','2026-10-24')
        self.value=adapt_rendered_search_observation(discovery_fixture(self.request),'2026-10-24')

    def prepare(self,failure=LEGACY,attempts=1):
        old_code={**self.code,'source_recovery.py':'0'*64}
        inputs={'navigation':self.request}
        old=self.pool.enqueue(task_spec('discovery','executive_social','2026-10-24',inputs,
            {'code':old_code,'policy':policy_snapshot()}))
        for index in range(attempts):
            owner=self.pool.claim(task_id=old,now=index+1)
            cause=failure if index==attempts-1 else {'code':'temporary','retryable':True,'retry_after_seconds':0}
            self.pool.fail(old,owner['lease'],cause,now=index+1)
        spec=task_spec('discovery','executive_social','2026-10-24',inputs,{'code':self.code,'policy':policy_snapshot()})
        key=self.pool.enqueue_compatible(spec,worker.validate_result)
        return old,key

    def reconcile(self,key,value=None,failure_sha=None,input_sha=None):
        return reconcile_saved_discovery(self.pool,key,value or self.value,
            expected_failure_sha256=failure_sha or fingerprint(LEGACY),
            input_sha256=input_sha or fingerprint(self.value),reason='fixed_rendered_search_adapter')

    def test_requalifies_only_new_alias_and_preserves_old_history_and_attempts(self):
        old,key=self.prepare();before=deepcopy(self.pool.get(old))
        result=self.reconcile(key)
        self.assertEqual(result['status'],'saved_discovery_requalified')
        self.assertEqual(self.pool.get(key)['state'],'succeeded')
        self.assertEqual(self.pool.get(key)['attempts'],1)
        self.assertEqual(self.pool.get(old),before)
        self.assertEqual(self.pool._compatible_budget(self.pool._compatible_rows(self.pool.get(key)['spec']))[0],1)

    def test_ack_replay_is_idempotent_and_different_evidence_conflicts(self):
        _,key=self.prepare();self.reconcile(key)
        count=self.pool.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        self.assertEqual(self.reconcile(key)['status'],'already_requalified')
        self.assertEqual(self.pool.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],count)
        with self.assertRaises(PoolConflict):self.reconcile(key,input_sha='1'*64)

    def assert_denial_retained(self,failure):
        _,key=self.prepare(failure=failure);before=self.pool.get(key)
        with self.assertRaises(PoolConflict):self.reconcile(key,failure_sha=fingerprint(failure))
        self.assertEqual(self.pool.get(key),before)

    def test_policy_denial_does_not_reopen(self):
        self.assert_denial_retained({'code':'policy_rejected','retryable':False})

    def test_http_403_does_not_reopen(self):
        self.assert_denial_retained({'code':'http_forbidden','retryable':False,'http_status':403})

    def test_other_business_failures_do_not_reopen(self):
        self.assert_denial_retained({'code':'source_unknown','retryable':False})

    def test_exhausted_budget_cannot_be_requalified(self):
        _,key=self.prepare(attempts=3)
        before=self.pool.get(key)
        with self.assertRaises(PoolConflict):self.reconcile(key)
        self.assertEqual(self.pool.get(key),before)

    def test_changed_failure_digest_or_query_rejected_before_mutation(self):
        _,key=self.prepare();before=self.pool.get(key)
        with self.assertRaises(PoolConflict):self.reconcile(key,failure_sha='2'*64)
        invalid=deepcopy(self.value);invalid['source_class']='official_company_social'
        with self.assertRaises(PoolConflict):self.reconcile(key,value=invalid)
        self.assertEqual(self.pool.get(key),before)

    def test_old_code_identity_is_not_reopened(self):
        old,_=self.prepare()
        with self.assertRaises(PoolConflict):self.reconcile(old)
        self.assertEqual(self.pool.get(old)['state'],'blocked')

if __name__=='__main__':unittest.main()
