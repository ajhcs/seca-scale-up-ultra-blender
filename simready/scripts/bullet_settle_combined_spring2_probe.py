"""Multibody drop with illustrative Bullet springs, reconstructed from USD proxies."""
import bpy,json,math,pathlib
from mathutils import Vector
ROOT=pathlib.Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'validation/articulation-model.json').read_text())
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
scene.render.fps=24;scene.frame_start=1;scene.frame_end=181;scene.gravity=(0,0,-9.81)
bodies={};local_vertices={};drop=Vector((0,0,.10))
for name,mass in data['body_mass_kg'].items():
    pivot=Vector(data['body_pivots_m'][name]);com=Vector(data['body_com_local_m'][name])
    bpy.ops.mesh.primitive_cube_add(size=.01,location=pivot+com+drop);body=bpy.context.object;body.name='Body '+name
    bpy.ops.rigidbody.object_add();body.rigid_body.type='ACTIVE';body.rigid_body.collision_shape='COMPOUND';body.rigid_body.mass=mass
    body.rigid_body.friction=.55;body.rigid_body.restitution=.02;body.rigid_body.use_margin=True;body.rigid_body.collision_margin=.0005
    bodies[name]=body;local_vertices[name]=[]
    for item in data['colliders']:
        if item['body']!=name or (name=='Base' and item['name']=='Display_Arm'):continue
        pts=[tuple(Vector(p)-com) for p in item['points_local_m']];local_vertices[name].extend(Vector(p) for p in pts)
        mesh=bpy.data.meshes.new(item['name']);mesh.from_pydata(pts,[],item['faces']);mesh.update()
        obj=bpy.data.objects.new(name+'_'+item['name'],mesh);scene.collection.objects.link(obj);obj.parent=body
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.rigidbody.object_add();obj.rigid_body.type='ACTIVE';obj.rigid_body.collision_shape='CONVEX_HULL';obj.rigid_body.use_margin=True;obj.rigid_body.collision_margin=.0005
for desc in data['joints']:
    bpy.ops.object.empty_add(location=Vector(data['body_pivots_m'][desc['body1']])+drop);ob=bpy.context.object
    has_spring = desc['name'] in data['provisional_display_drives']
    # Generic spring along local X; plain hinges rotate about their local Z.
    if has_spring and desc['axis']=='Z':ob.rotation_euler.y=-math.pi/2
    if not has_spring and desc['axis']=='X':ob.rotation_euler.y=math.pi/2
    bpy.ops.rigidbody.constraint_add();c=ob.rigid_body_constraint
    c.type='GENERIC_SPRING' if has_spring else 'HINGE';c.object1=bodies[desc['body0']];c.object2=bodies[desc['body1']];c.disable_collisions=True
    if has_spring:
        c.spring_type='SPRING2'
        for axis in 'xyz':
            setattr(c,'use_limit_lin_'+axis,True);setattr(c,'limit_lin_'+axis+'_lower',0);setattr(c,'limit_lin_'+axis+'_upper',0)
        for axis in 'yz':
            setattr(c,'use_limit_ang_'+axis,True);setattr(c,'limit_ang_'+axis+'_lower',0);setattr(c,'limit_ang_'+axis+'_upper',0)
        c.use_limit_ang_x=True;c.limit_ang_x_lower=math.radians(desc['limits_deg'][0]);c.limit_ang_x_upper=math.radians(desc['limits_deg'][1])
        c.use_spring_ang_x=True
        c.spring_stiffness_ang_x=data['provisional_display_drives'][desc['name']]['stiffness_Nm_per_degree']*180/math.pi
        c.spring_damping_ang_x=.5
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-.1));floor=bpy.context.object;floor.scale=(6,6,.2)
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);bpy.ops.rigidbody.object_add()
floor.rigid_body.type='PASSIVE';floor.rigid_body.collision_shape='BOX';floor.rigid_body.friction=.55;floor.rigid_body.restitution=.02
scene.rigidbody_world.substeps_per_frame=20;scene.rigidbody_world.solver_iterations=100
frames=[]
for f in range(1,182):
    scene.frame_set(f);dg=bpy.context.evaluated_depsgraph_get();m={k:v.evaluated_get(dg).matrix_world.copy() for k,v in bodies.items()}
    low=min((m[k]@p).z for k,pts in local_vertices.items() for p in pts)
    q=m['Display_Yaw'].to_quaternion().inverted()@m['Display_Tilt'].to_quaternion()
    tilt=2*math.atan2(q.x,q.w)
    errors=[]
    for j in data['joints']:
        a=j['body0'];b=j['body1'];p0=Vector(data['body_pivots_m'][b])-Vector(data['body_pivots_m'][a])-Vector(data['body_com_local_m'][a]);p1=-Vector(data['body_com_local_m'][b])
        errors.append(((m[a]@p0)-(m[b]@p1)).length)
    frames.append({'frame':f,'base_center_m':list(m['Base'].translation),'lowest_proxy_z_m':low,'display_tilt_rad':tilt,'max_joint_anchor_error_m':max(errors)})
tail=frames[-25:];final=frames[-1];tail_range=max(f['lowest_proxy_z_m'] for f in tail)-min(f['lowest_proxy_z_m'] for f in tail)
checks={'fell':frames[20]['base_center_m'][2]<frames[0]['base_center_m'][2]-.02,
 'floor_penetration_under_10mm':min(x['lowest_proxy_z_m'] for x in frames)>-.01,
 'settled_last_second_under_5mm':tail_range<.005,
 'joint_anchor_error_under_5mm':max(x['max_joint_anchor_error_m'] for x in frames)<.005,
 'display_tilt_within_study_limits':max(abs(x['display_tilt_rad']) for x in frames)<.45,
 'final_tilt_under_0_15rad':abs(final['display_tilt_rad'])<.15}
result={'engine':'Blender Bullet','scenario':'Five-body 10 cm drop onto level ground with illustrative combined SPRING2 display joints','checks':checks,
 'final_display_tilt_rad':final['display_tilt_rad'],'tail_z_range_m':tail_range,'frames':frames,
 'scope':'Reconstructed joints and colliders with gravity, one body friction and qualitative spring constraints; mounting arm omitted because Bullet compound cannot reproduce the USD per-shape filter; inferred inertia and spring model are not equivalent to USD drives or PhysX.'}
(ROOT/'validation/bullet-settle-combined-spring2.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='frames'},indent=2));assert all(checks.values())
