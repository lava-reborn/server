import zlib, struct, sys, re, os, collections

def body_of(path):
    raw=open(path,'rb').read()
    if raw[:3]==b'CWS': return zlib.decompress(raw[8:])
    if raw[:3]==b'FWS': return raw[8:]
    raise SystemExit('unsupported '+path)

def tags(body):
    nbits=body[0]>>3; p=(5+nbits*4+7)//8+4
    while p<len(body)-1:
        th=struct.unpack('<H',body[p:p+2])[0]; p+=2
        code=th>>6; ln=th&0x3f
        if ln==0x3f:
            ln=struct.unpack('<I',body[p:p+4])[0]; p+=4
        yield code, body[p:p+ln]
        p+=ln
        if code==0: break

def actions(data):
    """walk AVM1 action records, yield (opcode, payload)"""
    p=0
    while p < len(data):
        op=data[p]; p+=1
        if op==0: break
        if op>=0x80:
            if p+2>len(data): break
            ln=struct.unpack('<H',data[p:p+2])[0]; p+=2
            yield op, data[p:p+ln]; p+=ln
        else:
            yield op, b''

def strings_from(path):
    body=body_of(path)
    out=[]
    for code,data in tags(body):
        if code in (12,59):   # DoAction, DoInitAction
            d = data[2:] if code==59 else data   # DoInitAction has sprite id
            for op,payload in actions(d):
                if op==0x88:  # ConstantPool
                    if len(payload)<2: continue
                    n=struct.unpack('<H',payload[:2])[0]
                    parts=payload[2:].split(b'\x00')
                    out.extend(parts[:n])
                elif op==0x96:  # Push
                    q=0
                    while q<len(payload):
                        t=payload[q]; q+=1
                        if t==0:
                            e=payload.index(b'\x00',q); out.append(payload[q:e]); q=e+1
                        elif t==1: q+=4
                        elif t in (2,3): pass
                        elif t==4: q+=1
                        elif t==5: q+=1
                        elif t==6: q+=8
                        elif t==7: q+=4
                        elif t==8: q+=1
                        elif t==9: q+=2
                        else: break
    return out

if __name__=='__main__':
    path=sys.argv[1]
    s=strings_from(path)
    dec=[]
    for b in s:
        try: dec.append(b.decode('utf-8'))
        except: 
            try: dec.append(b.decode('cp1251'))
            except: pass
    print(f"### {os.path.basename(path)}: {len(dec)} strings, {len(set(dec))} unique")
    if len(sys.argv)>2 and sys.argv[2]=='dump':
        for x in sorted(set(dec)):
            print(x)
    else:
        pat=re.compile(r'XMLSocket|Socket|connect|onConnect|onXML|send|policy|crossdomain|localhost|\d{4,5}|http|\.ru|LoadVars|sendAndLoad|onData|close|server|host|port', re.I)
        hits=sorted({x for x in dec if pat.search(x) and len(x)<120})
        print(f"--- net-ish: {len(hits)}")
        for h in hits: print("  ",h)
