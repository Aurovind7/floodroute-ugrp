"""Tiny-case independent oracle: Floyd-Warshall plus exhaustive permutations."""
from itertools import permutations
from math import inf


def enumerate_optimum(raw):
    # Validation is shared input hygiene; distances, candidate tests and arithmetic are separate.
    from .core import validate
    d=validate(raw); nodes={n['id']:n for n in d['nodes']}; stops={s['id']:s for s in d['stops']}
    if len(stops)>9: raise ValueError('Oracle limited to <=9 stops.')
    cur=d['state']['current']; term=d['terminal']; served={e['stop'] for e in d['state']['history'] if e['kind']=='service'}
    def floyd(normal):
        dist={(a,b):(0. if a==b else inf) for a in nodes for b in nodes}
        for edge in d['roads']:
            t=edge['normal_time'] if normal else edge['current_time']
            if t is None or (not normal and (edge['closed'] or not edge['safe'])):continue
            pairs=[(edge['from'],edge['to'])]
            if not d['directed']:pairs.append((edge['to'],edge['from']))
            for a,b in pairs:
                if not normal and (not nodes[a]['transit_safe'] or not nodes[b]['transit_safe'] or a==term):continue
                dist[a,b]=min(dist[a,b],t)
        for k in nodes:
            for a in nodes:
                for b in nodes:dist[a,b]=min(dist[a,b],dist[a,k]+dist[k,b])
        return dist
    normal=floyd(True); times=floyd(False)
    root={v:times[cur,v] for v in nodes}
    emergency=cur==term and not (nodes[cur]['transit_safe'] and nodes[cur]['wait_safe'])
    if not nodes[cur]['transit_safe'] or emergency:
        root={v:inf for v in nodes}; root[cur]=0.
        for e in d['roads']:
            if e['current_time'] is None or e['closed'] or not e['safe'] or (not nodes[cur]['transit_safe'] and not e['escape_verified']):continue
            pairs=[(e['from'],e['to'])]
            if not d['directed']:pairs.append((e['to'],e['from']))
            for a,b in pairs:
                if a==cur and nodes[b]['transit_safe']:
                    for v in nodes:root[v]=min(root[v],e['current_time']+times[b,v])
    endpoints=set(d['endpoints'])
    if nodes[cur]['transit_safe'] and nodes[cur]['wait_safe']:endpoints.add(cur)
    endpoints=sorted(e for e in endpoints if nodes[e]['transit_safe'] and nodes[e]['wait_safe'])
    filt=d['candidate_filter']; ids=[]
    for sid,s in sorted(stops.items()):
        if sid in served or (sid not in d['original_route'] and not s['candidate']):continue
        if filt.get('allowed_stop_ids') is not None and sid not in filt['allowed_stop_ids']:continue
        limit=filt.get('max_normal_minutes_from_original')
        if limit is not None and min(normal[stops[o]['node'],s['node']] for o in d['original_route'])>limit:continue
        if not s['accessible'] or not nodes[s['node']]['transit_safe'] or root[s['node']]==inf:continue
        if s['node']==term and term not in endpoints:continue
        if not any(times[s['node'],e]<inf for e in endpoints):continue
        ids.append(sid)
    best=None; count=0; p=d['parameters']
    for k in range(len(ids)+1):
        for seq in permutations(ids,k):
            time=0.; reward=0.; last=cur
            for j,sid in enumerate(seq):
                s=stops[sid]; time+=(root[s['node']] if j==0 else times[last,s['node']])+s['dwell']
                reward+=s['demand']*s['priority']; last=s['node']
            for e in endpoints:
                remaining=time+(times[last,e] if seq else root[e])
                if remaining==inf:continue
                count+=1; total=d['state']['elapsed']+remaining
                penalty=sum(p['lambda_'+name]*max(0.,total-p['T_'+name]) for name in ['ref','soft','max'])+p['kappa']*(e!=term)
                candidate={'objective':reward-penalty,'remaining_minutes':remaining,'services':list(seq),'endpoint':e}
                if best is None or candidate['objective']>best['objective']+1e-9 or (abs(candidate['objective']-best['objective'])<=1e-9 and
                   (remaining,list(seq),e)<(best['remaining_minutes'],best['services'],best['endpoint'])):best=candidate
    return {'plan':best,'feasible_plans':count,'candidates':ids,'times':times,'normal':normal,'root':root}
