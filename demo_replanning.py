"""Runnable three-stage meeting demonstration, with append-only history assertions."""
from copy import deepcopy
import json
from pathlib import Path
from floodroute import advance, solve
from make_examples import base


def run_demo():
    d=base(); stages=[]
    def record(label,data,result):
        assert result.get('verification',{}).get('passed')
        stages.append({'stage':label,'scenario':deepcopy(data),'result':result})
    r=solve(d);record('Normal plan before departure',d,r)
    count=next(i+1 for i,e in enumerate(r['plan']['events']) if e.get('stop')=='school_stop')
    first=advance(d,r,count);prefix=deepcopy(first['state']['history'])
    next(e for e in first['roads'] if e['id']=='main2')['closed']=True
    r=solve(first);record('First update after school: use detour',first,r)
    assert first['state']['history']==prefix
    assert 'school_stop' not in r['plan']['services']
    count=next(i+1 for i,e in enumerate(r['plan']['events']) if e.get('stop')=='hospital_stop')
    second=advance(first,r,count)
    next(e for e in second['roads'] if e['id']=='main3')['closed']=True
    next(n for n in second['nodes'] if n['id']=='hospital')['wait_safe']=False
    r=solve(second);record('Second update after hospital: finish at safe layby',second,r)
    assert second['state']['history'][:len(prefix)]==prefix
    assert r['plan']['history_demand_proxy']==22 and r['plan']['served_demand_proxy']==0
    assert r['plan']['endpoint']=='layby'
    final=advance(second,r,len(r['plan']['events']))
    assert final['state']['history'][:len(second['state']['history'])]==second['state']['history']
    return {'synthetic':True,'stages':stages,'final_state':final['state'],'history_preservation_passed':True}


if __name__=='__main__':
    demo=run_demo();path=Path(__file__).parent/'results/replanning_demo.json';path.write_text(json.dumps(demo,indent=2)+'\n')
    for stage in demo['stages']:
        p=stage['result']['plan'];print(stage['stage'])
        print('  current:',stage['scenario']['state']['current'],'elapsed:',p['elapsed_minutes'],'new services:',p['services'],'finish:',p['endpoint'])
    print('History remained fixed; demand was counted once. Saved results/replanning_demo.json')
