"""Fit native boundary maps together without changing the owner's painted cells.

Direction, native collision and reciprocal exits are constraints. Variation is
only a tie breaker between compatible maps, never a reason to rotate a map or
to open a blocked face. Explicit template pins remain authoritative.
"""
from collections import deque
import boundary_planner as p


def variant_rank(key,ident):
    value=2166136261
    for c in f'{key}:{ident}':value=((value^ord(c))*16777619)&0xffffffff
    return value


def fit(placements,layers,catalog,generated,special,context,repair=False):
    """Joint coordinate and pair moves; accept only a lexicographic improvement.

    A previously compatible seam is a hard constraint. This keeps an isolated
    impossible join from preventing repairs elsewhere in the same long rim.
    Pair moves escape cases where neither map can be changed on its own.
    """
    original={k:r['template'] for k,r in placements.items()}
    domains={};closed={};fixed={};edges=[];incident={k:[] for k in placements}
    for key,row in sorted(placements.items()):
        wanted,neighbours=context(row['kind'],p.point(key))
        closed[key]=wanted
        old=original[key]
        candidates={old}
        if key not in layers['overrides'] and not row.get('tunnel'):
            candidates|={i for i,pr in catalog.items() if pr.kind==row['kind']
                         and pr.closed==wanted and (i not in p.CONNECTORS or old in p.CONNECTORS or repair and not wanted)}
        # Keep the old value as a safe fallback at impossible or pinned joins.
        # Do not introduce a new closed face behind another authored scene.
        forbidden={s for s in p.STEP if p.cell_key(p.neighbour(p.point(key),s)) in placements
                   or p.neighbour(p.point(key),s) in special}
        candidates={i for i in candidates if not (catalog[i].closed-catalog[old].closed)&forbidden}
        fixed[key]=[(s,pr) for s,pr in neighbours
                    if p.cell_key(p.neighbour(p.point(key),s)) not in placements]
        candidates={i for i in candidates if all(p.seam(catalog[i],pr,s) is not None
                    for s,pr in fixed[key] if p.seam(catalog[old],pr,s) is not None)}
        domains[key]=sorted(candidates)
        for side in ('E','S'):
            other=p.cell_key(p.neighbour(p.point(key),side))
            if other in placements:
                idx=len(edges);edges.append((key,other,side,p.seam(catalog[old],catalog[original[other]],side) is not None))
                incident[key].append(idx);incident[other].append(idx)
    chosen=dict(original)

    def score(patch):
        keys=patch.keys();bad=direction=0;drift=0.;repeat=rank=0
        for k,i in patch.items():
            direction+=len(catalog[i].closed^closed[k])
            rank+=variant_rank(k,i)
            for side,pr in fixed[k]:
                value=p.seam(catalog[i],pr,side)
                bad+=value is None
                if value is not None:drift+=value
        for idx in {idx for k in keys for idx in incident[k]}:
            a,b,side,was_good=edges[idx]
            ai=patch.get(a,chosen[a]);bi=patch.get(b,chosen[b])
            value=p.seam(catalog[ai],catalog[bi],side)
            if value is None and was_good:return None
            bad+=value is None
            if value is not None:drift+=value
            repeat+=ai==bi
        # Never sacrifice a native join or direction for cosmetic variety.
        # Among usable seams prefer more overlapping exits before variation.
        return bad,direction,round(drift,9),repeat,rank

    active={k for k,d in domains.items() if len(d)>1}
    def plus(a,b):return tuple(x+y for x,y in zip(a,b))
    def node_cost(key,ident):
        bad=repeat=0;drift=0.
        for side,pr in fixed[key]:
            value=p.seam(catalog[ident],pr,side);bad+=value is None
            if value is not None:drift+=value
        for idx in incident[key]:
            a,b,side,was_good=edges[idx];other=b if a==key else a
            if other in active:continue
            value=p.seam(catalog[ident],catalog[chosen[other]],side if a==key else p.OPPOSITE[side])
            if value is None and was_good:return None
            bad+=value is None
            if value is not None:drift+=value
            repeat+=ident==chosen[other]
        return bad,len(catalog[ident].closed^closed[key]),drift,repeat,variant_rank(key,ident)
    def edge_cost(a,ai,b,bi):
        idx=next(idx for idx in incident[a] if b in edges[idx][:2])
        x,y,side,was_good=edges[idx]
        value=p.seam(catalog[ai],catalog[bi],side if x==a else p.OPPOSITE[side])
        if value is None and was_good:return None
        return int(value is None),0,value or 0.,int(ai==bi),0

    if repair:
        # Several stale closed faces can mutually pin a whole two-dimensional
        # patch. Try the real backing of the entire patch before local moves.
        preferred={k:min(d,key=lambda i:(len(catalog[i].closed^closed[k]),
                    sum(p.seam(catalog[i],pr,s) is None for s,pr in fixed[k]),variant_rank(k,i)))
                   for k,d in domains.items()}
        value=score(preferred)
        if value is not None and value<score(chosen):chosen.update(preferred)

    unseen=set(active)
    while unseen:
        root=min(unseen);component={root};queue=[root];unseen.remove(root)
        for key in queue:
            for idx in incident[key]:
                a,b,_,_=edges[idx];other=b if a==key else a
                if other in unseen:unseen.remove(other);component.add(other);queue.append(other)
        adjacent={k:[b if a==k else a for idx in incident[k] for a,b,_,_ in [edges[idx]]
                     if (b if a==k else a) in component] for k in component}
        # Long straight runs and branching trees are solved jointly, including
        # switches of three or more maps which no greedy pair can discover.
        # On a cycle, condition one map and solve the remaining path exactly.
        count=sum(map(len,adjacent.values()))//2
        cyclic=count==len(component) and all(len(v)==2 for v in adjacent.values())
        if count!=len(component)-1 and not cyclic:continue
        first=min(component)
        trials=domains[first] if cyclic else [None]
        best_patch=None;best_cost=None
        for initial in trials:
            parent={first:None};order=[first]
            for key in order:
                for other in adjacent[key]:
                    if other not in parent:
                        parent[other]=key;order.append(other)
                        if cyclic:break
            extra=[(a,b) for a in component for b in adjacent[a] if a<b and parent[a]!=b and parent[b]!=a]
            dp={};decisions={}
            for key in reversed(order):
                dp[key]={};decisions[key]={}
                for ident in domains[key]:
                    if key==first and initial is not None and ident!=initial:continue
                    cost=node_cost(key,ident)
                    if cost is None:continue
                    for a,b in extra:
                        if key not in (a,b):continue
                        other=b if key==a else a
                        # The only extra edge on a ring joins the conditioned root.
                        if other==first:
                            value=edge_cost(key,ident,first,initial)
                            if value is None:cost=None;break
                            cost=plus(cost,value)
                    if cost is None:continue
                    picks={}
                    for child in adjacent[key]:
                        if parent.get(child)!=key:continue
                        options=[]
                        for ci,cc in dp[child].items():
                            value=edge_cost(key,ident,child,ci)
                            if value is not None:options.append((plus(cc,value),ci))
                        if not options:cost=None;break
                        value,ci=min(options);cost=plus(cost,value);picks[child]=ci
                    if cost is not None:dp[key][ident]=cost;decisions[key][ident]=picks
            if not dp[first]:continue
            cost,ident=min((cost,ident) for ident,cost in dp[first].items())
            patch={first:ident}
            for key in order:patch.update(decisions[key][patch[key]])
            # Use the same rounded objective as local moves for comparisons.
            total=score(patch)
            if total is not None and (best_cost is None or total<best_cost):best_cost=total;best_patch=patch
        old={k:chosen[k] for k in component}
        if best_patch is not None and best_cost<score(old):chosen.update(best_patch)
    # A work queue revisits only the neighbours of a change. Deterministic
    # bounded sweeps avoid a full coastline solver on every brush stroke.
    queue=deque(sorted(active));queued=set(queue);budget=max(1,len(active))*12
    while queue and budget:
        key=queue.popleft();queued.discard(key);budget-=1
        old=chosen[key];best=score({key:old});value=old
        for ident in domains[key]:
            candidate=score({key:ident})
            if candidate is not None and candidate<best:best=candidate;value=ident
        if value!=old:
            chosen[key]=value
            for idx in incident[key]:
                a,b,_,_=edges[idx];other=b if a==key else a
                if other in active and other not in queued:queue.append(other);queued.add(other)
    # Adjacent alternatives can need a coordinated switch. Every accepted
    # pair preserves all good external joins, not only their shared face.
    for _ in range(3):
        changed=False
        for a,b,_,_ in edges:
            if a not in active or b not in active:continue
            old={a:chosen[a],b:chosen[b]};best=score(old);patch=old
            for ai in domains[a]:
                for bi in domains[b]:
                    candidate=score({a:ai,b:bi})
                    if candidate is not None and candidate<best:
                        best=candidate;patch={a:ai,b:bi}
            if patch!=old:chosen.update(patch);changed=True
        if not changed:break
    updates=[]
    for key,ident in sorted(chosen.items()):
        if ident!=original[key]:
            placements[key]['template']=ident
            updates.append(dict(cell=key,previous=original[key],template=ident))
    return updates
