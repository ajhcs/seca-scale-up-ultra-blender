"""Create a separate, unvalidated drive overlay; never alter the base stage."""
import json,pathlib
from pxr import Usd,UsdPhysics,UsdGeom
ROOT=pathlib.Path(__file__).resolve().parents[1]
folder=ROOT/'asset/seca_scale_up_ultra_articulated/usd'
base=folder/'seca_scale_up_ultra_articulated.usda'
out=folder/'layers/illustrative_driven.usda'
assert not out.exists(), 'Do not overwrite an existing drive stage'
stage=Usd.Stage.CreateNew(str(out));stage.GetRootLayer().subLayerPaths=['../'+base.name]
stage.SetDefaultPrim(stage.GetPrimAtPath('/SecaScaleUpUltra'))
UsdGeom.SetStageMetersPerUnit(stage,1.0);UsdGeom.SetStageUpAxis(stage,UsdGeom.Tokens.z)
# Document that the layer has the same source metadata, while the drive is a hypothesis.
base_stage=Usd.Stage.Open(str(base));stage.GetRootLayer().customLayerData=base_stage.GetRootLayer().customLayerData
spec={'DisplaySwivel':(.05,.005,1.0),'DisplayTilt':(.10,.010,1.5)}
for name,(stiffness,damping,max_torque) in spec.items():
    p=stage.GetPrimAtPath('/SecaScaleUpUltra/Joints/'+name);assert p.IsValid()
    drive=UsdPhysics.DriveAPI.Apply(p,'angular');drive.CreateTypeAttr('force');drive.CreateTargetPositionAttr(0);drive.CreateTargetVelocityAttr(0)
    drive.CreateStiffnessAttr(stiffness);drive.CreateDampingAttr(damping);drive.CreateMaxForceAttr(max_torque)
stage.GetRootLayer().Save()
print('Created unvalidated, explicitly illustrative drive overlay',out)
