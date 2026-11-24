"""Dependency-free SVG; only escaped input strings enter the document."""
from html import escape
from math import cos,sin,pi
from .core import prepare


def network_svg(raw,result=None):
    m=prepare(raw);d=m['data'];nodes=d['nodes'];positions={}
    provided=all('x' in n and 'y' in n for n in nodes)
    coords={n['id']:((n['x'],n['y']) if provided else (cos(2*pi*i/len(nodes)),sin(2*pi*i/len(nodes)))) for i,n in enumerate(nodes)}
    xs=[v[0] for v in coords.values()];ys=[v[1] for v in coords.values()]
    for v,(x,y) in coords.items():positions[v]=(100+720*(x-min(xs))/max(1,max(xs)-min(xs)),100+360*(max(ys)-y)/max(1,max(ys)-min(ys)))
    root=d['state']['current'];plan=result.get('plan') if result else None
    old=d['state']['history'];new=plan['events'] if plan else []
    history_roads={e['road'] for e in old if e['kind']=='move'}
    selected_roads={e['road'] for e in new if e['kind']=='move'}
    old_services={e['stop'] for e in old if e['kind']=='service'};new_services=set(plan['services']) if plan else set()
    original_roads=set()
    for a,b in zip(d['original_route'],d['original_route'][1:]):
        va,vb=m['stops'][a]['node'],m['stops'][b]['node']
        original_roads.update(e['road'] for e in m['normal'][va][1].get(vb,[]))
    parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 650" role="img" aria-label="Road network and bus journey"><rect width="920" height="650" fill="#fcfcff"/>',
           '<defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="15" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="context-stroke"/></marker></defs>']
    for e in d['roads']:
        a,b=positions[e['from']],positions[e['to']]
        closed=e['closed'] or not e['safe'] or e['current_time'] is None
        color='#cbd5e1';width=2
        if e['id'] in original_roads:color='#60a5fa';width=5
        if e['id'] in history_roads:color='#9333ea';width=7
        if e['id'] in selected_roads:color='#15803d';width=6
        marker=' marker-end="url(#arrow)"' if d['directed'] else ''
        title=escape(f"{e['id']}: {e['from']} → {e['to']}; normal {e['normal_time']} min; current {e['current_time']} min")
        parts.append(f'<path d="M{a[0]},{a[1]} L{b[0]},{b[1]}" stroke="{color}" stroke-width="{width}" fill="none"{marker}><title>{title}</title></path>')
        if closed:parts.append(f'<path d="M{a[0]},{a[1]} L{b[0]},{b[1]}" stroke="#dc2626" stroke-width="3" stroke-dasharray="7 4" fill="none"{marker}><title>{title}; CLOSED / UNSAFE</title></path>')
        time='closed' if closed else f"{e['current_time']:g}m"
        parts.append(f'<text x="{(a[0]+b[0])/2}" y="{(a[1]+b[1])/2-8}" text-anchor="middle" font-size="11" fill="#475569">{escape(time)}</text>')
    for n in nodes:
        v=n['id'];x,y=positions[v];ss=[s for s in d['stops'] if s['node']==v];sids={s['id'] for s in ss}
        unsafe=not n['transit_safe'] or any(not s['accessible'] for s in ss)
        color=('#fee2e2' if unsafe else '#dcfce7' if sids&new_services else '#ede9fe' if sids&old_services else '#ffedd5' if ss else '#e2e8f0')
        if any(s['id'] not in d['original_route'] for s in ss):
            parts.append(f'<path d="M{x},{y-17} L{x+17},{y} L{x},{y+17} L{x-17},{y} Z" fill="{color}" stroke="#475569"/>')
        else:parts.append(f'<circle cx="{x}" cy="{y}" r="15" fill="{color}" stroke="#475569" stroke-width="2"/>')
        if v==root:parts.append(f'<circle cx="{x}" cy="{y}" r="23" fill="none" stroke="#111827" stroke-width="3"/>')
        if plan and v==plan['endpoint']:parts.append(f'<rect x="{x-29}" y="{y-29}" width="58" height="58" rx="5" fill="none" stroke="#15803d" stroke-width="3"/>')
        if unsafe:parts.append(f'<text x="{x}" y="{y+5}" text-anchor="middle" fill="#b91c1c" font-weight="bold">×</text>')
        label=v+(' ['+', '.join(sorted(sids))+']' if ss and sids!={v} else '')
        parts.append(f'<text x="{x}" y="{y+43}" font-family="sans-serif" font-size="12" text-anchor="middle">{escape(label)}</text>')
    legends=[('#60a5fa','Original normal road reference'),('#9333ea','Locked completed road journey'),('#15803d','Selected remaining road path'),('#dc2626','Closed / unsafe road or stop'),('#dcfce7','Newly served stop'),('#ffedd5','Unserved / skipped stop'),('#ede9fe','Previously served stop')]
    for i,(color,label) in enumerate(legends):
        x=30+(i%3)*300;y=535+(i//3)*30
        parts.append(f'<rect x="{x}" y="{y-12}" width="20" height="12" fill="{color}" stroke="#64748b"/><text x="{x+28}" y="{y}" font-family="sans-serif" font-size="12">{label}</text>')
    parts.append('<text x="30" y="635" font-family="sans-serif" font-size="12">Diamond: alternative stop · Black ring: current bus · Green square: selected endpoint · Arrows: road direction</text></svg>')
    return ''.join(parts)
