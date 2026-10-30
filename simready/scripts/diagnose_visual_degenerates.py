import collections,json,pathlib
import numpy as np
from pxr import Usd,UsdGeom
ROOT=pathlib.Path(__file__).resolve().parents[1];s=Usd.Stage.Open(str(ROOT/'asset/seca_scale_up_ultra_articulated/usd/seca_scale_up_ultra_articulated.usda'))
scales=[0,1e-24,1e-18,1e-16,1e-14,2e-14,1e-12];counts=collections.Counter();attrs=collections.Counter();examples=[]
for p in s.Traverse():
 if not p.IsA(UsdGeom.Mesh) or '/Visual/' not in str(p.GetPath()):continue
 m=UsdGeom.Mesh(p);c=np.array(m.GetFaceVertexCountsAttr().Get());idx=np.array(m.GetFaceVertexIndicesAttr().Get());pts=np.asarray(m.GetPointsAttr().Get())
 if not (c==3).all():continue
 t=idx.reshape(-1,3);cross=np.linalg.norm(np.cross(pts[t[:,1]]-pts[t[:,0]],pts[t[:,2]]-pts[t[:,0]]),axis=1)
 for tol in scales:counts[str(tol)]+=int((cross<=tol).sum())
 if (cross<=1e-18).any():
  attr=[(a.GetName(),a.GetMetadata('interpolation'),len(a.Get()) if hasattr(a.Get(),'__len__') else None) for a in p.GetAuthoredAttributes() if a.Get() is not None]
  key=str([(x[0],x[1]) for x in attr if x[1]])
  attrs[key]+=1
  if len(examples)<4:examples.append({'path':str(p.GetPath()),'attributes':attr,'children':[(x.GetName(),x.GetTypeName()) for x in p.GetChildren()]})
r={'cross_product_thresholds_m2':counts,'interpolations':attrs,'examples':examples}
(ROOT/'validation/visual-degenerate-diagnostic.json').write_text(json.dumps(r,indent=2,default=str)+'\n');print(json.dumps(r,indent=2,default=str))
