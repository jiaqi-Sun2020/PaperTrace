# -*- coding: utf-8 -*-
"""Actual lifecycle/preview entry points; synthetic reviews and mocked OSS only."""
from argparse import Namespace
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import publish_daily_to_oss as publisher
import daily_pipeline as dp
import test_publish_preview as fixtures
import test_rendered_search_evidence as discovery

CHECKS = ('responsive_reading', 'formula_links_keyboard', 'print_layout')


class PreviewDisplayPendingTests(unittest.TestCase):
    setUp = fixtures.PreviewTests.setUp
    call = fixtures.PreviewTests.call
    put = fixtures.PreviewTests.put
    rebind_fixture = fixtures.PreviewTests.rebind_fixture

    def pending(self):
        self.review_path = self.stage / f'opening_story_review_{self.day}.json'
        review = dp.load_json(self.review_path)
        third = next(r for r in review['rounds'] if r['id'] == 'cross-surface-and-display')
        third.update(judgment='pending', unresolved=[{'kind': 'actual_display_pending',
                                                     'reason': 'Exact preview must be observed in a permitted browser.'}],
                     cross_surface_checks={'judgment': 'pass', 'reason': 'Synthetic case, quantities and HTML agree.'},
                     display_review={'version': 1, 'status': 'pending', 'html_sha256': self.sha,
                                     'checks': [{'id': name, 'status': 'pending'} for name in CHECKS]})
        dp.atomic_json(self.review_path, review)
        self.report_path.unlink()
        self.rebind_fixture()
        return review, third

    def save(self, review):
        dp.atomic_json(self.review_path, review)
        self.rebind_fixture()

    def test_only_actual_display_pending_can_get_preview_without_sealing(self):
        self.pending()
        before = {p.name: p.read_bytes() for p in self.stage.iterdir() if p.is_file()}
        with patch.object(publisher, 'upload_preview_file', side_effect=self.put) as upload, \
                patch.object(publisher, 'upload_file') as formal:
            receipt = self.call()
            self.assertEqual(receipt['browser_display_status'], 'not_tested')
            self.assertFalse(receipt['formal_publish'])
            upload.assert_called_once(); formal.assert_not_called()
            self.assertEqual(self.call(), receipt)
        self.assertEqual({p.name: p.read_bytes() for p in self.stage.iterdir() if p.is_file()}, before)
        self.assertEqual((self.news / '_index/story_index.jsonl').read_bytes(), self.index_before)

    def test_first_two_rounds_and_news_claims_are_still_mandatory(self):
        review, third = self.pending()
        original = deepcopy(review)
        for round_id in ('story-completeness', 'semantic-and-source'):
            bad = deepcopy(original)
            next(r for r in bad['rounds'] if r['id'] == round_id)['judgment'] = 'pending'
            self.save(bad)
            with patch.object(publisher, 'upload_preview_file') as upload:
                with self.assertRaises(publisher.PublishError): self.call()
                upload.assert_not_called()
        self.save(original)
        news_path = self.stage / f'news_content_review_{self.day}.json'
        news = dp.load_json(news_path)
        news['items'][0]['claim_reviews']['facts']['verdict'] = 'fail'
        dp.atomic_json(news_path, news); self.rebind_fixture()
        with patch.object(publisher, 'upload_preview_file') as upload:
            with self.assertRaises(publisher.PublishError): self.call()
            upload.assert_not_called()

    def test_mixed_failed_unknown_or_stale_display_cannot_get_preview(self):
        review, _ = self.pending()
        for mutate in (
            lambda r: r['unresolved'].append({'kind': 'source_unknown', 'reason': 'Missing original source.'}),
            lambda r: r.update(judgment='fail'),
            lambda r: r['display_review'].update(version=2),
            lambda r: r['display_review'].update(html_sha256='a' * 64),
            lambda r: r['display_review']['checks'][0].update(status='fail'),
            lambda r: r['cross_surface_checks'].update(judgment='fail'),
            lambda r: r['example_alignment'].update(result='different promised quantity'),
        ):
            bad = deepcopy(review)
            mutate(next(r for r in bad['rounds'] if r['id'] == 'cross-surface-and-display'))
            self.save(bad)
            with patch.object(publisher, 'upload_preview_file') as upload:
                with self.assertRaises(publisher.PublishError): self.call()
                upload.assert_not_called()

    def test_formal_validation_seal_finalize_and_upload_refuse_pending(self):
        self.pending()
        self.assertTrue(publisher.validate_bundle(self.stage, self.manifest, require_manifest_binding=False,
                                                require_audit_report=False))
        self.assertTrue(publisher.validate_bundle(self.stage, self.manifest, require_manifest_binding=True,
                                                require_audit_report=False, preview_display_pending=True))
        self.assertTrue(publisher.validate_bundle(self.stage, self.manifest, require_manifest_binding=False,
                                                preview_display_pending=True))
        before = self.manifest_path.read_bytes()
        self.assertEqual(dp.cmd_seal_review(Namespace(run_dir=str(self.stage))), 1)
        self.assertFalse(self.report_path.exists())
        self.assertEqual(self.manifest_path.read_bytes(), before)
        with patch.object(publisher, 'auto_publish_after_finalize') as auto, \
                patch.object(publisher, 'upload_file') as upload:
            self.assertNotEqual(dp.cmd_finalize(Namespace(run_dir=str(self.stage), strict=True)), 0)
            auto.assert_not_called(); upload.assert_not_called()
        state_path, _ = publisher.locations(self.config_path)
        publisher.atomic_json(state_path, {'version': 1, 'enabled': True, 'deployment_id': publisher.deployment_id(self.config)})
        with patch.object(publisher, 'upload_file') as upload:
            try:
                result = publisher.publish(self.stage, self.config_path)
                self.assertNotEqual(result.get('status'), 'published')
            except publisher.PublishError:
                pass
            upload.assert_not_called()

    def test_changing_pending_to_pass_without_actual_evidence_is_not_completion(self):
        review, third = self.pending()
        third.update(judgment='pass', unresolved=[])
        self.save(review)
        self.assertTrue(publisher.validate_bundle(self.stage, self.manifest, require_manifest_binding=False,
                                                require_audit_report=False))
        third['display_review'].update(status='pass')
        for check in third['display_review']['checks']: check['status'] = 'pass'
        self.save(review)
        self.assertTrue(publisher.validate_bundle(self.stage, self.manifest, require_manifest_binding=False,
                                                require_audit_report=False))

    def test_completed_typed_display_can_follow_normal_formal_seal(self):
        review, third = self.pending()
        third.update(judgment='pass', unresolved=[])
        third['display_review']['status'] = 'pass'
        for check in third['display_review']['checks']:
            check.update(status='pass', evidence={'type': 'human_acceptance', 'reference': 'synthetic-fixture-only',
                                                 'environment': 'synthetic offline test',
                                                 'observed_at': '2026-07-10T08:00:00+08:00'})
        self.save(review)
        self.assertEqual(publisher.validate_bundle(self.stage, self.manifest, require_manifest_binding=False,
                                                 require_audit_report=False), [])
        self.assertEqual(dp.cmd_seal_review(Namespace(run_dir=str(self.stage))), 0)
        self.assertEqual(dp.verify_artifacts(self.stage, strict=True)['status'], 'pass')

    def test_rendered_discovery_flows_through_real_v4_staging_without_changing_captures(self):
        fixture = fixtures.v4fixtures.V4PublicationTests()
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        fixture.prepare()
        row = fixture.raw['coverage_evidence'][0]
        social = row['social_search']
        social['source_class_evidence'] = [social['source_class_evidence'][0]] + [
            discovery.fixture(kind, empty=(kind == 'official_company_social')) for kind in discovery.TARGETS]
        row['social_search_ref'] = discovery.coverage.evidence_digest(social)
        fixture.write_candidate()
        capture_files = list((fixture.news / '_collection').rglob('*.json'))
        before = {str(p): p.read_bytes() for p in capture_files}
        stage, _, manifest = fixture.stage()
        self.assertEqual(dp.verify_artifacts(stage, strict=True, structure_only=True)['status'], 'pass')
        self.assertEqual({str(p): p.read_bytes() for p in capture_files}, before)
        self.assertEqual(manifest['required_story_review_protocol'], 3)
        self.assertEqual(dp.verify_artifacts(stage, strict=True)['status'], 'fail')

    def test_formally_completed_run_cannot_reuse_pending_or_stale_display(self):
        review, third = self.pending()
        third.update(judgment='pass', unresolved=[])
        third['display_review']['status'] = 'pass'
        for check in third['display_review']['checks']:
            check.update(status='pass', evidence={'type': 'actual_browser', 'reference': 'synthetic-fixture-only',
                                                 'environment': 'synthetic offline test',
                                                 'observed_at': '2026-07-10T08:00:00+08:00'})
        self.save(review)
        self.assertEqual(dp.cmd_seal_review(Namespace(run_dir=str(self.stage))), 0)
        with patch.object(publisher, 'auto_publish_after_finalize', return_value={'status': 'disabled'}):
            self.assertEqual(dp.cmd_finalize(Namespace(run_dir=str(self.stage), strict=True,
                                                      require_remote=False)), 0)
        final = self.news / self.day
        final_manifest_path = final / self.manifest_path.name
        final_manifest = dp.load_json(final_manifest_path)
        review_path = final / self.review_path.name
        for stale_hash in (self.sha, 'f' * 64):
            bad = deepcopy(review)
            row = next(r for r in bad['rounds'] if r['id'] == 'cross-surface-and-display')
            if stale_hash == self.sha:
                row.update(judgment='pending', unresolved=[{'kind': 'actual_display_pending', 'reason': 'not observed'}])
                row['display_review']['status'] = 'pending'
                row['display_review']['checks'] = [{'id': name, 'status': 'pending'} for name in CHECKS]
            else:
                row['display_review']['html_sha256'] = stale_hash
            dp.atomic_json(review_path, bad)
            report = final / self.report_path.name
            dp.atomic_json(report, dp.make_report(final, final_manifest))
            final_manifest['artifact_sha256']['story_review'] = dp.sha256_file(review_path)
            final_manifest['artifact_sha256']['release_audit'] = dp.sha256_file(report)
            dp.atomic_json(final_manifest_path, final_manifest)
            self.assertEqual(dp.verify_artifacts(final, strict=True)['status'], 'fail')
            state_path, _ = publisher.locations(self.config_path)
            publisher.atomic_json(state_path, {'version': 1, 'enabled': True, 'deployment_id': publisher.deployment_id(self.config)})
            with patch.object(publisher, 'upload_file') as upload:
                with self.assertRaises(publisher.PublishError): publisher.publish(final, self.config_path)
                upload.assert_not_called()

    def test_malformed_or_historical_pending_review_is_not_preview_eligible(self):
        review, _ = self.pending()
        for mutate in (lambda r: r.update(rounds=None), lambda r: r.update(review_protocol_version=2),
                       lambda r: r.update(review_protocol_version=3.0)):
            bad = deepcopy(review); mutate(bad); self.save(bad)
            with patch.object(publisher, 'upload_preview_file') as upload:
                with self.assertRaises(publisher.PublishError): self.call()
                upload.assert_not_called()


if __name__ == '__main__':
    unittest.main()
