"""Draw a readable link graph directly from the authored USD physics stage."""
import pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from pxr import Usd,UsdPhysics
ROOT=pathlib.Path(__file__).resolve().parents[1]
stage=Usd.Stage.Open(str(ROOT/'asset/seca_scale_up_ultra_articulated/usd/seca_scale_up_ultra_articulated.usda'))
def mass(name):return UsdPhysics.MassAPI(stage.GetPrimAtPath('/SecaScaleUpUltra/Links/'+name)).GetMassAttr().Get()
def joint(name):
 j=UsdPhysics.RevoluteJoint(stage.GetPrimAtPath('/SecaScaleUpUltra/Joints/'+name))
 return {'axis':j.GetAxisAttr().Get(),'low':j.GetLowerLimitAttr().Get(),'high':j.GetUpperLimitAttr().Get(),
         'body0':j.GetBody0Rel().GetTargets()[0].name,'body1':j.GetBody1Rel().GetTargets()[0].name}
js={n:joint(n) for n in ['LeftWheel','RightWheel','DisplaySwivel','DisplayTilt']}
assert [(js[n]['body0'],js[n]['body1']) for n in js]==[('Base','Wheel_L'),('Base','Wheel_R'),('Base','Display_Yaw'),('Display_Yaw','Display_Tilt')]
fig,ax=plt.subplots(figsize=(12,4.6),dpi=150);fig.patch.set_facecolor('#f5f8fa');ax.set_facecolor('#f5f8fa');ax.set_xlim(0,12);ax.set_ylim(0,4.6);ax.axis('off')
ax.text(.3,4.2,'ARTICULATED USD  /  FIVE STUDY LINKS',fontsize=12,fontweight='bold',color='#163343',va='center')
ax.text(.3,3.88,'Four revolute joints connect the rigid bodies.',fontsize=10.5,color='#51636c',va='center')
positions={'Base':(.4,1.53,2.6,.95),'Wheel_L':(4.25,2.95,2.75,.78),'Wheel_R':(4.25,1.94,2.75,.78),'Display_Yaw':(4.25,.93,2.75,.78),'Display_Tilt':(8.35,.93,2.75,.78)}
def box(name,title,subtitle,color):
 x,y,w,h=positions[name];ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.02,rounding_size=0.09',linewidth=1.2,edgecolor=color,facecolor='white'))
 ax.text(x+.17,y+h*.64,title,fontsize=11,fontweight='bold',color='#19313d',va='center');ax.text(x+.17,y+h*.29,subtitle,fontsize=9.4,color='#526670',va='center')
box('Base','Base',f'{mass("Base"):.1f} kg  ·  modeled mass','#426579')
for side,n in [('LeftWheel','Wheel_L'),('RightWheel','Wheel_R')]:
 box(n,'Left wheel' if n=='Wheel_L' else 'Right wheel',f'{mass(n):.1f} kg  ·  {js[side]["axis"]} rotation','#c4762d')
for n,jname,title in [('Display_Yaw','DisplaySwivel','Display swivel'),('Display_Tilt','DisplayTilt','Display tilt')]:
 j=js[jname];box(n,title,f'{mass(n):.1f} kg  ·  {j["axis"]}  ·  ±{j["high"]:.1f}°','#258b8b')
edge='#8299a4';ax.plot([3,3.65],[2.005,2.005],color=edge,lw=1.7);ax.plot([3.65,3.65],[1.32,3.34],color=edge,lw=1.7)
for n in ('Wheel_L','Wheel_R','Display_Yaw'):
 x,y,w,h=positions[n];ax.annotate('',xy=(x,y+h/2),xytext=(3.65,y+h/2),arrowprops={'arrowstyle':'-|>','color':edge,'lw':1.7,'mutation_scale':11})
x,y,w,h=positions['Display_Yaw'];ax.annotate('',xy=(positions['Display_Tilt'][0],y+h/2),xytext=(x+w,y+h/2),arrowprops={'arrowstyle':'-|>','color':edge,'lw':1.7,'mutation_scale':11})
ax.text(.3,.25,'Axes, joint limits and per-link masses are assumptions; the 29 kg total is published.',fontsize=9.5,color='#536974',va='center')
fig.subplots_adjust(left=0,right=1,bottom=0,top=1);fig.savefig(ROOT/'previews/usd-joint-graph.png',facecolor=fig.get_facecolor());plt.close(fig)
