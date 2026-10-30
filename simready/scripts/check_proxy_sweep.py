import itertools,json,pathlib
import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation
from scipy.optimize import linprog
ROOT=pathlib.Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'validation/articulation-model.json').read_text())
display=next(c for c in data['colliders'] if c['body']=='Display_Tilt' and c['name']=='Display')
pivot=np.asarray(data['body_pivots_m']['Display_Tilt']);dpoints=np.asarray(display['points_local_m'])
base=[]
for c in data['colliders']:
    if c['body']!='Base' or c['name']=='Display_Arm':continue
    pts=np.asarray(c['points_local_m'])+np.asarray(data['body_pivots_m']['Base'])
    base.append((c['name'],ConvexHull(pts).equations,pts.min(axis=0),pts.max(axis=0)))
overlaps=[];samples=[]
for yi in range(7):
    for ti in range(7):
        yaw=-.6+yi*.2;tilt=-.4+ti*(.8/6)
        matrix=Rotation.from_euler('z',yaw).as_matrix()@Rotation.from_euler('x',tilt).as_matrix()
        pts=dpoints@matrix.T+pivot;h=ConvexHull(pts).equations;lo=pts.min(axis=0);hi=pts.max(axis=0);hits=[]
        for name,hb,blo,bhi in base:
            if np.any(hi<=blo) or np.any(bhi<=lo):continue
            planes=np.concatenate([h,hb]);A=np.column_stack([planes[:,:3],np.linalg.norm(planes[:,:3],axis=1)])
            x=linprog([0,0,0,-1],A_ub=A,b_ub=-planes[:,3],bounds=[(None,None)]*3+[(0,None)],method='highs')
            if x.success and x.x[3]>1e-5:hits.append({'collider':name,'inscribed_overlap_radius_m':float(x.x[3])})
        samples.append({'yaw_rad':yaw,'tilt_rad':tilt,'hits':hits});overlaps.extend([{'yaw_rad':yaw,'tilt_rad':tilt,**x} for x in hits])
result={'sample_count':len(samples),'samples':samples,'overlaps':overlaps,
 'excluded_pair':'Display_Tilt/Display versus Base/Display_Arm (authored USD pair filter)',
 'scope':'Static convex proxy intersections at 49 simultaneous yaw/tilt poses; does not test swept surfaces, near-misses, PhysX filtering or actual device clearance.'}
(ROOT/'validation/proxy-sweep.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'samples':len(samples),'overlaps':overlaps},indent=2))
assert not overlaps
