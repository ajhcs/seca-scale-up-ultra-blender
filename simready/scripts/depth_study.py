import pathlib,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pxr import Usd,UsdGeom,Gf,Sdf
ROOT=pathlib.Path(__file__).resolve().parents[1]
receipt=json.loads((ROOT/'source/build-inputs/visual-export.json').read_text())
offset=receipt['center_y_m'];bounds=receipt['bounds_m'];front=bounds[0][1]-offset;rear=bounds[1][1]-offset
chassis=receipt['geometry']['654 • lower platform chassis']['bounds_m'];glass=receipt['geometry']['654 • Bearclaw glass top']['bounds_m']
cases={'front_aligned':(front,front+.650),'center_aligned':(-.325,.325),'rear_aligned':(rear-.650,rear)}
result={'source_bounds_y_m':[front,rear],'source_depth_m':rear-front,'published_depth_m':.650,
 'difference_m':.650-(rear-front),'platform_chassis_dimensions_m':[chassis[1][i]-chassis[0][i] for i in range(3)],
 'modeled_glass_top_z_m':glass[1][2],'published_platform_dimensions_m':[.600,.467,.070],
 'registered_intervals_m':cases,
 'scope':'These three intervals are hypothetical registrations of the manufacturer nominal 650 mm dimension, not measured end planes, proposed geometry corrections, service clearances or physical validation.',
 'manufacturer_source':'https://hs.seca.com/hubfs/Lyndsey%20Folders/Product%20Sheets/seca_Scale-up_Line_654_455_257_257sh_product_sheet_US_en_24.pdf?hsLang=en'}
(ROOT/'research/depth-registration.json').write_text(json.dumps(result,indent=2)+'\n')
fig,ax=plt.subplots(figsize=(10,3.5));colors=['#1e78a5','#707b84','#b65b3c'];names=['Front aligned','Centered','Rear aligned']
for i,((key,(lo,hi)),color,name) in enumerate(zip(cases.items(),colors,names)):
    y=2-i;ax.hlines(y,front,rear,color='#30383d',lw=10,label='Modeled extent' if i==0 else None)
    ax.hlines(y+.19,lo,hi,color=color,lw=3,label='Hypothetical 650 mm extent' if i==0 else None)
    ax.plot([lo,hi],[y+.19,y+.19],'|',color=color,ms=12,mew=2);ax.text(-.43,y+.05,name,ha='left',va='center',fontsize=10)
ax.axvline(0,color='#9ba9b0',lw=.8);ax.set_xlim(-.44,.44);ax.set_ylim(-.45,2.55)
ax.set_yticks([]);ax.set_xlabel('Front  ←   centered model Y (m)   →  rear');ax.set_title('Unresolved registration of published overall depth',loc='left')
ax.legend(loc='upper center',bbox_to_anchor=(0.5,-0.20),ncol=2,frameon=False,fontsize=8);ax.spines[['right','left','top']].set_visible(False)
fig.tight_layout();fig.savefig(ROOT/'research/depth-registration.png',dpi=150);plt.close(fig)
stage=Usd.Stage.CreateInMemory()
UsdGeom.SetStageUpAxis(stage,UsdGeom.Tokens.z);UsdGeom.SetStageMetersPerUnit(stage,1)
root=UsdGeom.Xform.Define(stage,'/DepthRegistration');stage.SetDefaultPrim(root.GetPrim())
root.GetPrim().CreateAttribute('study:status',Sdf.ValueTypeNames.String,custom=True).Set('Hypothetical reference envelopes, not physical geometry or colliders')
for name,(lo,hi) in cases.items():
    curves=UsdGeom.BasisCurves.Define(stage,'/DepthRegistration/'+name)
    points=[]
    for z in (0,2.387):
        points.extend([(-.4005,lo,z),(.4005,lo,z),(.4005,hi,z),(-.4005,hi,z),(-.4005,lo,z)])
    for x,y in [(-.4005,lo),(.4005,lo),(.4005,hi),(-.4005,hi)]:points.extend([(x,y,0),(x,y,2.387)])
    curves.CreateTypeAttr('linear');curves.CreateCurveVertexCountsAttr([5,5,2,2,2,2]);curves.CreatePointsAttr([Gf.Vec3f(*p) for p in points]);curves.CreateWidthsAttr([.003]);curves.SetWidthsInterpolation('constant');curves.CreatePurposeAttr('guide')
stage.GetRootLayer().Export(str(ROOT/'research/depth-registration-guides.usda'))
print(json.dumps(result,indent=2))
