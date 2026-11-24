"""Interaction tests using Streamlit's real app execution/session engine."""
import json
from pathlib import Path
from copy import deepcopy
import unittest
import logging
from streamlit.testing.v1 import AppTest
from floodroute import validate

ROOT=Path(__file__).parents[1]
logging.getLogger('streamlit.runtime.scriptrunner_utils.script_run_context').setLevel(logging.ERROR)


def button(at,label):return next(b for b in at.button if b.label==label)
def number(at,label):return next(n for n in at.number_input if n.label==label)


class InterfaceTests(unittest.TestCase):
    def start(self):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
        self.assertEqual(len(at.exception),0)
        return at

    def test_run_compare_advance_update_export_reset(self):
        at=self.start();button(at,'Run routing model').click().run()
        self.assertEqual(len(at.exception),0)
        r=at.session_state.result;self.assertEqual(r['solver_status'],'optimal')
        self.assertTrue(r['verification']['passed'])
        button(at,'Save this result for comparison').click().run()
        self.assertEqual(len(at.session_state.comparisons),1)
        count=next(i+1 for i,e in enumerate(r['plan']['events']) if e.get('stop')=='school_stop')
        number(at,'Number of planned events to execute').set_value(count).run()
        button(at,'Advance bus and lock these events').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state.scenario['state']['current'],'school')
        history=at.session_state.scenario['state']['history']
        # Inject a snapshot through the same persisted scenario API; table editor is a browser widget.
        d=at.session_state.scenario
        next(e for e in d['roads'] if e['id']=='main2')['closed']=True
        at.session_state.scenario=d
        at.run();button(at,'Run routing model').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertNotIn('school_stop',at.session_state.result['plan']['services'])
        self.assertEqual(at.session_state.scenario['state']['history'],history)
        self.assertTrue(any(e.get('road')=='detour1' for e in at.session_state.result['plan']['events']))
        button(at,'Reset journey and edits').click().run()
        self.assertEqual(at.session_state.scenario['state']['history'],[])
        self.assertEqual(at.session_state.scenario['state']['current'],'depot')

    def test_apply_penalty_and_all_saved_scenarios(self):
        at=self.start()
        number(at,'kappa').set_value(5)
        button(at,'Apply inputs').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state.scenario['parameters']['kappa'],5)
        for path in sorted((ROOT/'examples').glob('*.json')):
            at.session_state.scenario=validate(json.loads(path.read_text()))
            at.session_state.result=None;at.session_state.revision+=1
            at.run();button(at,'Run routing model').click().run()
            self.assertEqual(len(at.exception),0,path.name)
            self.assertIn(at.session_state.result['solver_status'],['optimal','physical_infeasible'])

    def test_load_example_invalid_form_and_limit(self):
        at=self.start()
        choice=next(s for s in at.selectbox if s.label=='Built-in synthetic example')
        selected=ROOT/'examples/09_unsafe_no_escape.json'
        choice.set_value(selected);button(at,'Load example').click().run()
        self.assertIn('unsafe origin',at.session_state.scenario['name'])
        button(at,'Run routing model').click().run()
        self.assertEqual(at.session_state.result['operational_outcome'],'intervention_required')
        choice=next(s for s in at.selectbox if s.label=='Built-in synthetic example');choice.set_value(ROOT/'examples/01_normal.json')
        button(at,'Load example').click().run()
        number(at,'T_max').set_value(1);button(at,'Apply inputs').click().run()
        self.assertEqual(len(at.exception),0);self.assertTrue(any('not applied' in e.value for e in at.error))
        self.assertEqual(at.session_state.scenario['parameters']['T_max'],12)
        number(at,'Time limit (seconds)').set_value(0);button(at,'Run routing model').click().run()
        self.assertEqual(len(at.exception),0);self.assertEqual(at.session_state.result['solver_status'],'feasible_time_limit')

    def test_old_result_migration_preserves_completed_journey(self):
        at=self.start();button(at,'Run routing model').click().run()
        result=at.session_state.result
        count=next(i+1 for i,e in enumerate(result['plan']['events']) if e.get('stop')=='school_stop')
        number(at,'Number of planned events to execute').set_value(count).run()
        button(at,'Advance bus and lock these events').click().run()
        button(at,'Run routing model').click().run()
        state_before=deepcopy(at.session_state.scenario['state'])
        legacy=deepcopy(at.session_state.result)
        legacy['plan'].pop('decisions');legacy['plan'].pop('legs')
        at.session_state.result=legacy
        at.run()
        self.assertEqual(len(at.exception),0)
        self.assertIsNone(at.session_state.result)
        self.assertEqual(at.session_state.scenario['state'],state_before)
        self.assertTrue(any('older format' in x.value for x in at.info))
        button(at,'Run routing model').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertTrue(at.session_state.result['verification']['passed'])
        self.assertNotIn('school_stop',at.session_state.result['plan']['services'])


if __name__=='__main__':unittest.main(verbosity=2)
