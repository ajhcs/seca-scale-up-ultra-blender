import bpy,runpy,json,math,pathlib
from mathutils import Vector
ROOT=pathlib.Path(__file__).resolve().parents[1]
fit=ROOT/'source/build-inputs/display_fit_study.py'
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'source/seca-articulation-editable.blend'),load_ui=False,use_scripts=False)
scene=bpy.context.scene;evaluate=runpy.run_path(str(fit),run_name='display_fit_import')['evaluate_display_crossings']
yaw=scene.objects['CONTROL • display swivel'];tilt=scene.objects['CONTROL • display tilt and rotation']
samples=[]
for i in range(7):
    for j in range(7):
        y=-.6+i*.2;t=-.4+j*(.8/6)
        yaw.rotation_euler.z=y;tilt.rotation_euler.x=t;scene.view_layers.update()
        fit_result=evaluate(scene)
        samples.append({'yaw_rad':y,'tilt_rad':t,'status':fit_result['status'],'crossings':fit_result['crossings']})
yaw.rotation_euler.z=0;tilt.rotation_euler.x=0
wheels=[]
for side in ('L','R'):
    control=scene.objects['CONTROL • wheel '+side]
    tread=scene.objects['Transport wheel tread' if side=='L' else 'Transport wheel tread.001']
    rows=[]
    for angle in (0,math.pi/2,math.pi,3*math.pi/2):
        control.rotation_euler.x=angle;scene.view_layers.update();dg=bpy.context.evaluated_depsgraph_get();ev=tread.evaluated_get(dg);mesh=ev.to_mesh()
        points=[ev.matrix_world@v.co for v in mesh.vertices];pivot=control.evaluated_get(dg).matrix_world.translation
        radii=[math.hypot(p.y-pivot.y,p.z-pivot.z) for p in points]
        rows.append({'angle_rad':angle,'pivot_m':list(pivot),'radius_min_m':min(radii),'radius_max_m':max(radii)})
        ev.to_mesh_clear()
    control.rotation_euler.x=0
    wheels.append({'side':side,'samples':rows,'max_radius_spread_m':max(x['radius_max_m'] for x in rows)-min(x['radius_max_m'] for x in rows)})
result={'display_samples':samples,'crossing_count':sum(x['status']!='NO_CROSSINGS_DETECTED' for x in samples),
        'wheel_samples':wheels,'scope':'49 sampled Blender source-control poses and four angles per wheel; selected surface intersections only, not full containment, cable motion, physical stops, continuous sweep or USD runtime behavior.'}
(ROOT/'validation/control-sweep.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'display_poses':len(samples),'crossing_count':result['crossing_count'],'wheels':wheels},indent=2))
assert result['crossing_count']==0 and all(x['max_radius_spread_m']<1e-5 for x in wheels)
