"""Independent road-event auditor; does not use solver evaluation or shortest paths."""
from math import isclose, inf


def check_result(d,r):
    if not __debug__:
        raise ValueError('Independent auditing requires Python without the -O optimization flag.')
    p=r.get('plan')
    assert p is not None, 'No plan to audit.'
    nodes={n['id']:n for n in d['nodes']}; roads={e['id']:e for e in d['roads']}; stops={s['id']:s for s in d['stops']}
    st=d['state']; cur=st['current']; historical={e['stop'] for e in st['history'] if e['kind']=='service'}
    services=[]; travel=0.; dwell=0.; raw=0.; reward=0.; moves=0
    emergency=cur==d['terminal'] and not (nodes[cur]['transit_safe'] and nodes[cur]['wait_safe'])
    reached=cur==d['terminal'] and not emergency
    filt=d.get('candidate_filter',{})
    for event in p['events']:
        if event['kind']=='move':
            assert not reached, 'Movement after arrival at absorbing terminal.'
            if event.get('terminal_escape'):
                assert emergency and moves==0 and not services, 'Invalid terminal emergency marker.'
            road=roads[event['road']]; a,b=event['from'],event['to']
            assert a==cur, 'Disconnected physical journey.'
            assert (a,b)==(road['from'],road['to']) or (not d['directed'] and (b,a)==(road['from'],road['to'])), 'Wrong direction.'
            assert road['current_time'] is not None and not road.get('closed',False) and road.get('safe',True), 'Forbidden road.'
            assert nodes[b]['transit_safe'], 'Entering unsafe node.'
            if not nodes[a]['transit_safe']:
                assert moves==0 and a==st['current'] and road.get('escape_verified',False), 'Unverified unsafe-origin escape.'
            assert isclose(event['minutes'],road['current_time'],abs_tol=1e-8), 'Wrong edge time.'
            travel+=road['current_time']; cur=b; moves+=1; reached=cur==d['terminal']
        elif event['kind']=='service':
            sid=event['stop']; s=stops[sid]
            assert s['node']==cur==event['node'], 'Phantom service.'
            assert sid not in services and sid not in historical, 'Repeated demand.'
            assert s['accessible'] and nodes[cur]['transit_safe'], 'Unsafe service.'
            assert sid in d['original_route'] or s.get('candidate',True), 'Ineligible stop universe.'
            if filt.get('allowed_stop_ids') is not None:
                assert sid in filt['allowed_stop_ids'], 'Explicit candidate filter violated.'
            # Independent Bellman-Ford corridor check (normal directed minutes).
            limit=filt.get('max_normal_minutes_from_original')
            if limit is not None:
                dist={v:inf for v in nodes}
                for name in d['original_route']: dist[stops[name]['node']]=0.
                for _ in range(len(nodes)-1):
                    for edge in d['roads']:
                        a,b,t=edge['from'],edge['to'],edge['normal_time']
                        dist[b]=min(dist[b],dist[a]+t)
                        if not d['directed']: dist[a]=min(dist[a],dist[b]+t)
                assert dist[cur]<=limit+1e-8, 'Corridor filter violated.'
            for key,val in [('minutes',s['dwell']),('demand',s['demand']),('score',s['demand']*s['priority'])]:
                assert isclose(event[key],val,abs_tol=1e-8), f'Wrong service {key}.'
            dwell+=s['dwell']; raw+=s['demand']; reward+=s['demand']*s['priority']; services.append(sid)
        else:
            raise AssertionError('Unknown planned event kind.')
    assert services==p['services'], 'Service list disagrees with execution.'
    if 'decisions' in p:
        dec=p['decisions']
        assert dec['u']=={s:int(s in services) for s in stops}, 'Service binary linkage incorrect.'
        eligible=set(d['endpoints']) | {st['current']}
        eligible={e for e in eligible if nodes[e]['transit_safe'] and nodes[e]['wait_safe']}
        assert dec['r']=={e:int(e==cur) for e in eligible}, 'Endpoint binary linkage incorrect.'
        assert dec['r_terminal']==int(reached), 'Terminal binary linkage incorrect.'
        vertices=[{'type':'root'}]+[{'type':'service','id':s} for s in services]+[{'type':'finish','id':cur}]
        assert dec['selected_x']==[{'from':a,'to':b,'x':1} for a,b in zip(vertices,vertices[1:])], 'Event path disconnected or cyclic.'
        assert dec['selected_service_order']=={s:i+1 for i,s in enumerate(services)}, 'Service order variables incorrect.'
    if 'legs' in p:
        road_events=[];rebuilt=[];leg_start=st['current'];leg_minutes=0.
        for event in p['events']:
            if event['kind']=='move':
                road_events.append({k:event[k] for k in ('road','from','to')});leg_minutes+=event['minutes']
            else:
                rebuilt.append({'from_node':leg_start,'to_node':event['node'],'minutes':leg_minutes,'road_arcs':road_events})
                leg_start=event['node'];road_events=[];leg_minutes=0.
        rebuilt.append({'from_node':leg_start,'to_node':cur,'minutes':leg_minutes,'road_arcs':road_events})
        assert len(rebuilt)==len(p['legs']), 'Connection leg count mismatch.'
        for a,b in zip(rebuilt,p['legs']):
            assert a['from_node']==b['from_node'] and a['to_node']==b['to_node'] and a['road_arcs']==b['road_arcs'], 'Road leg reconstruction mismatch.'
            assert isclose(a['minutes'],b['minutes'],abs_tol=1e-8), 'Connection time mismatch.'
    assert cur==p['endpoint'], 'Endpoint disagrees with physical route.'
    assert nodes[cur]['transit_safe'] and nodes[cur]['wait_safe'], 'Unsafe final location.'
    assert cur in d['endpoints'] or cur==st['current'], 'Endpoint not permitted.'
    assert reached==(cur==d['terminal'])==p['terminal_arrival'], 'Terminal linkage incorrect.'
    remaining=travel+dwell; total=st['elapsed']+remaining; par=d['parameters']
    late={k:max(0.,total-par['T_'+k]) for k in ['ref','soft','max']}
    penalties={k:late[k]*par['lambda_'+k] for k in late}; penalties['terminal']=0. if reached else par['kappa']
    metrics={'travel_minutes':travel,'dwell_minutes':dwell,'elapsed_minutes':st['elapsed'],
             'remaining_minutes':remaining,'total_minutes':total,'served_demand_proxy':raw,
             'weighted_service_score':reward,'penalty_total':sum(penalties.values()),'objective':reward-sum(penalties.values()),
             'history_demand_proxy':sum(e.get('demand',0) for e in st['history'] if e['kind']=='service'),
             'history_weighted_score':sum(e.get('score',0) for e in st['history'] if e['kind']=='service')}
    for key,value in metrics.items():
        assert isclose(p[key],value,rel_tol=1e-10,abs_tol=1e-8), f'{key} mismatch: {p[key]} vs {value}.'
    for key in late: assert isclose(p['lateness'][key],late[key],abs_tol=1e-8), 'Hinge mismatch.'
    for key in penalties: assert isclose(p['penalties'][key],penalties[key],abs_tol=1e-8), 'Penalty mismatch.'
    can_leave=False
    for e in d['roads']:
        pairs=[(e['from'],e['to'])]
        if not d['directed']: pairs.append((e['to'],e['from']))
        for a,b in pairs:
            if a==st['current'] and b!=a and nodes[b]['transit_safe'] and e['current_time'] is not None and not e.get('closed',False) and e.get('safe',True):
                if nodes[a]['transit_safe'] or e.get('escape_verified',False): can_leave=True
    if st['current']==d['terminal'] and not emergency: can_leave=False
    outcome=('reaches_terminal' if reached else 'terminates_elsewhere_safely' if moves else
             'stays_safely_by_choice' if can_leave else 'cannot_move_from_safe_location')
    assert p['operational_outcome']==outcome, 'Operational outcome mismatch.'
    return {'passed':True,'checks':['road identity and direction','physical connectivity','hard road and node safety',
            'verified unsafe-origin escape','explicit service and no repeated reward','candidate filters',
            'safe eligible finish','absorbing terminal and arrival linkage','travel dwell elapsed and total',
            'all three cumulative hinges','four separate penalties and objective','operational outcome']}
