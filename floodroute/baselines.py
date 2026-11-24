"""Clearly named baselines. Original-order baseline allows safe rerouting between stops."""
from .core import evaluate, prepare


def baselines(raw):
    m=prepare(raw); d=m['data']; root=d['state']['current']; stops=m['stops']; term=d['terminal']
    output={}
    route=d['original_route']; historical=[e['stop'] for e in d['state']['history'] if e['kind']=='service' and e['stop'] in route]
    # Resume after furthest original service already completed; never rewrite actual prefix.
    index=max((route.index(s) for s in historical),default=-1)
    sequence=[s for s in route[index+1:] if s not in m['served']]
    try:
        if any(s not in m['candidates'] for s in sequence):raise ValueError('A remaining original stop is inaccessible, unreachable or filtered out.')
        output['original_order_all_remaining_service']=dict(status='feasible',plan=evaluate(m,sequence,term),
            definition='Remaining original stops in original order; shortest current safe connections; actual history fixed.')
    except ValueError as e:
        output['original_order_all_remaining_service']={'status':'infeasible','reason':str(e)}
    for name,ends in [('shortest_terminal',[term]),('shortest_safe_endpoint',m['endpoints'])]:
        possible=[(m['connections'][root][0][e],e) for e in ends if e in m['endpoints'] and e in m['connections'][root][0]]
        if possible:
            _,end=min(possible); output[name]={'status':'feasible','plan':evaluate(m,[],end),
                'definition':'Shortest road path without new stop service; safe waiting at current can be zero.'}
        else: output[name]={'status':'infeasible','reason':'No reachable permitted endpoint for this baseline.'}
    # A separate strict physical reference retains normal pair paths, detecting closed segments.
    prev=root; events=[]; reason=None; time=0.
    for sid in sequence:
        target=stops[sid]['node']
        if prev not in m['normal']:
            reason='Current position has no stored normal reference connection.';break
        path=m['normal'][prev][1].get(target)
        if path is None:reason='Normal reference connection is unreachable.';break
        byid={e['id']:e for e in d['roads']}
        for arc in path:
            road=byid[arc['road']]
            if (road['current_time'] is None or road['closed'] or not road['safe'] or not m['nodes'][arc['to']]['transit_safe']
                or (not m['nodes'][arc['from']]['transit_safe'] and not (not events and arc['from']==root and road['escape_verified']))
                or arc['from']==term):
                reason='A road on the normal reference path is blocked or unsafe.';break
            events.append(arc);time+=road['current_time']
        if reason:break
        if not stops[sid]['accessible'] or not m['nodes'][target]['transit_safe']:
            reason='Original service stop is inaccessible or unsafe.';break
        time+=stops[sid]['dwell'];prev=target
    if reason or term not in m['endpoints'] or prev!=term:
        output['fixed_normal_road_reference']={'status':'infeasible','reason':reason or 'Terminal is not a permitted reachable finish.'}
    else:
        output['fixed_normal_road_reference']={'status':'feasible','remaining_minutes':time,'road_arcs':events,
                                              'definition':'Normal shortest paths between remaining original stops, evaluated on current roads.'}
    return output
