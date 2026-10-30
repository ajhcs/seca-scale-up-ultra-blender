"""Reconstruct the USD link graph in Bullet and drive each joint both ways.

This checks a corresponding Bullet setup, not the USD PhysX runtime.
"""
import bpy,json,math,pathlib
from mathutils import Vector
ROOT=pathlib.Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'validation/articulation-model.json').read_text())
probes=[]
for target in data['joints']:
  for direction in (-1,1):
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
    scene.render.fps=24;scene.frame_start=1
    is_wheel=target['name'] in ('LeftWheel','RightWheel');scene.frame_end=181 if is_wheel else 121
    scene.gravity=(0,0,0)
    bodies={}
    for name,mass in data['body_mass_kg'].items():
        pivot=Vector(data['body_pivots_m'][name]);com=Vector(data['body_com_local_m'][name])
        bpy.ops.mesh.primitive_cube_add(size=.01,location=pivot+com)
        body=bpy.context.object;body.name='Body '+name
        bpy.ops.rigidbody.object_add();body.rigid_body.type='ACTIVE';body.rigid_body.collision_shape='COMPOUND';body.rigid_body.mass=mass
        body.rigid_body.kinematic=(name=='Base');body.rigid_body.use_margin=True;body.rigid_body.collision_margin=.0005
        body.rigid_body.linear_damping=.04;body.rigid_body.angular_damping=.1
        bodies[name]=body
        for item in data['colliders']:
            if item['body']!=name:continue
            # Bullet's compound wrapper lacks USD's per-shape pair filter;
            # omit this one mounting shape for the probe so the display can
            # pass its hinge, while retaining mast and rail shapes.
            if name=='Base' and item['name']=='Display_Arm':continue
            points=[tuple(Vector(p)-com) for p in item['points_local_m']]
            mesh=bpy.data.meshes.new(item['name']);mesh.from_pydata(points,[],item['faces']);mesh.update()
            obj=bpy.data.objects.new(name+'_'+item['name'],mesh);scene.collection.objects.link(obj);obj.parent=body
            bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
            bpy.ops.rigidbody.object_add();obj.rigid_body.type='ACTIVE';obj.rigid_body.collision_shape='CONVEX_HULL';obj.rigid_body.use_margin=True;obj.rigid_body.collision_margin=.0005
    def constraint(name,desc,kind):
        loc=Vector(data['body_pivots_m'][desc['body1']]);bpy.ops.object.empty_add(location=loc)
        ob=bpy.context.object;ob.name=name
        # Blender hinge is local Z, angular motor is local X.
        if kind=='HINGE' and desc['axis']=='X':ob.rotation_euler.y=math.pi/2
        if kind=='MOTOR' and desc['axis']=='Z':ob.rotation_euler.y=-math.pi/2
        bpy.ops.rigidbody.constraint_add();c=ob.rigid_body_constraint;c.type=kind;c.object1=bodies[desc['body0']];c.object2=bodies[desc['body1']];c.disable_collisions=True
        if kind=='HINGE' and desc['limits_deg']:
            c.use_limit_ang_z=True;c.limit_ang_z_lower=math.radians(desc['limits_deg'][0]);c.limit_ang_z_upper=math.radians(desc['limits_deg'][1])
        if kind=='MOTOR':c.use_motor_ang=True;c.motor_ang_target_velocity=direction*(1.0 if is_wheel else .5);c.motor_ang_max_impulse=.2
    for desc in data['joints']:
        constraint('Hinge '+desc['name'],desc,'HINGE')
        if desc['name']==target['name']:constraint('Motor '+desc['name'],desc,'MOTOR')
    scene.rigidbody_world.substeps_per_frame=20;scene.rigidbody_world.solver_iterations=80
    parent=bodies[target['body0']];child=bodies[target['body1']];idx=0 if target['axis']=='X' else 2
    angles=[];anchor_errors=[];unwrapped=0.;previous=0.;frames=[]
    pivot0=Vector(data['body_pivots_m'][target['body0']]);pivot1=Vector(data['body_pivots_m'][target['body1']])
    local0=pivot1-pivot0-Vector(data['body_com_local_m'][target['body0']]);local1=-Vector(data['body_com_local_m'][target['body1']])
    for f in range(1,scene.frame_end+1):
        scene.frame_set(f);dg=bpy.context.evaluated_depsgraph_get()
        ma=parent.evaluated_get(dg).matrix_world.copy();mb=child.evaluated_get(dg).matrix_world.copy()
        a=ma.to_quaternion();b=mb.to_quaternion();q=a.inverted()@b
        anchor_errors.append(((ma@local0)-(mb@local1)).length)
        raw=2*math.atan2((q.x,q.y,q.z)[idx],q.w)
        delta=(raw-previous+math.pi)%(2*math.pi)-math.pi;unwrapped+=delta;previous=raw
        frames.append({'frame':f,'relative_angle_rad':unwrapped})
        angles.append(unwrapped)
    maxabs=max(abs(a) for a in angles);limits=target['limits_deg'];limit_rad=math.radians(max(abs(x) for x in limits)) if limits else None
    checks={'joint_reaches_one_revolution_or_90_percent_of_study_limit':maxabs>=(2*math.pi if is_wheel else .9*limit_rad),
            'study_limit_respected_with_0_05rad_tolerance':limit_rad is None or maxabs<=limit_rad+.05,
            'joint_anchor_error_under_5mm':max(anchor_errors)<.005,
            'finite_angles':all(math.isfinite(x) for x in angles)}
    probes.append({'joint':target['name'],'command_sign':direction,'final_angle_rad':angles[-1],
                   'max_abs_angle_rad':maxabs,'study_limit_rad':limit_rad,'max_anchor_error_m':max(anchor_errors),'checks':checks,'frames':frames})
report={'engine':'Blender Bullet','probes':probes,'scope':'Reconstructed four hinges and separately aligned motors, fixed base, no gravity, each joint driven both directions; the mounting-arm collider is omitted because this probe cannot implement the USD shape-pair filter, Bullet calculates its own inertia, and this is not USD, PhysX, real motion or clearance validation.'}
(ROOT/'validation/bullet-joints.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'probes':[{k:v for k,v in p.items() if k!='frames'} for p in probes]},indent=2))
assert all(all(p['checks'].values()) for p in probes)
for name in {p['joint'] for p in probes}:
    pair=[p['final_angle_rad'] for p in probes if p['joint']==name]
    assert pair[0]*pair[1]<0,(name,pair)
