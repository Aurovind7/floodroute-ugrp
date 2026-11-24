"""Local and Community Cloud UI. The independently checked routing core is separate."""
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from floodroute import InputError, advance, solve, validate
from floodroute.baselines import baselines
from floodroute.diagram import network_svg
from floodroute.presentation import OUTCOMES, event_rows, penalty_rows, result_problem

ROOT=Path(__file__).parent
st.set_page_config(page_title='FloodRoute · UGRP routing lab',page_icon='🚌',layout='wide')
st.markdown('''<style>
:root {color-scheme:light;}
.stApp {background:#f4f7fa;color:#132c43;}
[data-testid="stHeader"] {background:rgba(244,247,250,.95);}
[data-testid="stSidebar"] {background:#eaf0f5;border-right:1px solid #d8e2ec;}
[data-testid="stSidebar"] h2 {font-size:1.05rem;letter-spacing:.01em;}
.block-container {max-width:1500px;padding-top:2.25rem;padding-bottom:3rem;}
h1,h2,h3 {color:#132c43;letter-spacing:-.025em;}
h1 {font-size:2.7rem !important;font-weight:750 !important;line-height:1.1 !important;}
h3 {font-size:1.2rem !important;}
p {line-height:1.55;}
[data-testid="stMetric"] {background:white;border:1px solid #dce5ed;border-radius:14px;padding:16px 18px;}
[data-testid="stMetricLabel"] {color:#60758b;font-size:.83rem;}
[data-testid="stMetricValue"] {color:#15394c;font-weight:700;font-size:1.9rem;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:14px;}
[data-testid="stTabs"] [role="tablist"] {gap:12px;border-bottom:1px solid #d9e3ec;padding-bottom:3px;}
[data-testid="stTabs"] [role="tab"] {padding:10px 6px;font-weight:600;color:#5a7186;}
[data-testid="stTabs"] [aria-selected="true"] {color:#087f8c;}
.stButton button,.stDownloadButton button {border-radius:9px;font-weight:600;}
.lab-eyebrow {color:#087f8c;font-size:.72rem;font-weight:800;letter-spacing:.17em;margin-bottom:10px;}
.lab-subtitle {color:#60758b;font-size:1rem;margin:10px 0 19px;max-width:850px;}
.context-line {display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 22px;}
.context-line span {background:#fff;border:1px solid #dce5ed;border-radius:7px;padding:6px 11px;font-size:.8rem;color:#405c73;}
.action-title {font-size:1.25rem;font-weight:700;color:#15394c;line-height:1.35;margin:8px 0;}
.status-pill {display:inline-block;border-radius:20px;background:#e2f3ee;color:#186955;padding:5px 10px;font-size:.75rem;font-weight:700;}
.empty-hint {color:#60758b;font-size:.92rem;line-height:1.6;}
@media(max-width:700px){.block-container{padding-top:1.4rem;}h1{font-size:2rem!important;}[data-testid="stMetricValue"]{font-size:1.5rem;}}
</style>''',unsafe_allow_html=True)


def set_scenario(data,reset=True):
    for field,bound in [('nodes',1000),('roads',5000),('stops',50)]:
        if isinstance(data,dict) and isinstance(data.get(field),list) and len(data[field])>bound:
            raise InputError(f'The interactive app supports at most {bound} {field}. Use the programmatic solver for larger inputs.')
    validated=validate(data)
    st.session_state.scenario=validated
    if reset:st.session_state.initial=deepcopy(validated)
    st.session_state.result=None
    st.session_state.revision=st.session_state.get('revision',0)+1


def show_events(events):
    if events:
        st.dataframe(pd.DataFrame(event_rows(events)),hide_index=True,width='stretch',
                     column_config={'Minutes':st.column_config.NumberColumn(format='%.2f'),
                                    'Demand proxy':st.column_config.NumberColumn(format='%.2f'),
                                    'Service score':st.column_config.NumberColumn(format='%.2f')})
    else:
        st.caption('No events. A safe zero-movement plan can have an empty event list.')


if 'scenario' not in st.session_state:
    set_scenario(json.loads((ROOT/'examples/01_normal.json').read_text()))
st.session_state.setdefault('initial',deepcopy(st.session_state.scenario))
st.session_state.setdefault('comparisons',[])
st.session_state.setdefault('revision',1)
st.session_state.setdefault('result',None)
problem=result_problem(st.session_state.scenario,st.session_state.result)
if problem:
    st.session_state.result=None
    st.session_state['compatibility_notice']=problem

with st.sidebar:
    st.markdown('### 🚌 FloodRoute')
    st.caption('ONE BUS · ONE SNAPSHOT')
    st.divider()
    st.header('Scenario library')
    files=sorted((ROOT/'examples').glob('*.json'))
    def example_name(path):
        data=json.loads(path.read_text())
        return path.stem[:2]+' · '+data.get('name',path.stem).removeprefix('Synthetic ').capitalize()
    choice=st.selectbox('Built-in synthetic example',files,format_func=example_name)
    if st.button('Load example',width='stretch'):
        set_scenario(json.loads(choice.read_text()));st.rerun()
    with st.expander('Upload your own scenario'):
        upload=st.file_uploader('Upload scenario JSON',type=['json'])
        if st.button('Load uploaded scenario',disabled=upload is None,width='stretch'):
            try:set_scenario(json.loads(upload.getvalue()));st.rerun()
            except (ValueError,TypeError,KeyError) as e:st.error(f'Invalid scenario: {e}')
        st.download_button('Download input template',(ROOT/'scenario_template.json').read_text(),file_name='scenario_template.json',width='stretch')
    st.divider()
    with st.expander('Search limits'):
        limit=st.number_input('Time limit (seconds)',min_value=0.,max_value=60.,value=15.,step=1.)
        states=st.number_input('Maximum generated states',min_value=1,max_value=500000,value=200000,step=1000)
        st.caption('A limited search returns an audited feasible incumbent, with a conservative bound.')
    run=st.button('Run routing model',type='primary',width='stretch')
    st.caption('Apply input edits before running.')
    if st.button('Reset journey and edits',width='stretch'):
        set_scenario(deepcopy(st.session_state.initial));st.rerun()
    st.divider()
    st.caption('UGRP with Dr Anmol Pahwa\n\nSynthetic research prototype · Snapshot replanning')

scenario=st.session_state.scenario;rev=st.session_state.revision
if run:
    with st.spinner('Finding a route and checking every road and service event…'):
        result=solve(scenario,time_limit=float(limit),max_states=int(states))
        if result['solver_status'] in ('optimal','feasible_time_limit','feasible_state_limit','physical_infeasible'):
            result['baselines']=baselines(scenario)
        st.session_state.result=result
r=st.session_state.result
st.markdown('<div class="lab-eyebrow">UGRP RESEARCH / ROUTING LAB</div>',unsafe_allow_html=True)
st.title('Flood-aware bus rerouting')
st.markdown('<div class="lab-subtitle">Explore safe routes, service priorities and disruption trade-offs — then lock the completed journey and replan what remains.</div>',unsafe_allow_html=True)
st.markdown('<div class="context-line">'+''.join(f'<span>{escape(str(label))}</span>' for label in [scenario.get('name','Scenario'),
    f"Current · {scenario['state']['current']}",f"Elapsed · {scenario['state']['elapsed']:g} min",f"Locked events · {len(scenario['state']['history'])}"])
    +'</div>',unsafe_allow_html=True)
if notice:=st.session_state.pop('compatibility_notice',None):st.info(notice)
st.caption('Demand is a stop-access service proxy. Safety is supplied by the scenario; passenger capacity and future flooding are outside this model.')
overview,config,out,execution,docs=st.tabs(['Route overview','Edit inputs','Results & comparison','Journey history','Model notes'])

with overview:
    p=r.get('plan') if r else None
    if p:
        metrics=st.columns(4)
        for col,title,val in zip(metrics,['New demand proxy','Weighted service score','Remaining journey','Safe endpoint'],
                [f"{p['served_demand_proxy']:g}",f"{p['weighted_service_score']:g}",f"{p['remaining_minutes']:g} min",p['endpoint']]):col.metric(title,val)
        st.write('')
    network,summary=st.columns([2.65,1],gap='large')
    with network:
        with st.container(border=True):
            st.subheader('Road network & journey')
            st.image(network_svg(scenario,r),width='stretch')
            st.caption('Schematic network · Arrows show direction · Open fullscreen to inspect larger networks')
    with summary:
        with st.container(border=True):
            st.subheader('Recommended action')
            if r and p:
                st.markdown('<div class="status-pill">'+escape(r['solver_status'].replace('_',' ').capitalize())+'</div>',unsafe_allow_html=True)
                st.markdown('<div class="action-title">'+escape(OUTCOMES.get(p['operational_outcome'],p['operational_outcome']))+'</div>',unsafe_allow_html=True)
                st.write('**New service**')
                st.write(' → '.join(p['services']) or 'No additional stops served')
                st.divider()
                st.metric('Net objective',f"{p['objective']:g}")
                st.caption(f"Full trip {p['total_minutes']:g} min · Travel {p['travel_minutes']:g} min · Dwell {p['dwell_minutes']:g} min")
                st.success('Independent road audit passed.')
                if r['solver_status']!='optimal':st.warning('Feasible incumbent. Optimality is not proven.')
            elif r:
                st.error(OUTCOMES.get(r.get('operational_outcome'),'No verified plan'))
                st.write(r.get('message',''))
                st.caption('Solver status: '+r['solver_status'])
            else:
                st.markdown('<div class="action-title">Ready to plan</div>',unsafe_allow_html=True)
                st.markdown('<div class="empty-hint">Load an example or edit the snapshot, then select <b>Run routing model</b>. The recommendation and checked route will appear here.</div>',unsafe_allow_html=True)
            st.divider()
            st.caption('Purple = completed journey · Green = remaining plan · Red dashes = closed road')
    with st.expander('Road direction and exact attributes'):st.dataframe(scenario['roads'],hide_index=True,width='stretch')

with config:
    st.subheader('Build the disruption snapshot')
    st.caption('Apply inputs to validate your edits. Completed history stays locked, and old results are cleared.')
    with st.form(f'inputs_{rev}'):
        name=st.text_input('Scenario name',scenario.get('name',''))
        directed=st.checkbox('Directed road network',value=scenario['directed'],disabled=bool(scenario['state']['history']))
        st.markdown('#### Stops and service')
        stops=st.data_editor(pd.DataFrame(scenario['stops']),num_rows='dynamic',key=f'stops_{rev}',width='stretch',hide_index=True)
        st.caption('Demand is counted once per intentionally served stop. Priority changes its score; dwell is measured in minutes.')
        st.markdown('#### Roads')
        roads=st.data_editor(pd.DataFrame(scenario['roads']),num_rows='dynamic',key=f'roads_{rev}',width='stretch',hide_index=True)
        st.caption('Blank current_time, closed=true or safe=false disables a road. An unsafe origin requires a verified escape road.')
        with st.expander('Node safety and drawing coordinates'):
            nodes=st.data_editor(pd.DataFrame(scenario['nodes']),num_rows='dynamic',key=f'nodes_{rev}',width='stretch',hide_index=True)
            st.caption('transit_safe permits passage and service; wait_safe permits a safe finish. Coordinates x,y are optional.')
        st.markdown('#### Route and finishing locations')
        route=st.text_input('Original ordered stop IDs (JSON array)',json.dumps(scenario['original_route']))
        nodeids=[n['id'] for n in scenario['nodes']];a,b,c=st.columns(3)
        with a:terminal=st.selectbox('Original terminal node',nodeids,index=nodeids.index(scenario['terminal']))
        with b:endpoints=st.multiselect('Eligible endpoint nodes',nodeids,default=scenario['endpoints'])
        with c:current=st.selectbox('Initial current node',nodeids,index=nodeids.index(scenario['state']['current']),disabled=bool(scenario['state']['history']))
        st.caption('For new IDs, apply the tables first, then select them. After execution, change current position by advancing the journey.')
        st.markdown('#### Whole-trip thresholds and penalties')
        st.caption('Thresholds include elapsed time. Rates are additional cumulative charges in points/minute; kappa is points for terminal non-arrival.')
        help_text={'T_ref':'Normal reference duration in minutes.','T_soft':'Soft threshold in minutes.','T_max':'Overtime target in minutes; this is not a hard cap.',
            'lambda_ref':'Additional points per minute beyond T_ref.','lambda_soft':'Additional points per minute beyond T_soft.',
            'lambda_max':'Additional points per minute beyond T_max.','kappa':'Points charged once if the original terminal is not reached.'}
        params={};cols=st.columns(4)
        for i,key in enumerate(['T_ref','T_soft','T_max','kappa','lambda_ref','lambda_soft','lambda_max']):
            with cols[i%4]:params[key]=st.number_input(key,min_value=0.,value=float(scenario['parameters'][key]),key=f'param_{key}_{rev}',help=help_text[key])
        with st.expander('Disruption diagnostics and candidate filters'):
            theta=st.number_input('theta (diagnostics only)',min_value=1.,value=float(scenario['theta']))
            allowed=st.text_input('Optional allowed stop IDs (JSON array or null)',json.dumps(scenario['candidate_filter'].get('allowed_stop_ids')))
            corridor=st.text_input('Optional normal network corridor minutes (number or null)',json.dumps(scenario['candidate_filter'].get('max_normal_minutes_from_original')))
        apply=st.form_submit_button('Apply inputs',type='primary')
    if apply:
        try:
            d=deepcopy(scenario)
            def records(frame):
                recs=json.loads(frame.to_json(orient='records'))
                for rec in recs:
                    if rec.get('x') is None and rec.get('y') is None:rec.pop('x',None);rec.pop('y',None)
                return recs
            d.update(name=name,directed=directed,nodes=records(nodes),stops=records(stops),roads=records(roads),original_route=json.loads(route),
                     terminal=terminal,endpoints=endpoints,theta=theta,parameters=params,
                     candidate_filter={'allowed_stop_ids':json.loads(allowed),'max_normal_minutes_from_original':json.loads(corridor)})
            if not d['state']['history']:d['state']['current']=d['state']['origin']=current
            elif terminal!=scenario['terminal']:raise InputError('Original terminal is locked after execution; reset to start a different trip.')
            set_scenario(d,reset=False);st.rerun()
        except (ValueError,TypeError,KeyError) as e:st.error(f'Inputs were not applied: {e}')
    with st.expander('Import a prepared completed journey'):
        st.caption('Load a scenario with state.history to begin mid-trip. This starts a new scenario; snapshot edits cannot rewrite completed events.')
        st.json(scenario['state'])

with out:
    st.subheader('Results & comparison')
    if r:
        p=r.get('plan')
        st.write('**Solver status:**',r['solver_status'])
        st.write('**Operational outcome:**',OUTCOMES.get(p['operational_outcome']) if p else OUTCOMES.get(r.get('operational_outcome'),'No verified plan'))
        gap=r.get('optimality_gap');gap_text='Not available' if gap is None else f'{gap:.2%}'
        st.caption(f"Runtime {r['runtime_seconds']:.4f} s · Relative bound gap {gap_text} · Absolute gap {r.get('absolute_gap','Not available')}")
        if p:
            cols=st.columns(4)
            for col,title,val in zip(cols,['Net objective','Unweighted new demand','Weighted new score','Full-trip time'],
                    [p['objective'],p['served_demand_proxy'],p['weighted_service_score'],f"{p['total_minutes']:g} min"]):col.metric(title,val)
            a,b=st.columns([1,1],gap='large')
            with a:
                st.markdown('#### Time accounting')
                st.dataframe(pd.DataFrame([{'Component':label,'Minutes':p[key]} for label,key in [
                    ('Already elapsed','elapsed_minutes'),('Remaining road travel','travel_minutes'),('Remaining dwell','dwell_minutes'),
                    ('Remaining journey','remaining_minutes'),('Whole trip','total_minutes')]]),hide_index=True,width='stretch')
            with b:
                st.markdown('#### Penalty breakdown')
                st.dataframe(pd.DataFrame(penalty_rows(p)),hide_index=True,width='stretch')
                st.caption(f"Total penalty: {p['penalty_total']:g} points")
            st.caption(f"Terminal arrived: {p['terminal_arrival']} · Terminal physically reachable: {r['terminal_reachable']} · Usable outgoing road: {r['has_usable_outgoing']}")
            st.caption(f"Fixed historical demand proxy: {p['history_demand_proxy']:g} · Fixed historical score: {p['history_weighted_score']:g}")
            if r['solver_status']!='optimal':st.warning('Feasible incumbent only. The search did not prove optimality; the gap uses a loose service-reward upper bound.')
            st.markdown('#### Planned road and service events')
            show_events(p['events'])
            with st.expander('Decision variables and reconstructed connections'):
                st.json(p.get('decisions',{}));st.json(p.get('legs',[]))
            with st.expander('Unserved stop explanations'):
                reasons={x['stop']:', '.join(x['reasons']) for x in r['exclusions']}
                skipped=[{'Stop':s['id'],'Explanation':reasons.get(s['id'],'Eligible service omitted by the selected objective trade-off; no unique causal claim.')} for s in scenario['stops'] if s['id'] not in p['services']]
                st.dataframe(skipped,hide_index=True,width='stretch')
            row={'scenario':scenario.get('name',''),'current':scenario['state']['current'],'elapsed':p['elapsed_minutes'],'status':r['solver_status'],
                 'outcome':p['operational_outcome'],'new_demand':p['served_demand_proxy'],'weighted_score':p['weighted_service_score'],
                 'objective':p['objective'],'total_min':p['total_minutes'],'endpoint':p['endpoint']}
            if st.button('Save this result for comparison'):
                st.session_state.comparisons.append(row);st.rerun()
        else:st.warning(r.get('message','No verified plan.'))
        with st.expander('Baselines'):
            for label,b in r.get('baselines',{}).items():
                st.write('**'+label.replace('_',' ').capitalize()+'** · '+b['status'])
                if b.get('plan'):
                    q=b['plan'];st.caption(f"Full time {q['total_minutes']:g} min · demand proxy {q['served_demand_proxy']:g} · objective {q['objective']:g}")
                elif b.get('reason'):st.caption(b['reason'])
                else:st.json(b)
        with st.expander('Candidates, exclusions, endpoints and disruption flags'):
            for key in ['candidates','exclusions','endpoints','flags']:st.write(key.capitalize());st.json(r.get(key,[]))
        st.download_button('Export result JSON',json.dumps(r,indent=2),file_name='routing_result.json',mime='application/json')
    else:st.info('Run the routing model to inspect service, time, penalties and baselines.')
    if st.session_state.comparisons:
        st.markdown('#### Saved scenario comparisons')
        st.dataframe(st.session_state.comparisons,hide_index=True,width='stretch')
        a,b=st.columns([1,1])
        with a:st.download_button('Export comparisons CSV',pd.DataFrame(st.session_state.comparisons).to_csv(index=False),file_name='comparisons.csv')
        with b:
            if st.button('Clear comparisons'):st.session_state.comparisons=[];st.rerun()
    st.download_button('Export current scenario JSON',json.dumps(scenario,indent=2),file_name='scenario.json',mime='application/json')

with execution:
    st.subheader('Advance, lock and replan')
    st.caption('The completed journey is immutable. Commit a prefix of a verified plan, then update the disruption snapshot.')
    with st.container(border=True):
        st.markdown('#### Completed journey')
        if scenario['state']['history']:show_events(scenario['state']['history'])
        else:st.caption('The bus has not executed any events in this scenario.')
    if r and r.get('plan'):
        events=r['plan']['events']
        st.caption('Each road move and stop service is a separate event. Advancing to a stop before its service event does not collect demand or charge dwell.')
        event_count=st.number_input('Number of planned events to execute',min_value=0,max_value=len(events),value=min(1,len(events)),step=1,key=f'count_{rev}')
        show_events(events[:event_count])
        if st.button('Advance bus and lock these events',disabled=event_count==0,type='primary'):
            try:set_scenario(advance(scenario,r,int(event_count)),reset=False);st.rerun()
            except (ValueError,AssertionError) as e:st.error(str(e))
    else:st.info('Run the model first, then advance a verified plan.')
    st.caption('Next: edit current roads or stop conditions in Edit inputs, apply them, and run again. Realized elapsed time and completed service remain fixed.')

with docs:
    st.subheader('Understand the model')
    manuals={label:path for label,path in [('Quick start','README.md'),('Mathematical formulation','docs/FORMULATION.md'),
        ('Input format','docs/INPUT_FORMAT.md'),('Meeting walkthrough','docs/MEETING_DEMO.md'),
        ('Existing work audit','docs/EXISTING_WORK_AUDIT.md'),('Assumptions and limitations','docs/LIMITATIONS.md')] if (ROOT/path).exists()}
    manual=st.selectbox('Read documentation',list(manuals))
    st.markdown((ROOT/manuals[manual]).read_text())
