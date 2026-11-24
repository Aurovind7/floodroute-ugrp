"""Validated snapshot preprocessing and exact subset routing. Standard library only."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
from heapq import heappop, heappush
import json
from math import inf, isfinite
from time import perf_counter

EPS = 1e-9


class InputError(ValueError):
    pass


def number(x, name):
    try:
        valid=not isinstance(x,bool) and isinstance(x,(int,float)) and isfinite(x) and x>=0
    except OverflowError:
        valid=False
    if not valid:
        raise InputError(f'{name} must be finite and nonnegative.')
    return float(x)


def boolean(x, name):
    if type(x) is not bool:
        raise InputError(f'{name} must be true or false.')
    return x


def identifiers(values, name, universe):
    if not isinstance(values, list) or any(not isinstance(x, str) or x not in universe for x in values):
        raise InputError(f'{name} must list known IDs.')
    if len(set(values)) != len(values):
        raise InputError(f'{name} contains duplicate IDs.')
    return values


def fingerprint(data):
    return sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()


def unsafe_terminal_departure(d):
    """An unusable initial terminal is an emergency location, not a completed trip."""
    current=d['state']['current']
    n=next(n for n in d['nodes'] if n['id']==current)
    return current==d['terminal'] and not (n['transit_safe'] and n['wait_safe'])


def validate(raw):
    """Copy inputs; validate history with realized values, never today's road times."""
    if not isinstance(raw, dict):
        raise InputError('Scenario must be a JSON object.')
    d = deepcopy(raw)
    if d.get('schema_version') != 2:
        raise InputError('schema_version must be 2.')
    boolean(d.get('directed'), 'directed')
    for field in ('nodes', 'roads', 'stops'):
        if not isinstance(d.get(field), list):
            raise InputError(f'{field} must be an array.')
        ids = []
        for rec in d[field]:
            if not isinstance(rec, dict) or not isinstance(rec.get('id'), str) or not rec['id']:
                raise InputError(f'{field} records need nonempty string IDs.')
            ids.append(rec['id'])
        if len(set(ids)) != len(ids):
            raise InputError(f'Duplicate {field} ID.')
    nodes = {x['id']: x for x in d['nodes']}
    if not nodes:
        raise InputError('At least one node is required.')
    for n in nodes.values():
        for f in ('transit_safe', 'wait_safe'):
            boolean(n.get(f), f'{n["id"]}.{f}')
        if 'x' in n or 'y' in n:
            for f in ('x','y'):
                if isinstance(n.get(f), bool) or not isinstance(n.get(f), (int,float)) or not isfinite(n[f]):
                    raise InputError('Coordinates need finite x and y (negative allowed).')
    for e in d['roads']:
        if e.get('from') not in nodes or e.get('to') not in nodes:
            raise InputError(f'Unknown road node: {e["id"]}.')
        e['normal_time'] = number(e.get('normal_time'), 'normal_time')
        if 'current_time' not in e:
            raise InputError('Road current_time required; null means closed.')
        if e['current_time'] is not None:
            e['current_time'] = number(e['current_time'], 'current_time')
        for f, default in [('closed',False),('safe',True),('escape_verified',False)]:
            e[f] = boolean(e.get(f,default), f)
    stops = {s['id']: s for s in d['stops']}
    for s in stops.values():
        if s.get('node') not in nodes:
            raise InputError('Stop node must exist.')
        for f, default in [('demand',0),('priority',1),('dwell',0)]:
            s[f] = number(s.get(f,default), f)
        s['accessible'] = boolean(s.get('accessible',True), 'accessible')
        s['candidate'] = boolean(s.get('candidate',True), 'candidate')
    identifiers(d.get('original_route'), 'original_route', stops)
    if not d['original_route']:
        raise InputError('original_route must contain at least one stop.')
    if d.get('terminal') not in nodes:
        raise InputError('terminal must be a known road node ID.')
    if stops[d['original_route'][-1]]['node'] != d['terminal']:
        raise InputError('Last original stop must map to terminal.')
    identifiers(d.get('endpoints'), 'endpoints', nodes)
    d['theta'] = number(d.get('theta',1.5), 'theta')
    if d['theta'] < 1:
        raise InputError('theta must be >= 1.')
    p = d.get('parameters')
    if not isinstance(p,dict):
        raise InputError('parameters must be an object.')
    for f in ('T_ref','T_soft','T_max','lambda_ref','lambda_soft','lambda_max','kappa'):
        p[f] = number(p.get(f), f)
    if not p['T_ref'] <= p['T_soft'] <= p['T_max']:
        raise InputError('Require T_ref <= T_soft <= T_max.')
    filt = d.setdefault('candidate_filter', {})
    if not isinstance(filt,dict):
        raise InputError('candidate_filter must be an object.')
    if filt.get('allowed_stop_ids') is not None:
        identifiers(filt['allowed_stop_ids'], 'allowed_stop_ids', stops)
    if filt.get('max_normal_minutes_from_original') is not None:
        filt['max_normal_minutes_from_original'] = number(filt['max_normal_minutes_from_original'], 'corridor minutes')
    st = d.get('state')
    if not isinstance(st,dict) or st.get('origin') not in nodes or st.get('current') not in nodes:
        raise InputError('state needs known origin and current nodes.')
    st['elapsed'] = number(st.get('elapsed'), 'elapsed')
    if not isinstance(st.get('history'),list):
        raise InputError('state.history must be an array of realized events.')
    current, elapsed, served = st['origin'], 0.0, set()
    roads = {e['id']:e for e in d['roads']}
    terminal_reached = current == d['terminal']
    for event in st['history']:
        if not isinstance(event,dict):
            raise InputError('History events must be objects.')
        duration = number(event.get('minutes'), 'history minutes')
        kind = event.get('kind')
        if kind == 'move':
            if terminal_reached:
                if not (event.get('terminal_escape') is True and current==d['terminal']):
                    raise InputError('History cannot leave the absorbing terminal except a recorded initial emergency escape.')
            road = roads.get(event.get('road'))
            if road is None or event.get('from') != current:
                raise InputError('History move is disconnected or has unknown road.')
            a,b = event['from'],event.get('to')
            if (a,b) != (road['from'],road['to']) and (d['directed'] or (b,a) != (road['from'],road['to'])):
                raise InputError('History move violates road direction.')
            current = b
            terminal_reached = current == d['terminal']
        elif kind == 'service':
            s = stops.get(event.get('stop'))
            if s is None or s['node'] != current or s['id'] in served:
                raise InputError('History service disconnected, unknown, or duplicated.')
            if event.get('node') != current:
                raise InputError('History service node disagrees.')
            number(event.get('demand'), 'realized service demand')
            number(event.get('score'), 'realized service score')
            served.add(s['id'])
        elif kind == 'wait':
            if event.get('node') != current:
                raise InputError('History wait at wrong node.')
        else:
            raise InputError('History kind must be move, service or wait.')
        elapsed += duration
    if current != st['current'] or abs(elapsed-st['elapsed']) > 1e-8:
        raise InputError('History endpoint or sum of minutes disagrees with state.')
    # Reject finite inputs whose derived arithmetic would overflow, instead of emitting inf/NaN.
    try:
        bound=(sum(e['normal_time']+(e['current_time'] or 0) for e in d['roads'])*(len(stops)+1)
               +sum(s['dwell'] for s in stops.values())+st['elapsed'])
        points=sum(s['demand']*s['priority'] for s in stops.values())
        charges=bound*sum(p['lambda_'+k] for k in ('ref','soft','max'))+p['kappa']
        finite=all(isfinite(x) for x in (bound,points,charges,sum(e.get('score',0) for e in st['history'])))
    except OverflowError:
        finite=False
    if not finite:
        raise InputError('Derived time, score or penalty would overflow; rescale inputs.')
    return d


def road_arcs(d, normal=False):
    for e in d['roads']:
        time = e['normal_time'] if normal else e['current_time']
        if time is None or (not normal and (e['closed'] or not e['safe'])):
            continue
        yield e['from'], e['to'], time, e
        if not d['directed'] and e['from'] != e['to']:
            yield e['to'], e['from'], time, e


def shortest(d, source, normal=False, escape=False):
    """Dijkstra with explicit orientation, absorbing terminal and root-only escape."""
    nodes = {n['id']:n for n in d['nodes']}
    adj = {v:[] for v in nodes}
    for a,b,t,e in road_arcs(d, normal):
        if not normal:
            if not nodes[b]['transit_safe']:
                continue
            if not nodes[a]['transit_safe'] and not (escape and a == source and e['escape_verified']):
                continue
        adj[a].append((b,t,e['id']))
    dist, paths = {source:0.0}, {source:[]}
    queue = [(0.0,source)]
    while queue:
        time,a = heappop(queue)
        if time != dist[a]:
            continue
        if not normal and a == d['terminal'] and not (a==source and unsafe_terminal_departure(d)):
            continue
        for b,t,rid in sorted(adj[a]):
            new = time+t
            if new < dist.get(b,inf):
                dist[b] = new
                paths[b] = paths[a]+[{'road':rid,'from':a,'to':b}]
                heappush(queue,(new,b))
    return dist,paths


def prepare(raw):
    d = validate(raw)
    nodes = {n['id']:n for n in d['nodes']}
    stops = {s['id']:s for s in d['stops']}
    state = d['state']
    current = state['current']
    served = {e['stop'] for e in state['history'] if e['kind']=='service'}
    normal = {v:shortest(d,v,normal=True) for v in {current} | {s['node'] for s in stops.values()}}
    sources = {current} | {s['node'] for s in stops.values()}
    connections = {v:shortest(d,v,escape=(v==current and not nodes[v]['transit_safe'])) for v in sources}
    # Connections from an unsafe current node are used only for the root; service there is excluded.
    endpoints = sorted(set(d['endpoints']) | ({current} if nodes[current]['transit_safe'] and nodes[current]['wait_safe'] else set()))
    endpoint_report = [{'node':e,'eligible':bool(nodes[e]['transit_safe'] and nodes[e]['wait_safe']),
                        'reachable':e in connections[current][0]} for e in endpoints]
    endpoints = [e for e in endpoints if nodes[e]['transit_safe'] and nodes[e]['wait_safe']]
    original = set(d['original_route'])
    filt = d['candidate_filter']
    candidates, exclusions = [], []
    for sid,s in sorted(stops.items()):
        reasons = []
        if sid in served: reasons.append('already_served')
        if sid not in original and not s['candidate']: reasons.append('outside_eligible_universe')
        if filt.get('allowed_stop_ids') is not None and sid not in filt['allowed_stop_ids']: reasons.append('explicit_candidate_filter')
        limit = filt.get('max_normal_minutes_from_original')
        corridor = min((normal[stops[j]['node']][0].get(s['node'],inf) for j in original),default=inf)
        if limit is not None and corridor > limit: reasons.append('outside_normal_network_time_corridor')
        if not s['accessible']: reasons.append('stop_inaccessible')
        if not nodes[s['node']]['transit_safe']: reasons.append('node_unsafe_for_service')
        if s['node']==d['terminal'] and d['terminal'] not in endpoints: reasons.append('terminal_not_safe_finish')
        if s['node'] not in connections[current][0]: reasons.append('unreachable_from_current')
        if not any(e in connections[s['node']][0] for e in endpoints): reasons.append('no_safe_endpoint_after_service')
        if reasons: exclusions.append({'stop':sid,'reasons':reasons})
        else: candidates.append(sid)
    flags = []
    roads = {e['id']:e for e in d['roads']}
    for a,b in zip(d['original_route'],d['original_route'][1:]):
        v,w = stops[a]['node'],stops[b]['node']
        c0 = normal[v][0].get(w,inf)
        # Do not grant escape permission for a historical original-pair diagnostic.
        c1 = shortest(d,v)[0].get(w,inf)
        reasons=[]; ratio=None
        if not isfinite(c0): reasons.append('normal_unreachable')
        elif not isfinite(c1): reasons.append('current_unreachable')
        elif c0 == 0:
            if c1 == 0: ratio=1.0
            else: reasons.append('zero_normal_positive_current')
        else:
            ratio=c1/c0
            if ratio>d['theta']: reasons.append('ratio_above_theta')
        if any(roads[x['road']]['closed'] or not roads[x['road']]['safe'] or roads[x['road']]['current_time'] is None
               for x in normal[v][1].get(w,[])):
            reasons.append('closure_on_normal_reference_path')
        if not stops[b]['accessible']: reasons.append('stop_inaccessible')
        flags.append({'from_stop':a,'to_stop':b,'normal_minutes':c0 if isfinite(c0) else None,
                      'current_minutes':c1 if isfinite(c1) else None,'ratio':ratio,'reasons':reasons})
    can_leave = any(a==current and b!=current and nodes[b]['transit_safe'] and
                    (nodes[current]['transit_safe'] or e['escape_verified'])
                    for a,b,t,e in road_arcs(d)) and (current != d['terminal'] or unsafe_terminal_departure(d))
    return dict(data=d,nodes=nodes,stops=stops,candidates=candidates,endpoints=endpoints,
                connections=connections,normal=normal,exclusions=exclusions,flags=flags,
                endpoint_report=endpoint_report,can_leave=can_leave,served=served)


def evaluate(m, services, endpoint):
    """Build concrete event plan from a service sequence and final node."""
    d=m['data']; cur=d['state']['current']; events=[]; travel=0.0; dwell=0.0; legs=[]; selected=[]
    previous_event={'type':'root'}
    if len(set(services))!=len(services) or any(s not in m['candidates'] for s in services):
        raise ValueError('Invalid or duplicated new service.')
    for sid in list(services)+[None]:
        target = endpoint if sid is None else m['stops'][sid]['node']
        if sid is None and endpoint not in m['endpoints']:
            raise ValueError('Invalid endpoint.')
        times,paths=m['connections'][cur]
        if target not in times: raise ValueError('Unreachable connection.')
        target_event={'type':'finish','id':endpoint} if sid is None else {'type':'service','id':sid}
        selected.append({'from':previous_event,'to':target_event,'x':1})
        legs.append({'from_node':cur,'to_node':target,'minutes':times[target],'road_arcs':deepcopy(paths[target])})
        previous_event=target_event
        road_by_id={e['id']:e for e in d['roads']}
        for arc in paths[target]:
            dt=road_by_id[arc['road']]['current_time']
            event=dict(kind='move',**arc,minutes=dt)
            if not events and unsafe_terminal_departure(d):event['terminal_escape']=True
            events.append(event); travel+=dt
        cur=target
        if sid is not None:
            s=m['stops'][sid]; dwell+=s['dwell']
            events.append(dict(kind='service',stop=sid,node=cur,minutes=s['dwell'],demand=s['demand'],score=s['demand']*s['priority']))
    remaining=travel+dwell; total=d['state']['elapsed']+remaining; p=d['parameters']
    lateness={k:max(0.0,total-p['T_'+k]) for k in ('ref','soft','max')}
    penalties={k:p['lambda_'+k]*lateness[k] for k in lateness}
    reached=endpoint==d['terminal']; penalties['terminal']=p['kappa']*(not reached)
    score=sum(m['stops'][s]['demand']*m['stops'][s]['priority'] for s in services)
    raw=sum(m['stops'][s]['demand'] for s in services)
    moved=any(e['kind']=='move' for e in events)
    if reached: outcome='reaches_terminal'
    elif moved: outcome='terminates_elsewhere_safely'
    elif not m['can_leave']: outcome='cannot_move_from_safe_location'
    else: outcome='stays_safely_by_choice'
    return dict(services=list(services),endpoint=endpoint,events=events,legs=legs,
                decisions={'u':{s:int(s in services) for s in m['stops']},'r':{e:int(e==endpoint) for e in m['endpoints']},
                           'r_terminal':int(reached),'selected_x':selected,'selected_service_order':{s:i+1 for i,s in enumerate(services)}},
                travel_minutes=travel,dwell_minutes=dwell,
                elapsed_minutes=d['state']['elapsed'],remaining_minutes=remaining,total_minutes=total,
                lateness=lateness,penalties=penalties,penalty_total=sum(penalties.values()),
                served_demand_proxy=raw,weighted_service_score=score,objective=score-sum(penalties.values()),
                terminal_arrival=reached,operational_outcome=outcome,
                history_demand_proxy=sum(e.get('demand',0) for e in d['state']['history'] if e['kind']=='service'),
                history_weighted_score=sum(e.get('score',0) for e in d['state']['history'] if e['kind']=='service'))


def better(p,b):
    if b is None: return True
    if p['objective']>b['objective']+EPS: return True
    if abs(p['objective']-b['objective'])<=EPS:
        return (p['remaining_minutes'],p['services'],p['endpoint']) < (b['remaining_minutes'],b['services'],b['endpoint'])
    return False


def _solve(raw, time_limit=15.0, max_states=500000):
    """Exact subset DP. Only audited incumbents leave this API."""
    started=perf_counter()
    try:
        if not isinstance(max_states,int) or isinstance(max_states,bool) or max_states<1:
            raise InputError('max_states must be a positive integer.')
        number(time_limit,'time_limit')
        m=prepare(raw)
    except (InputError,TypeError,KeyError) as e:
        return {'solver_status':'invalid_input','message':str(e),'plan':None,'runtime_seconds':perf_counter()-started}
    d=m['data']; origin=d['state']['current']; ids=m['candidates']; best=None
    def endings(seq,last):
        nonlocal best
        for end in m['endpoints']:
            if end in m['connections'][last][0]:
                p=evaluate(m,seq,end)
                if better(p,best): best=p
    endings((),origin)
    if best is None:
        return dict(solver_status='physical_infeasible',plan=None,
                    operational_outcome='intervention_required' if not m['nodes'][origin]['transit_safe'] else 'no_verified_safe_action',
                    message='No verified path from current location to an eligible safe endpoint.',
                    candidates=ids,exclusions=m['exclusions'],flags=m['flags'],endpoints=m['endpoint_report'],
                    runtime_seconds=perf_counter()-started,optimality_gap=None)
    # Layers contain minimal remaining time and lexicographic witness for fixed (mask,last).
    layer={(0,-1):(0.0,())}; states=1; status='optimal'
    for size in range(len(ids)+1):
        next_layer={}
        for (mask,last),(elapsed,seq) in layer.items():
            node=origin if last==-1 else m['stops'][ids[last]]['node']
            endings(seq,node)
            if perf_counter()-started>=time_limit:
                status='feasible_time_limit'; break
            for j,sid in enumerate(ids):
                if mask & (1<<j): continue
                s=m['stops'][sid]; travel=m['connections'][node][0].get(s['node'])
                if travel is None: continue
                dt=elapsed+travel+s['dwell']; key=(mask|(1<<j),j); candidate=(dt,seq+(sid,))
                old=next_layer.get(key)
                if old is None:
                    if states>=max_states:
                        status='feasible_state_limit'; break
                    states+=1
                if old is None or candidate<old: next_layer[key]=candidate
            if status!='optimal': break
        if status!='optimal' or not next_layer: break
        layer=next_layer
    upper=sum(m['stops'][s]['demand']*m['stops'][s]['priority'] for s in ids)
    bound=best['objective'] if status=='optimal' else upper
    result=dict(solver_status=status,plan=best,candidates=ids,exclusions=m['exclusions'],flags=m['flags'],
                endpoints=m['endpoint_report'],terminal_reachable=d['terminal'] in m['connections'][origin][0],
                has_usable_outgoing=m['can_leave'],states=states,upper_bound=bound,
                absolute_gap=max(0.0,bound-best['objective']),
                optimality_gap=max(0.0,bound-best['objective'])/max(1.0,abs(best['objective'])),
                scenario_fingerprint=fingerprint(d),history_fingerprint=fingerprint(d['state']['history']),
                runtime_seconds=perf_counter()-started)
    from .check import check_result
    try:
        result['verification']=check_result(d,result)
    except (AssertionError,ValueError,KeyError) as e:
        return dict(solver_status='verification_failed',plan=None,message=str(e),runtime_seconds=perf_counter()-started)
    result['runtime_seconds']=perf_counter()-started
    return result


def solve(raw, time_limit=15.0, max_states=500000):
    """Keep unexpected search failures distinct from infeasibility and invalid data."""
    started=perf_counter()
    try:
        return _solve(raw,time_limit=time_limit,max_states=max_states)
    except Exception as error:
        return dict(solver_status='solver_failure',plan=None,message=f'{type(error).__name__}: {error}',
                    runtime_seconds=perf_counter()-started,optimality_gap=None)


def advance(raw,result,event_count):
    """Commit a verified prefix at event boundaries; never modify existing events."""
    d=validate(raw)
    if result.get('scenario_fingerprint')!=fingerprint(d):
        raise InputError('Result is stale for these inputs. Solve again before advancing.')
    from .check import check_result
    check_result(d,result)
    events=result['plan']['events']
    if not isinstance(event_count,int) or isinstance(event_count,bool) or not 0<=event_count<=len(events):
        raise InputError('event_count must select a valid event prefix.')
    prefix=deepcopy(events[:event_count]); st=d['state']
    for e in prefix:
        st['elapsed']+=e['minutes']
        st['current']=e['to'] if e['kind']=='move' else e['node']
    st['history'].extend(prefix)
    return validate(d)
