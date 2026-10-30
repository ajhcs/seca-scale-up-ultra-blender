import pathlib,json
from pxr import Sdf,Usd,UsdPhysics
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=ROOT/'asset/seca_scale_up_ultra_articulated/usd/seca_scale_up_ultra_articulated.usda'
stage=Usd.Stage.Open(str(p))
display=stage.GetPrimAtPath('/SecaScaleUpUltra/Links/Display_Tilt/Colliders/Display')
arm=Sdf.Path('/SecaScaleUpUltra/Links/Base/Colliders/Display_Arm')
assert display.IsValid() and stage.GetPrimAtPath(arm).IsValid()
UsdPhysics.FilteredPairsAPI.Apply(display).CreateFilteredPairsRel().SetTargets([arm]);stage.GetRootLayer().Save()
meta=ROOT/'validation/articulation-model.json';data=json.loads(meta.read_text())
data['filtered_collider_pairs']=[['Display_Tilt/Display','Base/Display_Arm']]
data['assumptions']=[s.replace('Attached pairs have collision disabled by joint policy; the display and nonadjacent base remain eligible to collide.',
 'Attached pairs have collision disabled by joint policy; one display-to-mount proxy pair is additionally filtered, while display-to-mast and display-to-rail remain enabled.') for s in data['assumptions']]
meta.write_text(json.dumps(data,indent=2)+'\n')
print('Filtered only display shell collider versus mounting arm collider')
