"""Encode 36 Blender-rendered PNGs with one palette and a three-second loop."""
import json,os,pathlib
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parents[1]
frames=pathlib.Path(os.environ.get('SECA_FRAME_DIR',str(ROOT/'previews/.animation-frames')))
images=[Image.open(frames/f'frame-{i:03}.png').convert('RGB') for i in range(36)]
assert all(im.size==(640,480) for im in images)
sample=Image.new('RGB',(6*160,6*120))
for i,im in enumerate(images):sample.paste(im.resize((160,120)),((i%6)*160,(i//6)*120))
palette=sample.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
encoded=[im.quantize(palette=palette,dither=Image.Dither.FLOYDSTEINBERG) for im in images]
durations=[80 if i%3!=2 else 90 for i in range(36)]
output=ROOT/'previews/display-articulation.gif'
encoded[0].save(output,save_all=True,append_images=encoded[1:],duration=durations,loop=0,optimize=True,disposal=2)
with Image.open(output) as gif:
 assert gif.n_frames==36 and gif.size==(640,480)
 print(json.dumps({'frames':gif.n_frames,'dimensions':list(gif.size),'duration_ms':sum(durations),'bytes':output.stat().st_size,'loop':gif.info.get('loop')},indent=2))
