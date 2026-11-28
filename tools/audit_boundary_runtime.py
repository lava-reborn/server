"""Validate the installed representation through actual game travel functions."""
import argparse,collections,hashlib,json,os,re,sys
from pathlib import Path
from functools import lru_cache
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    os.environ['LAVA_BOUNDARY_WORLD']=str(args.manifest)
    import world,travel,boundary_world as bw,progression,rooms,coasts,mobs,location_entry
    @lru_cache(maxsize=128)
    def geometry(path):
        text=Path(path).read_text(encoding='utf-8-sig');tag=re.search(r'<location([^>]*)>',text)[1]
        attrs=dict(re.findall(r'(\w+)="([^"]*)"',tag));w,h=int(attrs['width']),int(attrs['height'])
        obstacles={int(c[2:4],16)*w+int(c[:2],16) for c in world._chunks(text,'obstacles',5)}
        remaining=set(range(w*h))-obstacles;groups=[]
        while remaining:
            seed=min(remaining);group={seed};pending=[seed];remaining.remove(seed)
            while pending:
                for n in progression.hex_neighbours(pending.pop(),w,h):
                    if n in remaining:remaining.remove(n);group.add(n);pending.append(n)
            groups.append(group)
        return obstacles,max(groups,key=len)
    errors=[];counts=collections.Counter();templates=collections.Counter();ids=set();actors=0
    for n,(key,record) in enumerate(bw.manifest()['cells'].items(),1):
        cell=tuple(map(int,key.split(',')));ident=record['id'];templates[record['template']]+=1
        if ident in ids:errors.append((key,'shared_location_identity'))
        ids.add(ident)
        loc=world.location(ident);obstacles,land=geometry(world.source_path_for(record['template']))
        if loc.obstacles!=obstacles:errors.append((key,'native_collision_changed'))
        if loc.spawns!=[tuple(s) for s in record['spawns']+record.get('scheduled_spawns',[])]:errors.append((key,'spawn_data_mismatch'))
        if hashlib.md5(Path(world.path_for(ident)).read_bytes()).hexdigest()!=record['md5']:errors.append((key,'client_hash_mismatch'))
        if world.location_at(*cell)!=ident:errors.append((key,'binding_mismatch'))
        for c,t in loc.spawns:
            if c not in land:errors.append((key,'actor_in_obstacle_or_isolated_area',c,t))
            if t==98:counts['magrib19']+=1
            if record.get('crocodile') and t==record['crocodile']['type_id']:
                counts['crocodiles']+=1
                if not coasts.without_loot(ident,t):errors.append((key,'animal_loot_enabled'))
        sides=travel.exit_sides(loc);by_side={}
        for c,side in sides.items():
            if c not in obstacles:by_side.setdefault(side,c)
        for side,c in by_side.items():
            try:
                dest=travel.plan_exit(loc,c,*cell);target=world.location(dest.loc_id)
                _blocked,target_land=geometry(world.source_path_for((bw.row(dest.loc_id) or {}).get('template',dest.loc_id)))
                if dest.pos not in target_land:errors.append((key,'arrival_in_obstacle_or_isolated_area',side,dest.pos))
                if '%d,%d'%(dest.gx,dest.gy) in bw.blocked_cells():errors.append((key,'exit_into_wall',side))
                if side in travel.SIDES:
                    reverse={s:p for p,s in travel.exit_sides(target).items() if p not in target.obstacles}
                    if travel.OPPOSITE[side] not in reverse:errors.append((key,'missing_return_exit',side))
                    else:
                        back=travel.plan_exit(target,reverse[travel.OPPOSITE[side]],dest.gx,dest.gy)
                        if back.loc_id!=ident:errors.append((key,'return_wrong_cell',side,back.loc_id))
                counts['transitions']+=1
            except travel.Refused as why:errors.append((key,'declared_exit_refused',side,str(why)))
        if record.get('no_map') and not travel.no_map(ident):errors.append((key,'tunnel_map_exit_enabled'))
        if record['boundary'] and not by_side:errors.append((key,'sealed_boundary_room'))
        if n%1000==0:
            print('Validated',n,'instances;',len(errors),'errors',flush=True)
            world._CACHE.clear();travel._SIDES.clear();travel._WAR_ENTRIES.clear()
        if len(errors)>100:break
    # Check compiled native service rooms wherever this snapshot places them.
    # Aligned trail nodes retain their original masters rather than adding
    # the four service copies used by an earlier draft.
    for cell,r in bw.manifest()['cells'].items():
        if r['source_location'] not in (599,624) or r['boundary']:continue
        room=rooms.Room(world.location(r['id']),rooms.IdAllocator(),world.mob_types())
        if sorted((a.cell,a.type_id) for a in room.npcs.values())!=sorted(map(tuple,r['spawns'])):errors.append((cell,'service_actor_duplicate_or_missing'))
    report=dict(instances=n,counts=dict(counts),errors=errors,templates=dict(templates),unique_ids=len(ids),
        magrib_level=mobs.stats(98).level,magrib_xp=mobs.stats(98).xp_mult)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='templates'},ensure_ascii=False),flush=True)
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
