"""Inventory exported render mesh topology; open artwork is not automatically a defect."""
import collections,json,pathlib
import numpy as np
from pxr import Usd,UsdGeom
ROOT=pathlib.Path(__file__).resolve().parents[1]
stage=Usd.Stage.Open(str(ROOT/'asset/seca_scale_up_ultra_articulated/usd/seca_scale_up_ultra_articulated.usda'))
rows=[]
for p in stage.Traverse():
 if not p.IsA(UsdGeom.Mesh) or '/Visual/' not in str(p.GetPath()):continue
 m=UsdGeom.Mesh(p);points=np.asarray(m.GetPointsAttr().Get(),dtype=float);counts=np.asarray(m.GetFaceVertexCountsAttr().Get(),dtype=int);ids=np.asarray(m.GetFaceVertexIndicesAttr().Get(),dtype=int)
 edges=collections.Counter();winding=collections.Counter();deg=0;exact=0;offset=0
 for n in counts:
  face=ids[offset:offset+n];offset+=n
  for a,b in zip(face,np.roll(face,-1)):
   key=(min(int(a),int(b)),max(int(a),int(b)));edges[key]+=1;winding[(int(a),int(b))]+=1
  if len(set(face))<n:deg+=1
  elif n==3:
   magnitude=np.linalg.norm(np.cross(points[face[1]]-points[face[0]],points[face[2]]-points[face[0]]))
   if magnitude<2e-14:deg+=1
   if magnitude==0:exact+=1
 badw=sum(1 for (a,b),n in edges.items() if n==2 and (winding[(a,b)]!=1 or winding[(b,a)]!=1))
 bound=sum(n==1 for n in edges.values());nonman=sum(n>2 for n in edges.values())
 rows.append({'path':str(p.GetPath()),'points':len(points),'faces':len(counts),'boundary_edges':bound,'nonmanifold_edges_gt2':nonman,'inconsistent_winding_edges':badw,'near_zero_cross_product_faces':deg,'exact_zero_area_faces':exact})
rows.sort(key=lambda x:x['path']);summary={'meshes':len(rows),'points':sum(r['points'] for r in rows),'faces':sum(r['faces'] for r in rows),
 'meshes_with_boundary_edges':sum(bool(r['boundary_edges']) for r in rows),'meshes_with_gt2_edges':sum(bool(r['nonmanifold_edges_gt2']) for r in rows),
 'meshes_with_winding_issues':sum(bool(r['inconsistent_winding_edges']) for r in rows),'meshes_with_near_zero_cross_product_faces':sum(bool(r['near_zero_cross_product_faces']) for r in rows),
 'boundary_edges':sum(r['boundary_edges'] for r in rows),'nonmanifold_edges_gt2':sum(r['nonmanifold_edges_gt2'] for r in rows),'near_zero_cross_product_faces':sum(r['near_zero_cross_product_faces'] for r in rows),'exact_zero_area_faces':sum(r['exact_zero_area_faces'] for r in rows)}
out={'summary':summary,'meshes':rows,'scope':'Index-topology inventory and triangle cross-product magnitudes under 2e-14 square meters of exported visual meshes only, not an intersection, manifold welding, physics-proxy, source-intent or rendering acceptance test. Open surfaces can be intentional artwork; findings require review.'}
(ROOT/'validation/visual-topology.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(summary,indent=2))
