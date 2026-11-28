"""Read-only preservation of existing places and isolated administrative regions."""
from collections import Counter,deque
from heapq import heappush,heappop
import boundary_planner as p


class Policy:
    def __init__(self,preserved,regions,baseline_open,named,special):
        self.preserved=set(preserved);self.regions=regions;self.baseline_open=baseline_open
        self.named=named;self.special=special;self.old_labels=None
        self.region_of={c:name for name,cells in regions.items() for c in cells}

    def attach(self,layers):
        layers['_regions']=self.region_of
        layers['_mask_regions']={'eden'}
        layers['_preserved_land']=self.preserved
        return layers

    def projection(self,layers,repairs):
        preserved=self.preserved|repairs
        value={**layers,**{key:layers[key]-preserved for key in ('water','walls','rocks','coast')}}
        value['_preserved_land']=preserved
        return self.attach(value)|{'_preserved_land':preserved}

    def _components(self,layers,plan,catalog):
        labels={};groups=[]
        targets={c for c in self.named if c in self.preserved}
        for seed in sorted(targets):
            if seed in labels or not p.passable(layers,plan,seed):continue
            number=len(groups);group={seed};labels[seed]=number;queue=[seed]
            while queue:
                cell=queue.pop()
                for side in p.STEP:
                    n=p.neighbour(cell,side)
                    if n not in labels and p.can_step(layers,plan,cell,n,catalog):
                        labels[n]=number;group.add(n);queue.append(n)
            groups.append(group)
        return labels,groups

    def _corridor(self,layers,plan,catalog,seeds,target):
        # Smallest correction, then shortest path. Never cut a new river crossing,
        # an isolated region boundary, native closed side, or the world's frame.
        water=set(map(p.point,plan['retained_river']))
        region=self.region_of.get(next(iter(seeds)),'world')
        previous={c:None for c in seeds};cost={c:(0,0) for c in seeds};heap=[]
        for c in seeds:heappush(heap,(0,0,c))
        x0,y0,x1,y1=layers['bounds']
        while heap:
            cuts,steps,cell=heappop(heap)
            if cost.get(cell)!=(cuts,steps):continue
            if cell in target:
                path=[]
                while cell is not None:path.append(cell);cell=previous[cell]
                return set(path)
            for side in p.STEP:
                n=p.neighbour(cell,side)
                if not(x0<n[0]<x1 and y0<n[1]<y1) or n in water:continue
                if self.region_of.get(n,'world')!=region or not self.baseline_open(n):continue
                # Keep real existing exits. Proposed boundary scenes may be withdrawn
                # and rebuilt around a protected access corridor.
                valid=True
                for c,s in ((cell,side),(n,p.OPPOSITE[side])):
                    row=plan['placements'].get(p.cell_key(c))
                    profile=p.existing_profile(self.special[c]) if c in self.special else None
                    if profile and not profile.edges.get(s):valid=False;break
                if not valid:continue
                value=(cuts+(not p.passable(layers,plan,n) or p.cell_key(n) in plan['placements']),steps+1)
                if value<cost.get(n,(10**9,10**9)):
                    cost[n]=value;previous[n]=cell;heappush(heap,(*value,n))
        return set()

    def generate(self,layers,catalog,special,version):
        self.attach(layers);special={**self.special,**special};repairs=set();unrepaired=[]
        if self.old_labels is None:
            x0,y0,x1,y1=layers['bounds']
            blocked={(x,y) for x in range(x0,x1+1) for y in range(y0,y1+1) if not self.baseline_open((x,y))}
            baseline={**layers,'water':set(),'walls':blocked,'rocks':set(),'_preserved_land':self.preserved}
            empty=dict(placements={},issues=[],effective_water=[],generated_walls=[])
            self.old_labels,_=self._components(baseline,empty,catalog)
        for attempt in range(len(self.named)+1):
            projected=self.projection(layers,repairs)
            plan=p.generate(projected,catalog,special,version)
            labels,groups=self._components(projected,plan,catalog)
            counts={}
            for c in self.named:
                if c in self.preserved and c in labels:
                    counts.setdefault((self.region_of.get(c,'world'),self.old_labels.get(c)),Counter())[labels[c]]+=1
            changed=False
            unrepaired=[]
            for (region,old_component),components in counts.items():
                main=components.most_common(1)[0][0]
                for number in components:
                    if number==main:continue
                    path=self._corridor(projected,plan,catalog,groups[number],groups[main])
                    addition={c for c in path if not p.passable(projected,plan,c) or p.cell_key(c) in plan['placements']}-self.preserved-repairs
                    if addition:repairs|=addition;changed=True;break
                    unrepaired.append(dict(region=region,cells=sorted(p.cell_key(c) for c in self.named if labels.get(c)==number)))
                if changed:break
            if not changed:break
        preserved=self.preserved|repairs
        plan['input_fingerprint']=p.fingerprint(layers,version)
        plan['preserved_land']=sorted(map(p.cell_key,preserved))
        plan['access_corridors']=sorted(map(p.cell_key,repairs))
        plan['isolated_regions']={name:sorted(map(p.cell_key,cells)) for name,cells in self.regions.items()}
        plan['unrepaired_access']=unrepaired
        plan['protected_repairs']=[dict(cell=p.cell_key(c),existing=special.get(c),
            source='water' if c in layers['water'] else 'wall' if c in layers['walls'] else 'coast' if c in layers.get('coast',set()) else 'rock')
            for c in sorted(preserved&(layers['water']|layers['walls']|layers['rocks']|layers.get('coast',set())))]
        plan['summary'].update(source_water=len(layers['water']),protected_repairs=len(plan['protected_repairs']),
                               access_corridors=len(repairs))
        plan.pop('_blocked',None)
        return plan


def populated_places():
    import world
    from boundary_cells import inhabitants
    candidates={**world.borders(),**world.settlements(),**world.eden_map.CELL_TO_LOC}
    for ident in world.placements():
        if world.is_wilderness(ident):
            cell=world.unpack(ident)
            if p.inside(cell,(world.MAP_X[0],world.MAP_Y[0],world.MAP_X[1],world.MAP_Y[1])):
                candidates.setdefault(cell,ident)
    return {c:ident for c,ident in candidates.items() if inhabitants(ident)}


def native_policy():
    import world
    named={**populated_places(),**world.settlements()};eden=set(world.eden_map.CELL_TO_LOC)
    x0,y0,x1,y1=world.NOOB_VALLEY
    nubia={(x,y) for x in range(x0,x1+1) for y in range(y0,y1+1) if world.in_noob_valley(x,y)}
    preserved=eden|{c for c in named if world.passable(*c)}|{c for c in nubia if world.passable(*c)}
    return Policy(preserved,{'eden':eden,'nubia':nubia},lambda c:world.passable(*c),named,
                  {**named,**world.eden_map.CELL_TO_LOC})
