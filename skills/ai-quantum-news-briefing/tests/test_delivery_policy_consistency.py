import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from daily_delivery_policy import DEFAULT_RANKING_POLICY,resolve_delivery_defaults,policy_snapshot
from rank_briefing_candidates import merged_policy

class PolicyTests(unittest.TestCase):
    def test_formal_publication_bounds_preserved_and_shared(self):
        resolved=resolve_delivery_defaults({})
        self.assertEqual(resolved['social_delivery']['minimum_new_or_material_update'],4)
        for kind in ('academic','social'):
            for key,value in DEFAULT_RANKING_POLICY[kind].items():
                self.assertEqual(resolved[kind+'_delivery'][key],value)
                self.assertEqual(merged_policy({})[kind][key],value)

    def test_conflicting_copies_fail_instead_of_silent_override(self):
        with self.assertRaisesRegex(ValueError,'policy_conflict'):
            resolve_delivery_defaults({'social_delivery':{'minimum_new_or_material_update':4},'ranking_policy':{'social':{'minimum_new_or_material_update':7}}})

    def test_existing_stricter_config_is_preserved(self):
        r=resolve_delivery_defaults({'social_delivery':{'minimum_new_or_material_update':7,'minimum_items':7}})
        self.assertEqual(r['social_delivery']['minimum_new_or_material_update'],7)
        self.assertEqual(r['social_delivery']['minimum_items'],7)

    def test_snapshot_is_detached_and_stable(self):
        original=policy_snapshot();other=policy_snapshot();other['policy']['social']['minimum_items']=1
        self.assertEqual(original,policy_snapshot())

if __name__=='__main__':unittest.main()
