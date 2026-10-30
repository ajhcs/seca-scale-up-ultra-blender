"""Author a provisional five-body USD assembly from the static derivative."""
import json,math,pathlib,re
import numpy as np
from scipy.spatial.transform import Rotation
from pxr import Gf,Kind,Sdf,Usd,UsdGeom,UsdPhysics,UsdSemantics,UsdShade

ROOT=pathlib.Path(__file__).resolve().parents[1]
PREV=ROOT/'source/build-inputs'
MODEL=PREV/'native-inspection.json'
ASSET=ROOT/'asset/seca_scale_up_ultra_articulated/usd';LAYERS=ASSET/'layers'
LAYERS.mkdir(parents=True,exist_ok=True)
receipt=json.loads((PREV/'visual-export.json').read_text())
physics=json.loads((PREV/'physics-model.json').read_text())
native=json.loads(MODEL.read_text());objects={o['name']:o for o in native['objects']}
source=Usd.Stage.Open(str(PREV/'visual.usdc'))
source_layer=source.GetRootLayer();source_root=source.GetDefaultPrim()
def export_name(name):return 'EXPORT_'+re.sub('[^0-9A-Za-z_]','_',name)
def has_ancestor(name,target):
    parent=objects[name]['parent'];seen=set()
    while parent and parent in objects and parent not in seen:
        if parent==target:return True
        seen.add(parent);parent=objects[parent]['parent']
    return False
groups={'Base':[],'Wheel_L':[],'Wheel_R':[],'Display_Yaw':[],'Display_Tilt':[]}
for name in receipt['geometry']:
    if has_ancestor(name,'CONTROL • wheel L'):group='Wheel_L'
    elif has_ancestor(name,'CONTROL • wheel R'):group='Wheel_R'
    elif has_ancestor(name,'CONTROL • display tilt and rotation'):group='Display_Tilt'
    elif name=='Display bottom swivel housing':group='Display_Yaw'
    else:group='Base'
    groups[group].append(name)
assert [len(groups[x]) for x in ['Wheel_L','Wheel_R','Display_Yaw','Display_Tilt']]==[1,1,1,38]

for group,names in groups.items():
    dst=Usd.Stage.CreateNew(str(LAYERS/(group+'.usdc')))
    UsdGeom.SetStageUpAxis(dst,'Z');UsdGeom.SetStageMetersPerUnit(dst,1)
    target=UsdGeom.Xform.Define(dst,'/VisualSource');dst.SetDefaultPrim(target.GetPrim())
    UsdGeom.Scope.Define(dst,'/VisualSource/_materials')
    mats=set()
    for name in names:
        path=Sdf.Path('/VisualSource/'+export_name(name))
        prim=source.GetPrimAtPath(path);assert prim.IsValid(),name
        for child in Usd.PrimRange(prim):
            if child.IsA(UsdGeom.Gprim):
                mat=UsdShade.MaterialBindingAPI(child).ComputeBoundMaterial()[0]
                if mat:mats.add(str(mat.GetPath()))
        assert Sdf.CopySpec(source_layer,path,dst.GetRootLayer(),path),name
    for path in sorted(mats):assert Sdf.CopySpec(source_layer,Sdf.Path(path),dst.GetRootLayer(),Sdf.Path(path)),path
    dst.GetRootLayer().Save()

stage=Usd.Stage.CreateNew(str(ASSET/'seca_scale_up_ultra_articulated.usda'))
UsdGeom.SetStageUpAxis(stage,'Z');UsdGeom.SetStageMetersPerUnit(stage,1);UsdPhysics.SetStageKilogramsPerUnit(stage,1)
root=UsdGeom.Xform.Define(stage,'/SecaScaleUpUltra').GetPrim();stage.SetDefaultPrim(root)
Usd.ModelAPI(root).SetKind(Kind.Tokens.component)
UsdPhysics.ArticulationRootAPI.Apply(root)
UsdSemantics.LabelsAPI.Apply(root,'class').CreateLabelsAttr(['medical_weighing_station'])
UsdSemantics.LabelsAPI.Apply(root,'wikidata_qcode').CreateLabelsAttr(['Q1421918'])
root.CreateAttribute('seca:study',Sdf.ValueTypeNames.String,custom=True).Set('Provisional multibody study: pivot geometry, mass distribution and display limits are unmeasured')
offset=float(receipt['center_y_m'])
pivot={'Base':np.array([0.,0.,0.]),'Wheel_L':np.array([-.230,.267-offset,.043]),
       'Wheel_R':np.array([.230,.267-offset,.043]),'Display_Yaw':np.array([.184,.180-offset,1.383886028]),
       'Display_Tilt':np.array([.184,.180-offset,1.383886028])}
base_parts=[p for p in physics['components'] if p['name'] in ['base','handrail','column','head']]
base_mass=sum(p['mass_kg'] for p in base_parts)
base_com=sum(p['mass_kg']*np.asarray(p['center_m']) for p in base_parts)/base_mass
base_inertia=np.zeros((3,3))
for p in base_parts:
    m=p['mass_kg'];d=np.array(p['box_size_m']);delta=np.asarray(p['center_m'])-base_com
    base_inertia+=np.diag([m*(d[1]**2+d[2]**2)/12,m*(d[0]**2+d[2]**2)/12,m*(d[0]**2+d[1]**2)/12])+m*((delta@delta)*np.eye(3)-np.outer(delta,delta))
ev,axes=np.linalg.eigh(base_inertia)
if np.linalg.det(axes)<0:axes[:,0]*=-1
qx,qy,qz,qw=Rotation.from_matrix(axes).as_quat()
wheel_m=.1;rad=.043;width=.027
wheel_inertia=[wheel_m*rad**2/2,wheel_m*(3*rad**2+width**2)/12,wheel_m*(3*rad**2+width**2)/12]
yaw_m=.1;yaw_radius=.015;yaw_height=.012
yaw_inertia=[yaw_m*(3*yaw_radius**2+yaw_height**2)/12]*2+[yaw_m*yaw_radius**2/2]
display_m=.9;display_dims=np.array([.081,.0204,.1332])
display_inertia=[display_m*(display_dims[1]**2+display_dims[2]**2)/12,
                 display_m*(display_dims[0]**2+display_dims[2]**2)/12,
                 display_m*(display_dims[0]**2+display_dims[1]**2)/12]
body_spec={'Base':(base_mass,base_com,ev,[qw,qx,qy,qz]),
           'Wheel_L':(wheel_m,np.zeros(3),wheel_inertia,[1,0,0,0]),
           'Wheel_R':(wheel_m,np.zeros(3),wheel_inertia,[1,0,0,0]),
           'Display_Yaw':(yaw_m,np.array([0,0,-.006]),yaw_inertia,[1,0,0,0]),
           'Display_Tilt':(display_m,np.array([0,-.0048,.066]),display_inertia,[1,0,0,0])}
assert abs(sum(v[0] for v in body_spec.values())-29)<1e-8
UsdGeom.Scope.Define(stage,'/SecaScaleUpUltra/Links')
body_paths={}
for name,(mass,com,inert,q) in body_spec.items():
    path='/SecaScaleUpUltra/Links/'+name;body_paths[name]=path
    body=UsdGeom.Xform.Define(stage,path);body.AddTranslateOp().Set(Gf.Vec3d(*pivot[name]));body.AddOrientOp().Set(Gf.Quatf(1))
    prim=body.GetPrim();UsdPhysics.RigidBodyAPI.Apply(prim).CreateRigidBodyEnabledAttr(True)
    api=UsdPhysics.MassAPI.Apply(prim);api.CreateMassAttr(mass);api.CreateCenterOfMassAttr(Gf.Vec3f(*com));api.CreateDiagonalInertiaAttr(Gf.Vec3f(*inert));api.CreatePrincipalAxesAttr(Gf.Quatf(float(q[0]),Gf.Vec3f(*map(float,q[1:]))))
    visual=UsdGeom.Xform.Define(stage,path+'/Visual');visual.GetPrim().GetReferences().AddReference('./layers/'+name+'.usdc','/VisualSource')
    visual.AddTranslateOp().Set(Gf.Vec3d(*(np.array([0.,-offset,0.])-pivot[name])))
    UsdGeom.Scope.Define(stage,path+'/Colliders')

UsdGeom.Scope.Define(stage,'/SecaScaleUpUltra/PhysicsMaterials')
materials={}
for name,st,dy in [('Rubber',.70,.55),('Coating',.50,.40),('Glass',.40,.30),('Plastic',.45,.35)]:
    mat=UsdShade.Material.Define(stage,'/SecaScaleUpUltra/PhysicsMaterials/'+name)
    api=UsdPhysics.MaterialAPI.Apply(mat.GetPrim());api.CreateStaticFrictionAttr(st);api.CreateDynamicFrictionAttr(dy);api.CreateRestitutionAttr(.02)
    UsdSemantics.LabelsAPI.Apply(mat.GetPrim(),'material').CreateLabelsAttr(['estimated_'+name.lower()]);materials[name]=mat

collider_map=[]
def add_collider(body_name,name,points,faces,material):
    path=body_paths[body_name]+'/Colliders/'+name;mesh=UsdGeom.Mesh.Define(stage,path)
    pts=np.array(points,dtype=float)-pivot[body_name]
    mesh.CreatePointsAttr([Gf.Vec3f(*x) for x in pts]);mesh.CreateFaceVertexCountsAttr([3]*len(faces));mesh.CreateFaceVertexIndicesAttr([i for f in faces for i in f])
    mesh.CreateSubdivisionSchemeAttr('none');mesh.CreatePurposeAttr('guide')
    mesh.CreateExtentAttr([Gf.Vec3f(*pts.min(axis=0)),Gf.Vec3f(*pts.max(axis=0))])
    normals=[]
    for a,b,c in faces:
        n=np.cross(pts[b]-pts[a],pts[c]-pts[a]);assert np.linalg.norm(n)>1e-14;normals.append(Gf.Vec3f(*(n/np.linalg.norm(n))))
    mesh.CreateNormalsAttr(normals);mesh.SetNormalsInterpolation('uniform')
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim()).CreateCollisionEnabledAttr(True)
    UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim()).CreateApproximationAttr('convexHull')
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(materials[material],materialPurpose='physics')
    collider_map.append({'body':body_name,'name':name,'points_local_m':pts.tolist(),'faces':faces,'material':material})
for c in physics['colliders']:
    name=c['name'];body='Wheel_L' if name=='Wheel_L' else 'Wheel_R' if name=='Wheel_R' else 'Display_Tilt' if name=='Display' else 'Base'
    points=np.array(c['points'],dtype=float)
    if name=='Display':points[:,2]=np.maximum(points[:,2],1.3845)
    add_collider(body,name,points,c['faces'],c['material'])
# Model the small, provisional turning collar as a closed 16-sided cylinder.
sides=16;center=pivot['Display_Yaw']+np.array([0,0,-.006]);pts=[]
for z in (-.006,.006):
    for i in range(sides):
        a=2*math.pi*i/sides;pts.append([center[0]+.015*math.cos(a),center[1]+.015*math.sin(a),center[2]+z])
faces=[]
for i in range(sides):
    j=(i+1)%sides;faces.extend([[i,j,sides+j],[i,sides+j,sides+i]])
for i in range(1,sides-1):faces.extend([[0,i+1,i],[sides,sides+i,sides+i+1]])
add_collider('Display_Yaw','Collar',pts,faces,'Coating')

UsdGeom.Scope.Define(stage,'/SecaScaleUpUltra/Joints')
joint_specs=[('LeftWheel','Base','Wheel_L','X',None),('RightWheel','Base','Wheel_R','X',None),
             ('DisplaySwivel','Base','Display_Yaw','Z',(-math.degrees(.6),math.degrees(.6))),
             ('DisplayTilt','Display_Yaw','Display_Tilt','X',(-math.degrees(.4),math.degrees(.4)))]
for name,a,b,axis,limits in joint_specs:
    joint=UsdPhysics.RevoluteJoint.Define(stage,'/SecaScaleUpUltra/Joints/'+name)
    joint.CreateBody0Rel().SetTargets([body_paths[a]]);joint.CreateBody1Rel().SetTargets([body_paths[b]])
    joint.CreateLocalPos0Attr(Gf.Vec3f(*(pivot[b]-pivot[a])));joint.CreateLocalPos1Attr(Gf.Vec3f(0,0,0))
    joint.CreateLocalRot0Attr(Gf.Quatf(1));joint.CreateLocalRot1Attr(Gf.Quatf(1))
    joint.CreateAxisAttr(axis);joint.CreateCollisionEnabledAttr(False)
    if limits:joint.CreateLowerLimitAttr(limits[0]);joint.CreateUpperLimitAttr(limits[1])

# The display's simplified box and its mounting arm intentionally meet at the
# pivot.  Filter only that collider pair; the display remains eligible to
# collide with the mast, rail, and all other nonadjacent base colliders.
display_collider=stage.GetPrimAtPath(body_paths['Display_Tilt']+'/Colliders/Display')
arm_collider=Sdf.Path(body_paths['Base']+'/Colliders/Display_Arm')
UsdPhysics.FilteredPairsAPI.Apply(display_collider).CreateFilteredPairsRel().SetTargets([arm_collider])

material_labels={};part_labels={}
for prim in list(stage.Traverse()):
    path=str(prim.GetPath());n=prim.GetName().lower()
    if '/Visual/' in path and prim.IsA(UsdShade.Material):
        if 'glass' in n and 'bezel' not in n:label='glass'
        elif any(x in n for x in ['aluminium','metal']):label='metal'
        elif any(x in n for x in ['elastomer','tread']):label='rubber'
        elif 'polymer' in n:label='plastic'
        else:label='unknown'
        UsdSemantics.LabelsAPI.Apply(prim,'material').CreateLabelsAttr([label]);material_labels[path]=label
    if '/Visual/EXPORT_' in path and prim.GetTypeName()=='Xform':
        if '/Wheel_' in path:label='transport_wheel_assembly'
        elif '/Display_' in path:label='display_assembly'
        elif 'footprint' in n or 'glass_stripe' in n or 'bearclaw' in n or 'platform_chassis' in n:label='weighing_platform'
        elif 'handrail' in n or n.startswith('export_455_'):label='support_handrail'
        elif 'leveling_foot' in n or 'foot_lock' in n:label='leveling_foot'
        elif 'wheel' in n:label='transport_wheel_assembly'
        elif 'display' in n or n.startswith('export_sim_') or 'screen' in n:label='display_assembly'
        elif 'sensor' in n or 'head_' in n or 'aperture' in n or 'speaker_grille' in n:label='ultrasonic_head'
        elif n.startswith('export_257_'):label='height_column'
        else:continue
        UsdSemantics.LabelsAPI.Apply(prim,'part').CreateLabelsAttr([label]);part_labels[path]=label
extent=np.array(receipt['bounds_m'][1])-np.array(receipt['bounds_m'][0])
stage.GetRootLayer().customLayerData={'SimReady_Metadata':{'author':'seca-scale-up-ultra-blender contributors',
    'asset_name':'seca Scale-up Ultra independent articulated reconstruction','asset_type':'prop','asset_license':'CC-BY-4.0',
    'category':'medical equipment','source_file':'https://github.com/ajhcs/seca-scale-up-ultra-blender/tree/ab13079013d5a4869acc56ac22884aa226b19502',
    'usd_date_generated':'2026-10-30','qcode':'Q1421918','rigid_body_count':5,'asset_extents':Gf.Vec3f(*extent),'mass':29.0}}
stage.GetRootLayer().Save()
summary={'body_groups':groups,'body_pivots_m':{k:v.tolist() for k,v in pivot.items()},
 'body_mass_kg':{k:v[0] for k,v in body_spec.items()},'body_com_local_m':{k:list(v[1]) for k,v in body_spec.items()},
 'body_diagonal_inertia_kg_m2':{k:list(v[2]) for k,v in body_spec.items()},'body_principal_axes_wxyz':{k:list(v[3]) for k,v in body_spec.items()},
 'joints':[{'name':n,'body0':a,'body1':b,'axis':axis,'limits_deg':lim,'connected_collision_enabled':False} for n,a,b,axis,lim in joint_specs],
 'colliders':collider_map,'filtered_collider_pairs':[['Display_Tilt/Display','Base/Display_Arm']],
 'provisional_display_drives':{'DisplaySwivel':{'stiffness_Nm_per_degree':.05,'damping_Nm_s_per_degree':.005,'max_torque_Nm':1.0,'target_deg':0},
                                'DisplayTilt':{'stiffness_Nm_per_degree':.10,'damping_Nm_s_per_degree':.010,'max_torque_Nm':1.5,'target_deg':0}},
 'part_labels':len(part_labels),'visual_material_labels':len(material_labels),
 'assumptions':['Display swivel and tilt axes, ±0.6 rad and ±0.4 rad stops are modeled study ranges, not verified manufacturer joints or stops.',
   'Wheel radii, pivots, mass distribution, friction and colliders are inferred from the reconstruction and not measured.',
   'The base stage has unpowered joints; an optional illustrative drive overlay is not evidence of real motors, springs or hinge friction.',
   'Attached pairs have collision disabled by joint policy; one display-to-mount proxy pair is additionally filtered, while display-to-mast and display-to-rail remain enabled.',
   'Display cable is a static approximation and does not deform with articulation.',
   'The display collider lower face is clipped at z=1.3845 m to avoid proxy overlap with the mounting arm.']}
(ROOT/'validation/articulation-model.json').write_text(json.dumps(summary,indent=2,default=float)+'\n')
print(json.dumps({'body_groups':{k:len(v) for k,v in groups.items()},'masses':summary['body_mass_kg'],
                  'joints':summary['joints'],'colliders':len(collider_map),'parts_labeled':len(part_labels),'materials_labeled':len(material_labels)},indent=2))
