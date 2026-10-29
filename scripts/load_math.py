"""Idealized four-support vertical static equilibrium, not a seca load-cell model."""
import math,itertools
import numpy as np

G=9.80665
def solve(mass_kg,platform_xy,rail_fraction,rail_xy,rail_transfer,half_x,half_y,stiffness,gains):
    values=[mass_kg,*platform_xy,rail_fraction,*rail_xy,rail_transfer,half_x,half_y,*stiffness,*gains]
    if not all(math.isfinite(float(v)) for v in values):raise ValueError('Inputs must be finite')
    if mass_kg<0 or half_x<=0 or half_y<=0 or not 0<=rail_fraction<=1 or not 0<=rail_transfer<=1:raise ValueError('Invalid force or support parameters')
    if len(stiffness)!=4 or len(gains)!=4 or min(stiffness)<=0 or min(gains)<0:raise ValueError('Four positive stiffnesses and nonnegative gains required')
    # Positions are guessed, not measured load-cell locations. Negative Y is front.
    points=[(-half_x,-half_y),(half_x,-half_y),(-half_x,half_y),(half_x,half_y)]
    weight=mass_kg*G;platform=weight*(1-rail_fraction);rail=weight*rail_fraction;coupled=rail*rail_transfer;bypass=rail-coupled
    force=platform+coupled;mx=platform*platform_xy[0]+coupled*rail_xy[0];my=platform*platform_xy[1]+coupled*rail_xy[1]
    if force<=1e-12:return {'reactions_n':[0.0]*4,'reading_kg':0.0,'total_weight_n':weight,'platform_n':platform,'rail_n':rail,'coupled_rail_n':coupled,'bypassed_rail_n':bypass,'effective_cop_m':None,'moments_nm':[mx,my]}
    A=np.array([[1]*4,[p[0] for p in points],[p[1] for p in points]],dtype=float);b=np.array([force,mx,my],dtype=float);k=np.asarray(stiffness,dtype=float);best=None
    # The statically indeterminate choice is the nonnegative equilibrium that
    # minimizes sum(reaction^2 / stiffness), equivalent to equal linear spring
    # compliance assumptions for active contacts. No real calibration implied.
    for count in range(1,5):
        for active in itertools.combinations(range(4),count):
            idx=list(active);sq=np.sqrt(k[idx]);matrix=A[:,idx]*sq
            try:u=np.linalg.lstsq(matrix,b,rcond=None)[0]
            except np.linalg.LinAlgError as exc:raise ValueError('Unable to solve assumed support equilibrium') from exc
            r=sq*u
            if np.min(r)<-1e-8*max(1,force):continue
            r=np.maximum(r,0);candidate=np.zeros(4);candidate[idx]=r
            if np.linalg.norm(A@candidate-b)>1e-8*max(1,force):continue
            energy=float(np.sum(candidate*candidate/k))
            if best is None or energy<best[0]-1e-9:best=(energy,candidate)
    if best is None:raise ValueError('No nonnegative equilibrium for assumed support locations')
    reactions=best[1];reading=float(np.dot(reactions,np.asarray(gains,dtype=float))/G)
    return {'reactions_n':[float(x) for x in reactions],'reading_kg':reading,'total_weight_n':weight,'platform_n':platform,'rail_n':rail,'coupled_rail_n':coupled,'bypassed_rail_n':bypass,'effective_cop_m':[mx/force,my/force],'moments_nm':[mx,my]}
