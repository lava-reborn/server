import zlib, struct, re, sys, os

TAGS = {0:'End',1:'ShowFrame',12:'DoAction',39:'DefineSprite',59:'DoInitAction',
        72:'DoABC_short',76:'SymbolClass',82:'DoABC',87:'DefineBinaryData',
        56:'ExportAssets'}

def parse(path):
    raw = open(path,'rb').read()
    sig = raw[:3].decode('latin1'); ver = raw[3]
    ulen = struct.unpack('<I', raw[4:8])[0]
    if sig == 'CWS':
        body = zlib.decompress(raw[8:])
    elif sig == 'ZWS':
        import lzma
        # SWF LZMA: 4 bytes compressed len, 5 bytes props, then data
        props = raw[12:17]
        d = lzma.LZMADecompressor(format=lzma.FORMAT_RAW,
              filters=[lzma._decode_filter_properties(lzma.FILTER_LZMA1, props)])
        body = d.decompress(raw[17:])
    else:
        body = raw[8:]
    print(f"{os.path.basename(path)}: sig={sig} swfver={ver} filelen={ulen} body={len(body)}")
    # skip rect
    p = 0
    nbits = body[0] >> 3
    total_bits = 5 + nbits*4
    p = (total_bits + 7)//8
    p += 4  # framerate + framecount
    counts = {}
    abc = []
    while p < len(body)-1:
        try:
            th = struct.unpack('<H', body[p:p+2])[0]
        except: break
        p += 2
        code = th >> 6
        ln = th & 0x3f
        if ln == 0x3f:
            ln = struct.unpack('<I', body[p:p+4])[0]; p += 4
        data = body[p:p+ln]
        p += ln
        name = TAGS.get(code, str(code))
        counts[name] = counts.get(name,0)+1
        if code in (72,82):
            abc.append(data)
        if code == 0: break
    print("  tags:", dict(sorted(counts.items(), key=lambda x:-x[1])[:14]))
    print("  DoABC blocks:", len(abc), "total", sum(len(a) for a in abc))
    return body, abc

if __name__ == '__main__':
    for f in sys.argv[1:]:
        try:
            parse(f)
        except Exception as e:
            print(f, "ERROR", e)
