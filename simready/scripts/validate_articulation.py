import collections,hashlib,json,pathlib,re
import numpy as np
from scipy.spatial import ConvexHull
from scipy.optimize import linprog
from pxr import Gf,Usd,UsdGeom,UsdPhysics,UsdShade,UsdSemantics,UsdUtils
ROOT=pathlib.Path(__file__).resolve().parents[1]
PREV=ROOT/'source/build-inputs';src=ROOT/'source/seca-scale-up-ultra-original.blend'
asset=ROOT/'asset/seca_scale_up_ultra_articulated/usd/seca_scale_up_ultra_articulated.usda'
data=json.loads((ROOT/'validation/articulation-model.json').read_text());receipt=json.loads((PREV/'visual-export.json').read_text())
stage=Usd.Stage.Open(str(asset));root=stage.GetDefaultPrim();prims=list(stage.Traverse());cache=UsdGeom.XformCache(Usd.TimeCode.Default())
entries=[]
for group,names in data['body_groups'].items():
    for n in names:
        slug='EXPORT_'+re.sub('[^0-9A-Za-z_]','_',n)
        parent=stage.GetPrimAtPath('/SecaScaleUpUltra/Links/'+group+'/Visual/'+slug)
        if not parent.IsValid():entries.append({'name':n,'group':group,'missing':True});continue
        meshes=[p for p in parent.GetChildren() if p.IsA(UsdGeom.Mesh)]
        points=[];materials=[]
        for p in meshes:
            xform=cache.GetLocalToWorldTransform(p)
            points.extend(list(xform.Transform(v)) for v in UsdGeom.Mesh(p).GetPointsAttr().Get())
            mat=UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial()[0];materials.append(mat.GetPrim().GetName() if mat else None)
        if not points:entries.append({'name':n,'group':group,'empty':True});continue
        points=np.asarray(points);actual=np.stack([points.min(axis=0),points.max(axis=0)])
        expected=np.asarray(receipt['geometry'][n]['bounds_m']);expected[:,1]-=receipt['center_y_m']
        def slugmat(x):
            s=re.sub('[^0-9A-Za-z_]','_',x);return ('_'+s) if s[0].isdigit() else s
        expected_mat=[slugmat(x['name']) for x in receipt['geometry'][n]['material_slots'] if x['name']]
        entries.append({'name':n,'group':group,'max_abs_error_m':float(np.max(np.abs(actual-expected))),
                        'material_match':not expected_mat or all(m in expected_mat for m in materials)})

joints=[]
for desc in data['joints']:
    p=stage.GetPrimAtPath('/SecaScaleUpUltra/Joints/'+desc['name']);j=UsdPhysics.RevoluteJoint(p)
    a=j.GetBody0Rel().GetTargets()[0];b=j.GetBody1Rel().GetTargets()[0]
    ma=cache.GetLocalToWorldTransform(stage.GetPrimAtPath(a));mb=cache.GetLocalToWorldTransform(stage.GetPrimAtPath(b))
    p0=ma.Transform(j.GetLocalPos0Attr().Get());p1=mb.Transform(j.GetLocalPos1Attr().Get())
    joints.append({'name':desc['name'],'body0':str(a),'body1':str(b),'axis':str(j.GetAxisAttr().Get()),
                   'world_joint_frame_error_m':float((p0-p1).GetLength()),
                   'disabled_connected_collisions':not j.GetCollisionEnabledAttr().Get()})
bodies=[p for p in prims if p.HasAPI(UsdPhysics.RigidBodyAPI)]
masses={str(p.GetPath()):UsdPhysics.MassAPI(p).GetMassAttr().Get() for p in bodies}
inertias={str(p.GetPath()):list(UsdPhysics.MassAPI(p).GetDiagonalInertiaAttr().Get()) for p in bodies}
axes={str(p.GetPath()):UsdPhysics.MassAPI(p).GetPrincipalAxesAttr().Get() for p in bodies}
inertias_valid=all(all(np.isfinite(x) and x>0 for x in d) and all(d[i]<=d[(i+1)%3]+d[(i+2)%3]+1e-7 for i in range(3)) for d in inertias.values())
axes_valid=all(abs(sum(float(x)**2 for x in [q.GetReal(),*q.GetImaginary()])-1)<1e-5 for q in axes.values())
joints_correct=all(j['body0'].endswith('/'+desc['body0']) and j['body1'].endswith('/'+desc['body1']) and j['axis']==desc['axis'] for j,desc in zip(joints,data['joints']))
limits_correct=True
for desc in data['joints']:
    joint=UsdPhysics.RevoluteJoint(stage.GetPrimAtPath('/SecaScaleUpUltra/Joints/'+desc['name']))
    if desc['limits_deg']:
        limits_correct &= abs(joint.GetLowerLimitAttr().Get()-desc['limits_deg'][0])<1e-4 and abs(joint.GetUpperLimitAttr().Get()-desc['limits_deg'][1])<1e-4
    else:
        limits_correct &= not joint.GetLowerLimitAttr().HasAuthoredValueOpinion() and not joint.GetUpperLimitAttr().HasAuthoredValueOpinion()
visuals=[p for p in prims if p.IsA(UsdGeom.Mesh) and '/Visual/' in str(p.GetPath())]
colliders=[p for p in prims if p.IsA(UsdGeom.Mesh) and p.HasAPI(UsdPhysics.CollisionAPI)]
materials=[UsdShade.Material(p) for p in prims if p.IsA(UsdShade.Material) and '/Visual/' in str(p.GetPath())]
bad_collider=[]
for p in colliders:
    m=UsdGeom.Mesh(p);pts=m.GetPointsAttr().Get();counts=m.GetFaceVertexCountsAttr().Get();indices=m.GetFaceVertexIndicesAttr().Get();edges=collections.Counter()
    for a,b,c in zip(indices[::3],indices[1::3],indices[2::3]):
        for edge in [(a,b),(b,c),(c,a)]:edges[tuple(sorted(edge))]+=1
    if any(v!=2 for v in edges.values()) or any(n!=3 for n in counts) or not m.GetExtentAttr().Get() or not m.GetNormalsAttr().Get():bad_collider.append(str(p.GetPath()))
    if UsdGeom.Imageable(p).ComputePurpose()!='guide' or not UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial('physics')[0]:bad_collider.append(str(p.GetPath())+' purpose/material')

# Identify pairs whose connected-body contacts are suppressed by the joints.
filtered={frozenset((x['body0'],x['body1'])) for x in data['joints'] if not x['connected_collision_enabled']}
hulls=[]
for c in data['colliders']:
    pts=np.asarray(c['points_local_m'])+np.asarray(data['body_pivots_m'][c['body']]);hulls.append((c,ConvexHull(pts).equations,pts.min(axis=0),pts.max(axis=0)))
intersections=[]
for i,(a,ha,amin,amax) in enumerate(hulls):
    for b,hb,bmin,bmax in hulls[i+1:]:
        if a['body']==b['body'] or frozenset((a['body'],b['body'])) in filtered:continue
        if np.any(amax<=bmin) or np.any(bmax<=amin):continue
        h=np.concatenate([ha,hb]);A=np.column_stack([h[:,:3],np.linalg.norm(h[:,:3],axis=1)])
        opt=linprog([0,0,0,-1],A_ub=A,b_ub=-h[:,3],bounds=[(None,None)]*3+[(0,None)],method='highs')
        if opt.success and opt.x[3]>1e-5:intersections.append({'a':a['name'],'b':b['name'],'bodies':[a['body'],b['body']],'inscribed_overlap_radius_m':float(opt.x[3])})
filtered_prims=[p for p in prims if p.HasAPI(UsdPhysics.FilteredPairsAPI)]
_,_,unresolved=UsdUtils.ComputeAllDependencies(str(asset))
overlay=asset.parent/'layers/illustrative_driven.usda';driven=Usd.Stage.Open(str(overlay))
_,_,overlay_unresolved=UsdUtils.ComputeAllDependencies(str(overlay))
drive_checks={}
for name,expected in data['provisional_display_drives'].items():
    base_prim=stage.GetPrimAtPath('/SecaScaleUpUltra/Joints/'+name)
    prim=driven.GetPrimAtPath('/SecaScaleUpUltra/Joints/'+name)
    d=UsdPhysics.DriveAPI(prim,'angular')
    drive_checks[name]={'absent_from_base':not base_prim.HasAPI(UsdPhysics.DriveAPI,'angular'),
      'present_in_overlay':prim.HasAPI(UsdPhysics.DriveAPI,'angular'),
      'type_force':d.GetTypeAttr().Get()=='force',
      'target_zero':abs(d.GetTargetPositionAttr().Get())<1e-7 and abs(d.GetTargetVelocityAttr().Get())<1e-7,
      'stiffness':abs(d.GetStiffnessAttr().Get()-expected['stiffness_Nm_per_degree'])<1e-6,
      'damping':abs(d.GetDampingAttr().Get()-expected['damping_Nm_s_per_degree'])<1e-6,
      'force_cap':abs(d.GetMaxForceAttr().Get()-expected['max_torque_Nm'])<1e-6}
for name in ('LeftWheel','RightWheel'):
    drive_checks[name]={'no_drive_in_base_or_overlay':not stage.GetPrimAtPath('/SecaScaleUpUltra/Joints/'+name).HasAPI(UsdPhysics.DriveAPI,'angular') and not driven.GetPrimAtPath('/SecaScaleUpUltra/Joints/'+name).HasAPI(UsdPhysics.DriveAPI,'angular')}
checks={'source_blend_unchanged':hashlib.sha256(src.read_bytes()).hexdigest()=='57e64f249073c472abacbc942eb990a76657a26333f56e80ec922815e7c5525d',
 'all_272_component_bounds_match':len(entries)==272 and all('max_abs_error_m'in e and e['max_abs_error_m']<1e-5 for e in entries),
 'all_source_material_bindings_match':all(e.get('material_match',False) for e in entries),
 'five_bodies_four_revolute_joints':len(bodies)==5 and len(joints)==4,
 'mass_sums_to_29kg':abs(sum(masses.values())-29)<1e-5,
 'joint_frames_coincident':all(j['world_joint_frame_error_m']<1e-6 for j in joints),
 'joint_graph_axes_and_limits_match_study':joints_correct and limits_correct,
 'finite_physical_inertia_and_normalized_axes':inertias_valid and axes_valid,
 'connected_pair_collisions_disabled':all(j['disabled_connected_collisions'] for j in joints),
 'only_display_mount_pair_explicitly_filtered':len(filtered_prims)==1 and str(filtered_prims[0].GetPath())=='/SecaScaleUpUltra/Links/Display_Tilt/Colliders/Display' and UsdPhysics.FilteredPairsAPI(filtered_prims[0]).GetFilteredPairsRel().GetTargets()==[stage.GetPrimAtPath('/SecaScaleUpUltra/Links/Base/Colliders/Display_Arm').GetPath()],
 'no_unfiltered_proxy_overlap_over_10um':not intersections,
 'closed_collider_meshes_and_bindings':len(colliders)==42 and not bad_collider,
 'visual_materials_have_surface_and_labels':all(m.ComputeSurfaceSource()[0] and UsdSemantics.LabelsAPI(m.GetPrim(),'material').GetLabelsAttr().Get() for m in materials),
 'no_unresolved_dependencies':not unresolved and not overlay_unresolved,
 'drives_only_in_optional_overlay':all(all(c.values()) for c in drive_checks.values()),
 'usd_meters_z_up':UsdGeom.GetStageMetersPerUnit(stage)==1 and UsdGeom.GetStageUpAxis(stage)=='Z'}
result={'checks':checks,'component_checks':entries,'max_component_bound_error_m':max(e.get('max_abs_error_m',0) for e in entries),
 'bodies':masses,'inertia_kg_m2':inertias,'joints':joints,'drive_checks':drive_checks,'unfiltered_proxy_intersections':intersections,'bad_colliders':bad_collider,
 'visual_meshes':len(visuals),'collider_meshes':len(colliders),'visual_materials':len(materials),'unresolved':list(unresolved),
 'scope':'USD structure, saved-pose component bounds, link frames and convex proxy intersections; no dynamic runtime or physical-device validation.'}
(ROOT/'validation/articulation-checks.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='component_checks'},indent=2,default=str))
assert all(checks.values())
