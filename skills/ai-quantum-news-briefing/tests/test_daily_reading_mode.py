"""Offline reading/feedback contracts; no browser or semantic approval claims."""
import copy
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from test_daily_pipeline import config, normalize_briefing_config, apply_design_system
import briefing_to_feedback_html as renderer
import orchestrate_daily as orchestration
from daily_pipeline import cmd_run, verify_artifacts
from test_release_protocol import daily_evidence


class DailyReadingModeTests(unittest.TestCase):
    def page(self, enabled=False, theme='light'):
        raw = config()
        raw['feedback_enabled'] = enabled
        normalized = normalize_briefing_config(raw, require_source_url=True)
        return normalized, apply_design_system(renderer.render_html(normalized), 'cosmic', theme)

    def test_default_has_no_feedback_dom_runtime_or_dead_buttons(self):
        raw = normalize_briefing_config(config(), require_source_url=True)
        page = renderer.render_html(raw)
        self.assertIn('data-feedback-enabled="false"', page)
        for marker in ('id="feedbackPanel"', 'id="annotateBtn"', 'id="newsSelectionToolbar"',
                       'PaperTraceFeedbackUX', 'localStorage', 'createAutosave', 'Download JSON',
                       'data-mark-strip=', '<button class="concept-chip"', 'selectionchange'):
            self.assertNotIn(marker, page)
        self.assertIn('class="concept-label"', page)
        self.assertNotIn('initial_feedback_items', json.loads(re.search(
            r'<script id="briefing-data" type="application/json">(.*?)</script>', page, re.S).group(1)))

    def test_explicit_enable_retains_full_feedback_contract(self):
        raw, page = self.page(True)
        self.assertTrue(raw['feedback_enabled'])
        for marker in ('data-feedback-enabled="true"', 'id="feedbackPanel"',
                       'id="newsSelectionToolbar"', 'createAutosave', 'localStorage', 'Download JSON'):
            self.assertIn(marker, page)
        self.assertEqual(renderer.feedback_surface_failures(page, True), [])

    def test_mode_is_boolean_and_normalization_retains_it(self):
        for value in ('false', 'true', 0, 1, None, {}, []):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'feedback_enabled'):
                normalize_briefing_config({**config(), 'feedback_enabled': value})
        self.assertFalse(normalize_briefing_config(config())['feedback_enabled'])

    def test_disabled_render_does_not_mutate_historical_feedback_input(self):
        raw = normalize_briefing_config(config())
        raw['initial_feedback_items'] = [{'feedback_id':'old','note':'KEEP ORIGINAL'}]
        before = copy.deepcopy(raw)
        page = renderer.render_html(raw)
        self.assertEqual(raw, before)
        self.assertEqual(renderer.render_html(raw), page)
        self.assertNotIn('KEEP ORIGINAL', page)
        self.assertNotIn('removeItem(', page)
        self.assertNotIn('clear()', page)

    def test_mode_toggle_preserves_historical_feedback_fingerprint(self):
        off=normalize_briefing_config({**config(),'feedback_enabled':False})
        on=normalize_briefing_config({**config(),'feedback_enabled':True})
        self.assertEqual(off['config_fingerprint'],on['config_fingerprint'])
        import hashlib
        legacy={k:v for k,v in off.items() if k not in ('feedback_enabled','config_fingerprint','run_fingerprint','generated_at')}
        expected=hashlib.sha256(json.dumps(legacy,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(off['config_fingerprint'],expected)

    def test_body_sources_formulas_themes_and_print_survive_both_modes(self):
        for enabled in (False, True):
            for theme in ('light','cosmic'):
                with self.subTest(enabled=enabled, theme=theme):
                    raw, page = self.page(enabled, theme)
                    for marker in ('data-briefing-body="true"','data-opening-story="true"',
                                   'data-story-example="true"','data-formula="true"',
                                   'id="MathJax-script"', '@media print',
                                   'data-lean-bg-option="light"','data-lean-bg-option="cosmic"'):
                        self.assertIn(marker, page)
                    for section in raw['sections']:
                        for item in section['items']:
                            self.assertIn('id="'+item['id']+'"', page)
                            self.assertIn('href="'+item['source_url']+'"', page)
                    self.assertEqual(renderer.feedback_surface_failures(page, enabled), [])

    def test_reading_gate_rejects_residual_panel_listener_and_mode_mismatch(self):
        _, page = self.page(False)
        for injected in ('<aside id="feedbackPanel"></aside>',
                         '<script>localStorage.getItem("papertrace-news:old")</script>',
                         '<script>document.addEventListener("selectionchange", f)</script>',
                         '<button class="concept-chip" data-concept="old">old</button>'):
            with self.subTest(injected=injected):
                self.assertTrue(renderer.feedback_surface_failures(page.replace('</body>',injected+'</body>'), False))
        self.assertTrue(renderer.feedback_surface_failures(page, True))

    def test_enabled_gate_does_not_accept_missing_feedback_runtime(self):
        _, page = self.page(True)
        self.assertTrue(renderer.feedback_surface_failures(page.replace('createAutosave','removed'), True))

    def test_cli_enable_is_explicit_and_default_is_reading(self):
        self.assertFalse(renderer.parse_args(['--config','fixture.json']).enable_feedback)
        self.assertTrue(renderer.parse_args(['--config','fixture.json','--enable-feedback']).enable_feedback)

    def test_pipeline_modes_bind_manifest_and_feedback_na_to_html(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); raw=config(); raw['feedback_enabled']=enabled
                raw['date_range']='2026-07-09'
                raw['collection_completed_at']='2026-07-10T08:00:00+08:00'
                raw['coverage_evidence']=[daily_evidence('2026-07-09')]
                raw['academic_search']=raw['coverage_evidence'][0]['academic_search']
                source=root/'candidate.json'; source.write_text(json.dumps(raw), encoding='utf-8')
                output=root/'news/2026-07-10'
                args=Namespace(config=str(source), output_dir=str(output), index=str(root/'index.jsonl'),
                               date='2026-07-10', days=7, continuing_mode='one-line',
                               design_system='cosmic', background_mode='light', release_protocol=2,
                               coverage_start=None, coverage_end=None)
                self.assertEqual(cmd_run(args), 0)
                run=next((output/'.staging').iterdir())
                manifest=json.loads((run/'daily_pipeline_manifest_2026-07-10.json').read_text())
                self.assertEqual(manifest['feedback_mode_version'],1)
                self.assertIs(manifest['feedback_enabled'],enabled)
                result=verify_artifacts(run, strict=True, structure_only=True)
                self.assertEqual(result['status'],'pass',result)
                scope=result['feedback_acceptance']
                self.assertEqual(scope['status'],'required' if enabled else 'not_applicable')
                self.assertEqual(scope['html_sha256'],manifest['artifact_sha256']['html'])
                self.assertIn('config_sha256',scope)
                # Structural success cannot approve content or strict publication.
                strict=verify_artifacts(run, strict=True)
                self.assertEqual(strict['status'],'fail')
                self.assertEqual(strict['feedback_acceptance']['status'],
                                 'required' if enabled else 'not_applicable')

    def test_unknown_manifest_mode_is_rejected(self):
        _, page=self.page(False)
        for value in (None, 'false', 0):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError,'feedback_enabled'):
                renderer.feedback_surface_failures(page,value)


class StoryPrintStateTests(unittest.TestCase):
    """Execute the print-state runtime against a synthetic DOM, not a browser."""
    def runtime(self, enabled=False):
        raw = normalize_briefing_config({**config(), 'feedback_enabled': enabled})
        page = renderer.render_html(raw)
        match = re.search(r'<script id="papertrace-story-print">(.*?)</script>', page, re.S)
        self.assertIsNotNone(match, 'Collapsed worked example has no print expansion/restoration contract')
        return match.group(1)

    def execute(self, initial, events, enabled=False):
        node = shutil.which('node')
        if node is None:
            self.skipTest('Node unavailable: synthetic print-state execution untested')
        program = r'''
const vm=require('node:vm');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const elements=input.initial.map(open=>({open}));
const listeners={};
const context={window:{addEventListener:(event,fn)=>{listeners[event]=fn}},
  document:{querySelectorAll:selector=>{
    if(selector!=='details[data-story-example="true"]') throw Error('Unbounded selector');
    return elements;
  }}};
vm.runInNewContext(input.runtime,context);
const states=[];
for(const event of input.events){listeners[event]();states.push(elements.map(x=>x.open));}
console.log(JSON.stringify({states,listeners:Object.keys(listeners)}));
'''
        result = subprocess.run([node, '-e', program], input=json.dumps({
            'runtime':self.runtime(enabled), 'initial':initial, 'events':events}),
            text=True, capture_output=True, timeout=10, check=True)
        return json.loads(result.stdout)

    def test_closed_example_prints_open_and_returns_closed(self):
        result=self.execute([False],['beforeprint','afterprint'])
        self.assertEqual(result['states'],[[True],[False]])

    def test_open_example_and_repeated_print_preserve_original_states(self):
        result=self.execute([False,True],['beforeprint','beforeprint','afterprint','afterprint',
                                          'beforeprint','afterprint'])
        self.assertEqual(result['states'],[[True,True],[True,True],[False,True],[False,True],
                                          [True,True],[False,True]])

    def test_print_hook_has_no_feedback_storage_and_is_mode_independent(self):
        for enabled in (False,True):
            with self.subTest(enabled=enabled):
                runtime=self.runtime(enabled)
                self.assertNotIn('localStorage',runtime)
                self.assertNotIn('PaperTraceFeedback',runtime)
                result=self.execute([False],['beforeprint','afterprint'],enabled)
                self.assertEqual(result['listeners'],['beforeprint','afterprint'])

    def test_no_worked_example_and_spurious_afterprint_are_safe(self):
        result=self.execute([],['afterprint','beforeprint','beforeprint','afterprint'])
        self.assertEqual(result['states'],[[],[],[],[]])


class QueueWithdrawalTests(unittest.TestCase):
    def test_withdraw_retains_history_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            news=Path(tmp); queue=news/'_automation/workflow_queue.json'
            queue.parent.mkdir(); queue.write_text(json.dumps({'version':1,'dates':['2026-10-10','2026-10-11']}))
            old=queue.read_bytes()
            with patch.object(orchestration,'NEWS_ROOT',news), patch.object(orchestration,'inspect',
                    side_effect=lambda day: {'date':day,'phase':'review_pending','action_required':True,'next_action':'review'}):
                state=orchestration.workflow_queue('2026-10-10',record=True,withdraw_reason='User cancelled backlog')
                after=queue.read_bytes()
                state=orchestration.workflow_queue('2026-10-11',record=True)
                self.assertNotIn('2026-10-10',state['execution_order'])
                self.assertIn('2026-10-11',state['execution_order'])
                self.assertIn('2026-10-10',json.loads(after)['dates'])
                orchestration.workflow_queue('2026-10-10',record=True,withdraw_reason='User cancelled backlog')
                self.assertEqual(queue.read_bytes(),after)
                self.assertNotEqual(after,old)

    def test_withdraw_requires_record_and_concrete_reason(self):
        for reason in ('', '   '):
            with self.assertRaises(ValueError): orchestration.workflow_queue('2026-10-10',record=True,withdraw_reason=reason)
        with self.assertRaises(ValueError): orchestration.workflow_queue('2026-10-10',withdraw_reason='cancelled')

    def test_unknown_or_conflicting_withdrawal_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            news=Path(tmp); queue=news/'_automation/workflow_queue.json'; queue.parent.mkdir()
            queue.write_text(json.dumps({'version':1,'dates':['2026-10-10'],'withdrawals':{'2026-10-10':None}}))
            before=queue.read_bytes()
            with patch.object(orchestration,'NEWS_ROOT',news), self.assertRaises(ValueError):
                orchestration.workflow_queue('2026-10-10',record=True,withdraw_reason='cancelled')
            self.assertEqual(queue.read_bytes(),before)

    def test_cancelled_date_is_not_inspected_or_implicitly_requeued(self):
        with tempfile.TemporaryDirectory() as tmp:
            news=Path(tmp)
            with patch.object(orchestration,'NEWS_ROOT',news), patch.object(orchestration,'inspect') as inspect:
                orchestration.workflow_queue('2026-10-10',record=True,withdraw_reason='No backfill')
                state=orchestration.workflow_queue('2026-10-10',record=True)
                inspect.assert_not_called()
                self.assertEqual(state['execution_order'],[])
                self.assertEqual(state['dates'][0]['phase'],'withdrawn')


if __name__=='__main__': unittest.main()
