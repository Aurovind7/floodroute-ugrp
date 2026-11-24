"""Programmatic entry point: python run_scenario.py examples/03_detour.json --output result.json"""
import argparse
import json
from pathlib import Path
from floodroute import solve
from floodroute.baselines import baselines

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Solve a flood-routing JSON scenario; standard library only.')
    parser.add_argument('scenario',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--time-limit',type=float,default=15);parser.add_argument('--max-states',type=int,default=500000)
    args=parser.parse_args()
    try:data=json.loads(args.scenario.read_text())
    except (OSError,ValueError) as e:parser.exit(2,f'Cannot load scenario: {e}\n')
    result=solve(data,time_limit=args.time_limit,max_states=args.max_states)
    if result['solver_status'] in ('optimal','feasible_time_limit','feasible_state_limit','physical_infeasible'):
        result['baselines']=baselines(data)
    text=json.dumps(result,indent=2,allow_nan=False)
    if args.output:args.output.write_text(text+'\n')
    p=result.get('plan')
    print(result['solver_status'])
    if p:
        print(p['operational_outcome'], 'endpoint:',p['endpoint'])
        print('New service:',p['services'],'objective:',p['objective'],'full-trip minutes:',p['total_minutes'])
        print('Road event audit:',result['verification']['passed'])
    else:print(result.get('message',''))
    if result['solver_status'] in ('invalid_input','verification_failed','solver_failure'):raise SystemExit(2)
