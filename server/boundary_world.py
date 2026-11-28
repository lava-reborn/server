"""Installed boundary instances: shared art, independent cells and safe exits.

The editor draft is never read by the game. Only an explicitly exported,
versioned manifest is active. Generated XML lives in a content-addressed temp
cache; no copy of the graphics or native templates is required.
"""
from functools import lru_cache
import hashlib,json,math,os,re,tempfile,threading
from pathlib import Path

_LOCK=threading.RLock()

@lru_cache(maxsize=1)
def manifest():
    setting=os.environ.get('LAVA_BOUNDARY_WORLD')
    if setting=='off':return {}
    path=Path(setting) if setting else Path(__file__).resolve().parents[1]/'data/boundary_world.json'
    if not path.exists():return {}
    value=json.loads(path.read_text(encoding='utf-8'))
    if value.get('version')!=1:raise ValueError('Unsupported boundary manifest')
    return value

@lru_cache(maxsize=1)
def by_id():
    return {int(r['id']):dict(r,cell=k) for k,r in manifest().get('cells',{}).items()}

def row(ident):return by_id().get(int(ident))
def cell_row(x,y):return manifest().get('cells',{}).get('%d,%d'%(math.floor(x),math.floor(y)))
def coordinate(ident):
    r=row(ident)
    return tuple(map(int,r['cell'].split(','))) if r else None

def blocked(x,y):
    if not manifest():return None
    return '%d,%d'%(math.floor(x),math.floor(y)) in blocked_cells()

@lru_cache(maxsize=1)
def blocked_cells():return frozenset(manifest().get('blocked',()))

@lru_cache(maxsize=1)
def regions():return {k:name for name,keys in manifest().get('regions',{}).items() for k in keys}

def crossing(a,b):
    """None outside an installation; otherwise respect both native faces."""
    if not manifest():return None
    ax,ay=map(math.floor,a);bx,by=map(math.floor,b)
    if (ax,ay)==(bx,by):return True
    delta=(bx-ax,by-ay);side={(1,0):'E',(-1,0):'W',(0,1):'S',(0,-1):'N'}.get(delta)
    if not side:return False
    ak,bk=f'{ax},{ay}',f'{bx},{by}'
    if regions().get(ak,'world')!=regions().get(bk,'world'):return False
    if bk in blocked_cells():return False
    ar,br=cell_row(ax,ay),cell_row(bx,by);op={'N':'S','S':'N','E':'W','W':'E'}[side]
    return (not ar or side in ar['allowed_exits']) and (not br or op in br['allowed_exits'])

def xml_bytes(record,raw):
    """Keep native drawing/collision intact, replace only spawns/exit zones."""
    text=raw.decode('utf-8-sig');allowed=set(record['allowed_exits']);portals=record.get('portals',{})
    codes={'1':'W','2':'N','3':'E','4':'S'}
    match=re.search(r'<outzones>(.*?)</outzones>',text,re.S)
    if not match:raise ValueError('Native location has no exit zones')
    zones=[]
    native_zones=''.join(match[1].split())
    if len(native_zones)%5:raise ValueError('Native location has malformed exit zones')
    for i in range(0,len(native_zones),5):
        chunk=native_zones[i:i+5];side=codes.get(chunk[4])
        if side in portals:zones.append(chunk[:4]+portals[side]['side'])
        elif side in allowed:zones.append(chunk)
        elif chunk[4] in ('a','b') and chunk[4] in record.get('source_doors',{}):zones.append(chunk)
    text=text[:match.start(1)]+''.join(zones)+text[match.end(1):]
    width=int(re.search(r'\bwidth="(\d+)"',text)[1])
    interior=''.join('%02x%02x%s'%(c%width,c//width,portal['side'])
                     for portal in portals.values() for c in portal.get('source_hexes',[]))
    if interior:
        text=text.replace('</outzones>',interior+'</outzones>',1)
    spawns=''.join('%02x%02x%04x'%(c%width,c//width,t) for c,t in record['spawns']+record.get('scheduled_spawns',[]))
    text,n=re.subn(r'<mobs>.*?</mobs>','<mobs>'+spawns+'</mobs>',text,count=1,flags=re.S)
    if n!=1:raise ValueError('Native location has no spawn node')
    return text.encode('utf-8')

@lru_cache(maxsize=256)
def native_bytes(template):
    import world
    path=world.source_path_for(template)
    if path is None:raise ValueError('Missing native boundary template')
    return Path(path).read_bytes()

def content(ident):
    record=row(ident)
    return xml_bytes(record,native_bytes(record['template'])) if record else None

@lru_cache(maxsize=32768)
def overlay_path(ident):
    record=row(ident)
    if not record:return None
    data=content(ident);digest=hashlib.sha256(data).hexdigest()
    path=Path(tempfile.gettempdir())/'lava-boundary-xml'/digest[:2]/(digest+'.xml')
    with _LOCK:
        if not path.exists():
            path.parent.mkdir(parents=True,exist_ok=True)
            import uuid
            pending=path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
            try:
                with pending.open('xb') as stream:stream.write(data)
                os.replace(pending,path)
            finally:
                if pending.exists():pending.unlink()
    return str(path)

def loc_defs(raw):
    """Small manifest metadata, without loading thousands of XMLs at once."""
    if not manifest():return raw
    records=by_id();seen=set()
    pattern=rb'<file\s+href="locations/static/(\d+)\.xml"[^>]*/>'
    def one(match):
        ident=int(match[1]);rec=records.get(ident)
        if not rec:return match[0]
        seen.add(ident)
        return definition(ident,rec)
    def definition(ident,rec):
        return ('<file href="locations/static/%d.xml" hash="%s" time="1616508972" size="%d" />'%(ident,rec['md5'],rec['size'])).encode()
    result=re.sub(pattern,one,raw)
    extra=b'\n'.join(definition(i,records[i]) for i in sorted(records) if i not in seen)
    return result.replace(b'</data>',extra+b'\n</data>')

def no_map(ident):return bool((row(ident) or {}).get('no_map'))
def source_id(ident):return (row(ident) or {}).get('source_location',ident)

def validation_problems(mob_types):
    """Validate the compiled actor source, including retired palm replacements.

    Old placements embedded into these XMLs must not also be checked against
    their former geometry. Validate every compiled spawn instead, once per
    shared native collision resource and independently per coordinate.
    """
    import world
    shapes={};seen=set();problems=[]
    for key,record in manifest().get('cells',{}).items():
        ident=record['id']
        if ident in seen:problems.append('boundary '+key+': duplicate location identity')
        seen.add(ident);path=world.source_path_for(record['template'])
        if path not in shapes:
            if path is None:problems.append('boundary '+key+': missing native resource');continue
            text=Path(path).read_text(encoding='utf-8-sig');tag=re.search(r'<location([^>]*)>',text)[1]
            attrs=dict(re.findall(r'(\w+)="([^"]*)"',tag));w,h=int(attrs['width']),int(attrs['height'])
            obstacles={int(c[2:4],16)*w+int(c[:2],16) for c in world._chunks(text,'obstacles',5)}
            shapes[path]=(w,h,obstacles)
        w,h,obstacles=shapes[path];occupied=set()
        for cell,kind in record['spawns']:
            if kind not in mob_types:problems.append('boundary '+key+': unknown inhabitant '+str(kind))
            if not 0<=cell<w*h or cell in obstacles:problems.append('boundary '+key+': inhabitant on an obstacle')
            if cell in occupied:problems.append('boundary '+key+': overlapping inhabitants')
            occupied.add(cell)
    return problems

def point_open(x,y):
    """Native second layer projected to the fractional global square."""
    record=cell_row(x,y)
    if not record or not record.get('boundary'):return True
    import world
    loc=world.location(record['id']);fx=x-math.floor(x);fy=y-math.floor(y)
    cell=min(loc.height-1,int(fy*loc.height))*loc.width+min(loc.width-1,int(fx*loc.width))
    return cell not in loc.obstacles

def clip_walk(gx,gy,x,y):
    if not manifest():return x,y
    dx,dy=x-gx,y-gy;steps=min(262144,max(1,math.ceil(max(abs(dx),abs(dy))*256)))
    previous=(gx,gy);was_open=point_open(gx,gy)
    for n in range(1,steps+1):
        t=n/steps;point=(gx+dx*t,gy+dy*t)
        a=tuple(map(math.floor,previous));b=tuple(map(math.floor,point))
        if a!=b:
            # A diagonal corner must have two viable face paths, so two
            # touching blockers cannot be slipped between.
            if a[0]!=b[0] and a[1]!=b[1]:
                ways=((a,(b[0],a[1]),b),(a,(a[0],b[1]),b))
                valid=all(crossing(u,v) for path in ways for u,v in zip(path,path[1:]))
            else:valid=crossing(a,b)
            if not valid:return previous
        opened=point_open(*point)
        if was_open and not opened:return previous
        was_open|=opened;previous=point
    return x,y
