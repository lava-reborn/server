"""Render one native inhabitant sprite into the editor's disposable cache."""
import argparse,json
from pathlib import Path
import location_art as A

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mob',type=int,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();art=A.Art();picture,offset=art.mob_picture(args.mob)
    placeholder=picture is None
    if placeholder:
        from PIL import Image
        path,_=art.mob_icon(args.mob);picture=Image.open(path).convert('RGBA');offset=(-picture.width//2,-picture.height)
    image=args.out.with_suffix('.png');temporary=image.with_name(image.stem+'.tmp.png');picture.save(temporary);temporary.replace(image)
    metadata=args.out.with_suffix('.tmp.json');metadata.write_text(json.dumps(dict(width=picture.width,height=picture.height,ox=offset[0],oy=offset[1],placeholder=placeholder)),encoding='utf-8');metadata.replace(args.out)
if __name__=='__main__':main()
