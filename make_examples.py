"""Recreate all synthetic fixtures; no external data or reference writes."""
from copy import deepcopy
from pathlib import Path
import json
from floodroute import advance, solve

HERE=Path(__file__).parent

def base():
    nodes=[{'id':v,'transit_safe':True,'wait_safe':v!='junction','x':x,'y':y}
           for v,x,y in [('depot',0,0),('school',2,0),('hospital',4,0),('terminal',6,0),('junction',3,1),('market',2,-1),('layby',5,1)]]
    stops=[{'id':sid,'node':node,'demand':dem,'priority':1,'dwell':dw,'accessible':True,'candidate':True}
           for sid,node,dem,dw in [('start','depot',0,0),('school_stop','school',12,1),('hospital_stop','hospital',10,1),('end','terminal',0,0),('market_stop','market',5,1)]]
    roads=[{'id':rid,'from':a,'to':b,'normal_time':t,'current_time':t,'closed':False,'safe':True,'escape_verified':False}
           for rid,a,b,t in [('main1','depot','school',2),('main2','school','hospital',2),('main3','hospital','terminal',2),
                            ('detour1','school','junction',2),('detour2','junction','hospital',2),('alternative1','depot','market',2),
                            ('alternative2','market','hospital',3),('safe_exit','hospital','layby',1)]]
    return {'schema_version':2,'name':'Synthetic normal operation','synthetic':True,'directed':True,'nodes':nodes,'stops':stops,'roads':roads,
            'original_route':['start','school_stop','hospital_stop','end'],'terminal':'terminal','endpoints':['terminal','layby'],
            'candidate_filter':{},'theta':1.5,'parameters':{'T_ref':8,'T_soft':10,'T_max':12,'lambda_ref':1,'lambda_soft':2,'lambda_max':4,'kappa':20},
            'state':{'origin':'depot','current':'depot','elapsed':0,'history':[]}}


def scenarios():
    cases={};d=base();cases['01_normal']=d
    d=deepcopy(d);d['name']='Synthetic slower roads without closures'
    for e in d['roads']:e['current_time']*=1.5
    cases['02_slow']=d
    d=base();d['name']='Synthetic blocked original segment with detour'
    next(e for e in d['roads'] if e['id']=='main2')['closed']=True
    cases['03_detour']=d
    d=base();d['name']='Synthetic high priority but unsafe hospital stop'
    s=next(s for s in d['stops'] if s['id']=='hospital_stop');s.update(accessible=False,priority=100)
    cases['04_unsafe_priority']=d
    d=base();d['name']='Synthetic terminal unavailable for safe finish'
    next(n for n in d['nodes'] if n['id']=='terminal').update(transit_safe=False,wait_safe=False)
    next(s for s in d['stops'] if s['id']=='end')['accessible']=False
    cases['05_terminal_alternative']=d
    d=base();d['name']='Synthetic overtime preferred to abandoning service'
    d['parameters'].update(T_ref=2,T_soft=3,T_max=4,lambda_ref=0.1,lambda_soft=0.2,lambda_max=0.3,kappa=100)
    cases['06_overtime']=d
    initial=base();r=solve(initial)
    # Advance through the second service event with positive demand, before terminal.
    n=next(i+1 for i,e in enumerate(r['plan']['events']) if e['kind']=='service' and e['stop']=='hospital_stop')
    d=advance(initial,r,n);d['name']='Synthetic mid trip after school and hospital'
    next(e for e in d['roads'] if e['id']=='main3')['closed']=True
    next(n for n in d['nodes'] if n['id']=='hospital')['wait_safe']=False
    cases['07_midtrip']=d
    d=base();d['name']='Synthetic safe origin without usable outgoing road'
    for e in d['roads']:
        if e['from']=='depot':e['closed']=True
    cases['08_safe_stranded']=d
    d=deepcopy(d);d['name']='Synthetic unsafe origin without verified escape'
    next(n for n in d['nodes'] if n['id']=='depot').update(transit_safe=False,wait_safe=False)
    cases['09_unsafe_no_escape']=d
    d=base();d['name']='Synthetic asymmetric directed reachability'
    d['state']['origin']=d['state']['current']='hospital'
    cases['10_directed']=d
    d=base();d['name']='Synthetic unsafe origin with certified escape'
    next(n for n in d['nodes'] if n['id']=='depot').update(transit_safe=False,wait_safe=False)
    next(e for e in d['roads'] if e['id']=='main1')['escape_verified']=True
    cases['11_unsafe_verified_escape']=d
    # Hand-checkable optional hospital detour, direct finish, or safe stay.
    d={'schema_version':2,'name':'Synthetic hand check hospital detour','synthetic':True,'directed':True,
       'nodes':[{'id':v,'transit_safe':True,'wait_safe':True,'x':x,'y':y} for v,x,y in [('origin',0,0),('clinic',1,1),('finish',2,0)]],
       'roads':[{'id':rid,'from':a,'to':b,'normal_time':t0,'current_time':t1,'closed':False,'safe':True,'escape_verified':False}
                for rid,a,b,t0,t1 in [('direct','origin','finish',4,4),('out','origin','clinic',1.5,4),('back','clinic','finish',1.5,4)]],
       'stops':[{'id':sid,'node':node,'demand':dem,'priority':1,'dwell':dw,'accessible':True,'candidate':True}
                for sid,node,dem,dw in [('origin_stop','origin',0,0),('clinic_stop','clinic',5,1),('finish_stop','finish',0,0)]],
       'original_route':['origin_stop','clinic_stop','finish_stop'],'terminal':'finish','endpoints':['finish'],
       'theta':1.5,'parameters':{'T_ref':4,'T_soft':10,'T_max':12,'lambda_ref':2,'lambda_soft':0,'lambda_max':0,'kappa':6},
       'candidate_filter':{},'state':{'origin':'origin','current':'origin','elapsed':0,'history':[]}}
    cases['12_hand_check']=d
    d=deepcopy(d);d['name']='Synthetic hand check with higher clinic priority';d['stops'][1]['priority']=3
    cases['13_priority_change']=d
    d=deepcopy(cases['12_hand_check']);d['name']='Synthetic hand check with lower time charge';d['parameters']['lambda_ref']=0.5
    cases['14_penalty_change']=d
    # Latest written eight-stop case, preserving its synthetic road table.
    d=base();d['name']='Synthetic regression of 26 October eight stop example'
    d['nodes']=[{'id':v,'transit_safe':True,'wait_safe':True} for v in 'ABCDEFGHXYZW']
    d['stops']=[{'id':v,'node':v,'demand':dem,'priority':1,'dwell':0 if v in 'AH' else 1,'accessible':True,'candidate':True} for v,dem in zip('ABCDEFGH',[0,25,40,20,100,50,30,0])]
    d['roads']=[{'id':f'road_{i}','from':a,'to':b,'normal_time':t0,'current_time':t1,'closed':False,'safe':True,'escape_verified':False}
                for i,(a,b,t0,t1) in enumerate([('A','B',4,4),('B','C',3,6),('C','D',2.5,5),('D','E',6,12),('E','F',6,12),('F','G',3,6),('G','H',4,4),('A','X',2,2),('X','C',3,3),('B','Y',3,3),('Y','D',4,4),('C','E',8,14),('D','Z',3,3),('Z','F',3,3),('F','W',2,2),('W','H',3,3)])]
    d.update(original_route=list('ABCDEFGH'),terminal='H',endpoints=list('ABCDEFGH'),parameters={'T_ref':34.5,'T_soft':39,'T_max':43,'lambda_ref':2,'lambda_soft':4,'lambda_max':8,'kappa':100},state={'origin':'A','current':'A','elapsed':0,'history':[]})
    cases['15_latest_written_regression']=d
    return cases


if __name__=='__main__':
    for name,d in scenarios().items():
        (HERE/'examples'/f'{name}.json').write_text(json.dumps(d,indent=2)+'\n')
    (HERE/'scenario_template.json').write_text(json.dumps(base(),indent=2)+'\n')
    print('Wrote 15 synthetic scenarios and template.')
