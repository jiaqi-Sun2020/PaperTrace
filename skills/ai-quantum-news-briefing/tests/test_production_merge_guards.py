"""Native Windows junction coverage; never accesses production or OSS."""
import os, shutil, subprocess, sys, tempfile, unittest
from argparse import Namespace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import daily_authoring as author
import daily_revisions as revisions
import daily_pipeline as pipeline
from source_capture import admit_candidates
import test_publication_v4 as fixtures
import test_release_protocol as reviewed
from unittest.mock import patch
from types import SimpleNamespace

class SyntheticReviewInvalidationTests(unittest.TestCase):
    setUp=fixtures.V4PublicationTests.setUp
    prepare=fixtures.V4PublicationTests.prepare
    write_candidate=fixtures.V4PublicationTests.write_candidate
    stage=fixtures.V4PublicationTests.stage
    def test_prior_approved_reviews_cannot_approve_changed_formula_revision(self):
        self.prepare(); old, old_manifest_path, manifest=self.stage()
        reviewed.ReviewedReleaseTests._write_reviews(SimpleNamespace(stage=old,date=self.release,manifest_path=old_manifest_path))
        approved_news=(old/('news_content_review_'+self.release+'.json')).read_bytes()
        approved_story=(old/('opening_story_review_'+self.release+'.json')).read_bytes()
        self.assertTrue(all(i['judgment']=='pass' for i in pipeline.load_json(old/('news_content_review_'+self.release+'.json'))['items']))
        current=revisions.candidate_path(self.news,self.release); current.parent.mkdir(parents=True,exist_ok=True)
        current.write_bytes(self.candidate.read_bytes())
        result=revisions.revise(self.news,self.release,manifest['run_id'],revisions.run_snapshot(self.news,old)['sha256'],
                                revisions.sha(current),'Repair synthetic failed display before sealing',verify=pipeline.verify_artifacts)
        candidate=Path(result['candidate']); draft=pipeline.load_json(candidate)
        draft['opening_story']['worked_example']['steps'][0]['formula']=r'x=80\%'
        author.save(self.news,self.release,'candidate',revisions.sha(candidate),draft)
        self.args.config=str(candidate); self.assertEqual(pipeline.cmd_run(self.args),0)
        new=revisions.active_stages(self.news,self.release)[0]
        self.assertEqual(pipeline.cmd_review_template(Namespace(run_dir=str(new))),0)
        self.assertTrue(all(i['judgment']=='unreviewed' for i in pipeline.load_json(new/('news_content_review_'+self.release+'.json'))['items']))
        (new/('news_content_review_'+self.release+'.json')).write_bytes(approved_news)
        (new/('opening_story_review_'+self.release+'.json')).write_bytes(approved_story)
        failures=pipeline.verify_artifacts(new,strict=True)['failures']
        self.assertTrue(any('story' in f and ('differs' in f or 'match' in f) for f in failures), failures)
        self.assertEqual(pipeline.cmd_seal_review(Namespace(run_dir=str(new))),1)

@unittest.skipUnless(os.name=='nt','Windows native junction test')
class NativeJunctionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name); self.news=self.base/'news'; self.target=self.base/'target'
        self.target.mkdir(); (self.target/'sentinel.txt').write_text('unchanged',encoding='utf-8')
        self.day='2026-10-10'; self.run=self.day+'-0123456789ab'
    def junction(self,path):
        path.parent.mkdir(parents=True,exist_ok=True)
        shell=shutil.which('pwsh') or shutil.which('powershell')
        if not shell: self.skipTest('PowerShell unavailable: native junction could not be created')
        command="New-Item -ItemType Junction -Path '"+str(path).replace("'","''")+"' -Target '"+str(self.target).replace("'","''")+"' | Out-Null"
        result=subprocess.run([shell,'-NoProfile','-NonInteractive','-Command',command],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode: self.skipTest('Native junction creation refused by environment')
        self.addCleanup(lambda: os.rmdir(str(path)) if path.exists() else None)
        self.assertTrue(path.lstat().st_file_attributes & 0x400)
    def unchanged(self):
        self.assertEqual([p.name for p in self.target.iterdir()],['sentinel.txt'])
        self.assertEqual((self.target/'sentinel.txt').read_text(),'unchanged')
    def test_native_news_root_junction_rejects_authoring_and_revision_before_write(self):
        self.junction(self.news)
        with self.assertRaises(ValueError): author.probe(self.news,self.day)
        with self.assertRaises(ValueError): revisions.lifecycle_path(self.news,self.day)
        self.unchanged()
    def test_native_collection_junction_rejects_candidate_and_capture_admission(self):
        self.junction(self.news/'_collection')
        with self.assertRaises(ValueError): author.target_path(self.news,self.day,'candidate')
        config={'sections':[{'items':[{'id':'N001','source_url':'https://example.org/article'}]}]}
        with self.assertRaises(ValueError): admit_candidates(config,self.day,news_root=self.news)
        self.unchanged()
    def layout(self):
        manifest={'pipeline_version':4,'date':self.day,'run_id':self.run,
                  'output_dir':str(self.news/self.day),'index_path':str(self.news/'_index/story_index.jsonl')}
        return pipeline.publication_layout(manifest,self.news/self.day/'.staging'/self.run,news_root=self.news)
    def test_native_staging_junction_rejects_publication_layout(self):
        self.junction(self.news/self.day/'.staging')
        with self.assertRaisesRegex(ValueError,'reparse'): self.layout()
        self.unchanged()
    def test_native_index_junction_rejects_publication_layout(self):
        self.junction(self.news/'_index')
        with self.assertRaisesRegex(ValueError,'reparse'): self.layout()
        self.unchanged()
    def test_native_internal_junction_rejected_even_without_path_escape(self):
        self.news.mkdir(); self.target=self.news/'internal-target'; self.target.mkdir()
        (self.target/'sentinel.txt').write_text('unchanged',encoding='utf-8')
        self.junction(self.news/'_collection')
        with self.assertRaisesRegex(ValueError,'reparse'): author.target_path(self.news,self.day,'candidate')
        self.unchanged()
