import json
import random
import unittest
from unittest.mock import patch
from copy import deepcopy
from pathlib import Path
from floodroute import InputError, advance, check_result, prepare, solve, validate
from floodroute.baselines import baselines
from floodroute.oracle import enumerate_optimum
from make_examples import base, scenarios


class PrototypeTests(unittest.TestCase):
    def assert_matches_oracle(self,d):
        r=solve(d,time_limit=60)
        self.assertNotIn(r['solver_status'],['invalid_input','verification_failed'])
        o=enumerate_optimum(d)
        self.assertEqual(r['plan'] is None,o['plan'] is None)
        if r['plan']:
            self.assertEqual(r['solver_status'],'optimal')
            for name in ['objective','remaining_minutes']:
                self.assertAlmostEqual(r['plan'][name],o['plan'][name],places=7)
            check_result(validate(d),r)
        return r,o

    def test_01_packaged_examples(self):
        for path in sorted((Path(__file__).parents[1]/'examples').glob('*.json')):
            with self.subTest(path=path.name):self.assert_matches_oracle(json.loads(path.read_text()))

    def test_02_supervisor_static_revision(self):
        ds=scenarios()
        r,_=self.assert_matches_oracle(ds['15_latest_written_regression'])
        self.assertAlmostEqual(r['plan']['objective'],181)
        self.assertAlmostEqual(r['plan']['total_minutes'],39)
        r=solve(ds['04_unsafe_priority']);self.assertNotIn('hospital_stop',r['plan']['services'])
        r=solve(ds['05_terminal_alternative']);self.assertFalse(r['plan']['terminal_arrival']);self.assertEqual(r['plan']['endpoint'],'layby')
        r=solve(ds['06_overtime']);self.assertGreater(r['plan']['total_minutes'],ds['06_overtime']['parameters']['T_max'])
        self.assertGreater(r['plan']['penalties']['max'],0)
        self.assertEqual(solve(ds['08_safe_stranded'])['plan']['operational_outcome'],'cannot_move_from_safe_location')
        self.assertEqual(solve(ds['09_unsafe_no_escape'])['operational_outcome'],'intervention_required')
        self.assertEqual(solve(ds['11_unsafe_verified_escape'])['plan']['terminal_arrival'],True)

    def test_03_hand_calculations_and_sensitivity(self):
        ds=scenarios()
        self.assertEqual(solve(ds['12_hand_check'])['plan']['objective'],0)
        self.assertEqual(solve(ds['13_priority_change'])['plan']['objective'],5)
        self.assertEqual(solve(ds['14_penalty_change'])['plan']['objective'],2.5)
        d=ds['12_hand_check'];d['parameters']['kappa']=0
        self.assertEqual(solve(d)['plan']['endpoint'],'origin')
        self.assertEqual(solve(d)['plan']['operational_outcome'],'stays_safely_by_choice')

    def test_04_two_updates_preserve_history(self):
        d=base();r=solve(d)
        count=next(i+1 for i,e in enumerate(r['plan']['events']) if e.get('stop')=='school_stop')
        first=advance(d,r,count);locked=deepcopy(first['state']['history']);elapsed=first['state']['elapsed']
        next(e for e in first['roads'] if e['id']=='main2')['closed']=True
        second_plan=solve(first)
        self.assertNotIn('school_stop',second_plan['plan']['services'])
        self.assertTrue(any(e.get('road')=='detour1' for e in second_plan['plan']['events']))
        self.assertEqual(first['state']['history'],locked)
        count=next(i+1 for i,e in enumerate(second_plan['plan']['events']) if e.get('stop')=='hospital_stop')
        second=advance(first,second_plan,count)
        self.assertEqual(second['state']['history'][:len(locked)],locked)
        self.assertGreater(second['state']['elapsed'],elapsed)
        next(e for e in second['roads'] if e['id']=='main3')['closed']=True
        next(n for n in second['nodes'] if n['id']=='hospital')['wait_safe']=False
        third_plan=solve(second)
        self.assertEqual(third_plan['plan']['endpoint'],'layby')
        self.assertEqual(third_plan['plan']['served_demand_proxy'],0)
        self.assertEqual(third_plan['plan']['history_demand_proxy'],22)
        end=advance(second,third_plan,len(third_plan['plan']['events']))
        self.assertEqual(len([e for e in end['state']['history'] if e.get('stop')=='school_stop']),1)
        self.assertEqual(len([e for e in end['state']['history'] if e.get('stop')=='hospital_stop']),1)
        # Realized rewards and elapsed time survive edited present-day priorities/dwell/closures.
        for s in end['stops']:s.update(priority=99,dwell=20)
        self.assertEqual(solve(end)['plan']['history_demand_proxy'],22)
        with self.assertRaises(InputError):advance(end,third_plan,0)

    def test_05_history_validation_and_stale_results(self):
        d=base();r=solve(d);modified=deepcopy(d);modified['parameters']['kappa']+=1
        with self.assertRaises(InputError):advance(modified,r,1)
        with self.assertRaises(InputError):advance(d,r,-1)
        after=advance(d,r,len(r['plan']['events']))
        self.assertEqual(solve(after)['plan']['served_demand_proxy'],0)
        for mutation in ('duplicate_service','elapsed','current','bad_direction'):
            bad=deepcopy(after)
            if mutation=='duplicate_service':bad['state']['history'].append(next(e for e in bad['state']['history'] if e['kind']=='service'))
            elif mutation=='elapsed':bad['state']['elapsed']+=1
            elif mutation=='current':bad['state']['current']='depot'
            else:bad['state']['history'][0]['from']='terminal'
            self.assertEqual(solve(bad)['solver_status'],'invalid_input')

    def test_06_seeded_random_networks(self):
        rng=random.Random(20261124)
        for case in range(60):
            with self.subTest(case=case):
                d=base();d['directed']=bool(case%2)
                d['stops']=d['stops'][:4]
                d['roads']=[]
                for a in d['nodes']:
                    for b in d['nodes']:
                        if a['id']!=b['id'] and rng.random()<.24:
                            d['roads'].append({'id':f'e{len(d["roads"])}','from':a['id'],'to':b['id'],
                                'normal_time':rng.randint(0,7),'current_time':rng.choice([None,0,1,3,8]),'closed':False,'safe':True,'escape_verified':bool(case%3==0)})
                for s in d['stops']:
                    s.update(demand=rng.randint(0,12),priority=rng.choice([0,.5,1,3]),dwell=rng.randint(0,3),accessible=rng.random()>.15)
                if case%5==0: d['nodes'][0].update(transit_safe=False,wait_safe=False)
                if case%7==0: d['nodes'][2].update(transit_safe=False,wait_safe=False)
                if case%4==0:d['parameters'].update(lambda_ref=0,lambda_soft=0,lambda_max=0)
                r,o=self.assert_matches_oracle(d);m=prepare(d)
                for src,(dist,_) in m['normal'].items():
                    for target in m['nodes']:
                        self.assertEqual(dist.get(target,float('inf')),o['normal'][src,target])
                for src,(dist,_) in m['connections'].items():
                    reference=o['root'] if src==d['state']['current'] else {v:o['times'][src,v] for v in m['nodes']}
                    for target in m['nodes']:self.assertEqual(dist.get(target,float('inf')),reference[target])

    def test_07_candidate_filters_and_disconnection(self):
        d=base();d['candidate_filter']={'allowed_stop_ids':['hospital_stop']}
        r,_=self.assert_matches_oracle(d)
        self.assertEqual(r['candidates'],['hospital_stop'])
        d=base();d['candidate_filter']={'max_normal_minutes_from_original':0}
        r,_=self.assert_matches_oracle(d)
        self.assertIn({'stop':'market_stop','reasons':['outside_normal_network_time_corridor']},r['exclusions'])
        d=base();d['roads']=[e for e in d['roads'] if e['to']!='market']
        r,_=self.assert_matches_oracle(d)
        self.assertTrue(any(x['stop']=='market_stop' and 'unreachable_from_current' in x['reasons'] for x in r['exclusions']))
        # A stop without boarding access need not close the road through it.
        d=scenarios()['04_unsafe_priority'];r=solve(d)
        self.assertTrue(any(e.get('to')=='hospital' for e in r['plan']['events']))

    def test_08_zero_normal_and_theta_never_suppresses_closure(self):
        d=base();d['theta']=100000
        d['roads'][1].update(closed=True,normal_time=0)
        r,_=self.assert_matches_oracle(d)
        self.assertTrue(any('closure_on_normal_reference_path' in x['reasons'] for x in r['flags']))
        self.assertFalse(any(e.get('road')=='main2' for e in r['plan']['events']))
        d['roads'][1].update(closed=False,current_time=0)
        self.assert_matches_oracle(d)
        # unreachable normal pair is diagnostic rather than division or invalidity
        d['roads']=[e for e in d['roads'] if e['to']!='terminal'];self.assert_matches_oracle(d)

    def test_09_directed_parallel_colocated_and_repeated_nodes(self):
        d=scenarios()['10_directed'];m=prepare(d)
        self.assertNotIn('school',m['connections']['hospital'][0])
        self.assertIn('hospital',m['connections']['school'][0])
        d=base();d['directed']=False
        extra=deepcopy(d['roads'][0]);extra.update(id='parallel',current_time=.5);d['roads'].append(extra)
        d['stops'].append({'id':'second_school','node':'school','demand':4,'priority':1,'dwell':0,'accessible':True,'candidate':True})
        r,_=self.assert_matches_oracle(d)
        self.assertIn('second_school',r['plan']['services'])
        self.assertTrue(any(e.get('road')=='parallel' for e in r['plan']['events']))
        # Return through the same junction is explicitly permitted on physical roads.
        d=base();d['directed']=False
        d['parameters'].update(lambda_ref=0,lambda_soft=0,lambda_max=0)
        r,_=self.assert_matches_oracle(d)
        self.assertIn('market_stop',r['plan']['services'])
        walk=[d['state']['current']]+[e['to'] for e in r['plan']['events'] if e['kind']=='move']
        self.assertGreater(len(walk),len(set(walk)))

    def test_10_limit_statuses_and_checker_rejects_tampering(self):
        d=base()
        for kwargs,status in [({'time_limit':0},'feasible_time_limit'),({'max_states':1},'feasible_state_limit')]:
            r=solve(d,**kwargs);self.assertEqual(r['solver_status'],status)
            self.assertTrue(r['verification']['passed']);self.assertGreaterEqual(r['upper_bound'],r['plan']['objective'])
            self.assertGreaterEqual(r['optimality_gap'],0)
        r=solve(d)
        for field in ('objective','travel_minutes','dwell_minutes','served_demand_proxy','penalty_total'):
            corrupt=deepcopy(r);corrupt['plan'][field]+=1
            with self.assertRaises(AssertionError):check_result(validate(d),corrupt)
        corrupt=deepcopy(r);corrupt['plan']['events'][0]['to']='layby'
        with self.assertRaises(AssertionError):check_result(validate(d),corrupt)
        corrupt=deepcopy(r);corrupt['plan']['decisions']['u']['market_stop']=1
        with self.assertRaises(AssertionError):check_result(validate(d),corrupt)
        corrupt=deepcopy(r);corrupt['plan']['decisions']['selected_x'].append({'from':{'type':'service','id':'market_stop'},'to':{'type':'service','id':'market_stop'},'x':1})
        with self.assertRaises(AssertionError):check_result(validate(d),corrupt)

    def test_11_invalid_inputs(self):
        for mutation in ('negative','nan','bad_id','duplicate','bool_time','bad_threshold','bad_current','missing_current_time','bad_bool','bad_history','unknown_stop'):
            d=base()
            if mutation=='negative':d['roads'][0]['current_time']=-1
            elif mutation=='nan':d['stops'][0]['priority']=float('nan')
            elif mutation=='bad_id':d['roads'][0]['to']='unknown'
            elif mutation=='duplicate':d['stops'].append(deepcopy(d['stops'][0]))
            elif mutation=='bool_time':d['roads'][0]['normal_time']=True
            elif mutation=='bad_threshold':d['parameters']['T_max']=1
            elif mutation=='bad_current':d['state']['current']='unknown'
            elif mutation=='missing_current_time':del d['roads'][0]['current_time']
            elif mutation=='bad_bool':d['nodes'][0]['transit_safe']='yes'
            elif mutation=='bad_history':d['state']['elapsed']=1
            else:d['original_route'].append('unknown')
            self.assertEqual(solve(d)['solver_status'],'invalid_input',mutation)

    def test_12_baselines_and_no_safe_wait(self):
        d=scenarios()['03_detour'];b=baselines(d)
        self.assertEqual(b['fixed_normal_road_reference']['status'],'infeasible')
        self.assertEqual(b['shortest_terminal']['status'],'feasible')
        d=scenarios()['09_unsafe_no_escape'];b=baselines(d)
        self.assertEqual(b['shortest_safe_endpoint']['status'],'infeasible')
        d=scenarios()['08_safe_stranded'];next(n for n in d['nodes'] if n['id']=='depot')['wait_safe']=False
        r=solve(d);self.assertEqual(r['solver_status'],'physical_infeasible');self.assertEqual(r['operational_outcome'],'no_verified_safe_action')

    def test_13_unsafe_initial_terminal_can_escape(self):
        d=base();d['state']['origin']=d['state']['current']='terminal'
        next(n for n in d['nodes'] if n['id']=='terminal').update(transit_safe=False,wait_safe=False)
        d['roads'].append({'id':'terminal_escape','from':'terminal','to':'layby','normal_time':1,'current_time':1,'escape_verified':True})
        r,_=self.assert_matches_oracle(d)
        self.assertEqual(r['plan']['endpoint'],'layby')
        self.assertFalse(r['plan']['terminal_arrival'])
        after=advance(d,r,len(r['plan']['events']))
        self.assertEqual(after['state']['current'],'layby')

    def test_14_failure_and_overflow_are_not_routes(self):
        d=base();d['stops'][1].update(demand=1e308,priority=1e308)
        self.assertEqual(solve(d)['solver_status'],'invalid_input')
        with patch('floodroute.core.shortest',side_effect=RuntimeError('injected search failure')):
            r=solve(base());self.assertEqual(r['solver_status'],'solver_failure');self.assertIsNone(r['plan'])
        with patch('floodroute.check.check_result',side_effect=AssertionError('injected audit failure')):
            r=solve(base());self.assertEqual(r['solver_status'],'verification_failed');self.assertIsNone(r['plan'])


if __name__=='__main__':unittest.main(verbosity=2)
