"""Synthetic fourteen-source fixtures: preflight/commit gap is never approval."""
from contextlib import redirect_stdout
from copy import deepcopy
import base64,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import daily_revisions as dr
import daily_authoring as da
from collection_checkpoint import atomic_json

class MigrationCommitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.day='2026-10-10';self.run=self.day+'-0123456789ab';self.stage=self.root/self.day/'.staging'/self.run
        atomic_json(self.stage/('daily_pipeline_manifest_'+self.day+'.json'),{'pipeline_version':4,'status':'staged','date':self.day,'run_id':self.run})
        self.candidate=dr.candidate_path(self.root,self.day);atomic_json(self.candidate,{'news_feedback_version':1,'sections':[]})
        self.index=self.root/'_index/story_index.jsonl';self.index.parent.mkdir(exist_ok=True);self.index.write_bytes(b'original index\n')
        self.captures=[]
        for i in range(14):
            path=self.root/'_collection/2026-10-09/source_captures'/('C%02d.json'%i);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(('synthetic capture %d'%i).encode());self.captures.append(path)
        self.binding=dr.normalize_evidence_binding(self.day,{'version':1,'date':self.day,'files':[{'path':p.relative_to(self.root).as_posix(),'sha256':dr.sha(p)} for p in self.captures],'index_sha256':dr.sha(self.index)})
        self.run_sha=dr.run_snapshot(self.root,self.stage)['sha256'];self.candidate_sha=dr.sha(self.candidate)
    def revise(self):
        return dr.revise(self.root,self.day,self.run,self.run_sha,self.candidate_sha,'synthetic migration boundary test',verify=lambda *a,**k:{'status':'fail'},expected_evidence=self.binding)
    def assert_not_committed(self):
        self.assertFalse(dr.lifecycle_path(self.root,self.day).exists());self.assertEqual(dr.active_stages(self.root,self.day),[self.stage])
    def test_each_of_fourteen_captures_changed_after_preflight_is_rejected(self):
        for source in self.captures:
            with self.subTest(source=source.name):
                old=source.read_bytes();source.write_bytes(old+b'changed')
                try:
                    with self.assertRaisesRegex(ValueError,'capture_evidence_conflict'):self.revise()
                    self.assert_not_committed()
                finally:source.write_bytes(old)
    def test_index_changed_after_preflight_is_rejected(self):
        self.index.write_bytes(b'new index')
        with self.assertRaisesRegex(ValueError,'index_evidence_conflict'):self.revise()
        self.assert_not_committed()
    def test_candidate_changed_after_preflight_is_rejected(self):
        self.candidate.write_bytes(self.candidate.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'candidate_conflict'):self.revise()
        self.assert_not_committed()
    def test_new_same_day_stage_after_preflight_is_rejected(self):
        other=self.root/self.day/'.staging'/(self.day+'-abcdefabcdef');other.mkdir()
        with self.assertRaisesRegex(ValueError,'multiple_active_runs'):self.revise()
        self.assertFalse(dr.lifecycle_path(self.root,self.day).exists())
    def test_capture_change_during_material_write_is_rechecked_before_commit(self):
        original=dr.atomic_bytes;changed=[False]
        def edit(path,body):
            original(path,body)
            if not changed[0]:changed[0]=True;self.captures[0].write_bytes(b'noncooperating editor change')
        with patch.object(dr,'atomic_bytes',side_effect=edit):
            with self.assertRaisesRegex(ValueError,'capture_evidence_conflict'):self.revise()
        self.assert_not_committed()
    def test_new_stage_during_material_write_is_rechecked_before_commit(self):
        original=dr.atomic_bytes;changed=[False]
        def edit(path,body):
            original(path,body)
            if not changed[0]:changed[0]=True;(self.root/self.day/'.staging'/(self.day+'-abcdefabcdef')).mkdir()
        with patch.object(dr,'atomic_bytes',side_effect=edit):
            with self.assertRaisesRegex(ValueError,'multiple_active_runs'):self.revise()
        self.assertFalse(dr.lifecycle_path(self.root,self.day).exists())
    def test_index_change_during_material_write_is_rechecked_before_commit(self):
        original=dr.atomic_bytes;changed=[False]
        def edit(path,body):
            original(path,body)
            if not changed[0]:changed[0]=True;self.index.write_bytes(b'noncooperating index change')
        with patch.object(dr,'atomic_bytes',side_effect=edit):
            with self.assertRaisesRegex(ValueError,'index_evidence_conflict'):self.revise()
        self.assert_not_committed()
    def test_binding_is_in_identity_and_repeat_must_match(self):
        result=self.revise();self.assertEqual(result['status'],'revision_created');self.assertFalse(result['content_approved'])
        state=dr.lifecycle(self.root,self.day);self.assertEqual(state['superseded_runs'][self.run]['external_evidence_sha256'],dr.fingerprint(self.binding))
        self.assertEqual(self.revise()['status'],'revision_unchanged')
        with self.assertRaisesRegex(ValueError,'repeat_conflict'):
            dr.revise(self.root,self.day,self.run,self.run_sha,self.candidate_sha,'synthetic migration boundary test',verify=lambda *a,**k:{'status':'fail'})
    def test_unsafe_or_wrong_date_binding_rejected_without_file_read(self):
        for path in ('../outside.json','_collection/2026-10-08/source_captures/C00.json','_collection/2026-10-09/source_captures/../C00.json'):
            value=deepcopy(self.binding);value['files'][0]['path']=path
            with self.subTest(path=path),self.assertRaisesRegex(ValueError,'binding_invalid'):dr.normalize_evidence_binding(self.day,value)
    def test_cli_forwards_bound_evidence_and_rejects_nonrevision_use(self):
        encoded=base64.b64encode(json.dumps(self.binding).encode()).decode()
        args=['revise','--date',self.day,'--run-id',self.run,'--expected-run-sha256',self.run_sha,'--expected-sha256',self.candidate_sha,'--reason','cli synthetic binding','--expected-evidence-base64',encoded]
        with patch.object(da,'NEWS_ROOT',self.root),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(da.main(args),0)
            self.assertEqual(json.loads(output.getvalue())['status'],'revision_created')
            self.assertEqual(da.main(['probe','--date',self.day,'--expected-evidence-base64',encoded]),2)

if __name__=='__main__':unittest.main()
