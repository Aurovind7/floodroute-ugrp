"""UI data preparation and session compatibility; no routing decisions live here."""
from .core import fingerprint, validate

RESULT_VIEW_VERSION = 2
REQUIRED_PLAN_FIELDS = {'events','services','endpoint','travel_minutes','dwell_minutes',
    'elapsed_minutes','remaining_minutes','total_minutes','lateness','penalties','objective',
    'served_demand_proxy','weighted_service_score','history_demand_proxy','history_weighted_score',
    'terminal_arrival','operational_outcome','decisions','legs'}

OUTCOMES = {
    'reaches_terminal':'Reach the original terminal',
    'terminates_elsewhere_safely':'Finish at a safe alternative',
    'stays_safely_by_choice':'Wait safely at the current location',
    'cannot_move_from_safe_location':'Stay safely · no usable outgoing road',
    'intervention_required':'Intervention required',
    'no_verified_safe_action':'No verified safe completion',
}


def result_problem(scenario, result):
    """Invalidate old/incompatible results, preserving all scenario and history data."""
    if result is None:
        return None
    if not isinstance(result,dict) or 'solver_status' not in result or 'runtime_seconds' not in result:
        return 'The previous result uses an older format. Run the model again; completed history is preserved.'
    plan=result.get('plan')
    if plan is not None:
        if not isinstance(plan,dict) or not REQUIRED_PLAN_FIELDS.issubset(plan):
            return 'The previous result uses an older format. Run the model again; completed history is preserved.'
        if result.get('scenario_fingerprint') != fingerprint(validate(scenario)):
            return 'The inputs have changed. Run the model again; completed history is preserved.'
    return None


def event_rows(events):
    rows=[]
    for i,e in enumerate(events,1):
        move=e['kind']=='move';service=e['kind']=='service'
        rows.append({'Step':i,'Action':e['kind'].capitalize(),
                     'From / stop':e['from'] if move else e.get('stop',e.get('node','')),
                     'To / location':e['to'] if move else e.get('node',''),
                     'Minutes':e['minutes'],'Demand proxy':e.get('demand') if service else None,
                     'Service score':e.get('score') if service else None})
    return rows


def penalty_rows(plan):
    labels={'ref':'Reference extension','soft':'Additional soft-threshold charge',
            'max':'Additional overtime charge','terminal':'Terminal non-arrival'}
    return [{'Penalty':labels[k],'Excess minutes':f"{plan['lateness'][k]:g}" if k in plan['lateness'] else '—',
             'Points':float(v)} for k,v in plan['penalties'].items()]
