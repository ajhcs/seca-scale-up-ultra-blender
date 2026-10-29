"""Quasistatic four-foot support on a planar floor, not a device model.

All distances are meters, floor parameters are dz/dx and dz/dy, angles are
radians. Screw geometry, rigid contacts and assumed COM are unmeasured.
"""
from math import sin,cos,atan
from itertools import combinations
FEET=((-0.25,-0.18),(-0.25,0.18),(0.25,-0.18),(0.25,0.18))

def world(p,rx,ry,h):
 x,y,z=p;cx,sx=cos(rx),sin(rx);cy,sy=cos(ry),sin(ry)
 return (cy*x+sy*sx*y+sy*cx*z,cx*y-sx*z,-sy*x+cy*sx*y+cy*cx*z+h)

def gaps(ext,ax,ay,rx,ry,h):
 pts=[world((x,y,-e),rx,ry,h) for (x,y),e in zip(FEET,ext)]
 return pts,[z-ax*x-ay*y for x,y,z in pts]

def solve3(A,b):
 m=[list(row)+[float(v)] for row,v in zip(A,b)]
 for i in range(3):
  k=max(range(i,3),key=lambda j:abs(m[j][i]));m[i],m[k]=m[k],m[i]
  if abs(m[i][i])<1e-12:raise ValueError('singular support')
  d=m[i][i];m[i]=[v/d for v in m[i]]
  for j in range(3):
   if j!=i:
    d=m[j][i];m[j]=[a-d*c for a,c in zip(m[j],m[i])]
 return [m[i][3] for i in range(3)]

def weights(triangle,p):
 (x0,y0),(x1,y1),(x2,y2)=triangle;x,y=p
 d=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
 if abs(d)<1e-12:raise ValueError('degenerate support triangle')
 a=((y1-y2)*(x-x2)+(x2-x1)*(y-y2))/d
 b=((y2-y0)*(x-x2)+(x0-x2)*(y-y2))/d
 return (a,b,1-a-b)

def support(ext,ax,ay,com=(0.0,0.03,0.55)):
 if len(ext)!=4 or any(e<0 or e>.01000001 for e in ext):raise ValueError('extension must be within 0 to 10 mm')
 results=[]
 for tri in combinations(range(4),3):
  q=[atan(ay),-atan(ax),sum(ext)/4]
  try:
   for _ in range(15):
    pts,g=gaps(ext,ax,ay,*q);f=[g[i] for i in tri]
    if max(abs(x) for x in f)<1e-10:break
    jac=[]
    for j in range(3):
     q1=q.copy();q1[j]+=1e-6;g1=gaps(ext,ax,ay,*q1)[1];jac.append([(g1[i]-g[i])/1e-6 for i in tri])
    dq=solve3([[jac[j][i] for j in range(3)] for i in range(3)],[-x for x in f]);q=[a+b for a,b in zip(q,dq)]
   pts,g=gaps(ext,ax,ay,*q)
   if min(g)<-1e-7 or max(abs(g[i]) for i in tri)>1e-7 or max(abs(q[0]),abs(q[1]))>.2:continue
   cp=world(com,*q);w=weights([(pts[i][0],pts[i][1]) for i in tri],cp[:2])
   if min(w)<-1e-7:continue
   results.append((cp[2],q,pts,g,tri,w))
  except (ValueError,OverflowError):continue
 if not results:raise ValueError('no stable support solution under model assumptions')
 _,q,pts,g,tri,w=min(results,key=lambda x:x[0]);return {'roll':q[0],'pitch':q[1],'height':q[2],'points':pts,'gaps':g,'support_triangle':tri,'support_weights':w}
