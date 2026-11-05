"""Export player animation lengths from shipped resources for server timing."""
import argparse
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

KINDS = ('fist', 'knife', 'pistol', 'rifle')
ACTIONS = ('fire_in', 'fire', 'fire_out', 'reload', 'use', 'arm_in', 'arm_out')


def build(resources, fps):
    models = {}
    for path in sorted((resources / 'personages').glob('*.xml')):
        models[path.stem] = {
            kind.tag: {action.get('id'): len([frame for frame in (action.text or '').split(',') if frame.strip()])
                       for action in kind if action.get('id') in ACTIONS}
            for kind in ET.parse(path).getroot() if kind.tag in KINDS}
    if fps <= 0 or '0' not in models:
        raise ValueError('Positive frame rate and default model 0 are required')
    for kind in KINDS:
        for action in ('fire', 'fire_out'):
            if models['0'][kind].get(action, 0) <= 0:
                raise ValueError('Default model lacks %s/%s' % (kind, action))
    return dict(frame_rate=fps, models=models)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--res', type=Path, default=os.environ.get('LAVA_RES', 'res'))
    parser.add_argument('--fps', type=int, default=25, help='Frame rate of the game main.swf')
    parser.add_argument('--out', type=Path, default=Path(__file__).with_name('action_animation.json'))
    args = parser.parse_args()
    data = build(args.res, args.fps)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('%d player models, %d frames/s' % (len(data['models']), args.fps))
