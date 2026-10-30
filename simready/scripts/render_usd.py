import bpy, json, math, pathlib
from mathutils import Vector, Quaternion
ROOT=pathlib.Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
props={p.identifier for p in bpy.ops.wm.usd_import.get_rna_type().properties}
options={'filepath':str(ROOT/'asset/seca_scale_up_ultra_articulated/usd/seca_scale_up_ultra_articulated.usda')}
if 'import_guide' in props:options['import_guide']=False
if 'import_proxy' in props:options['import_proxy']=False
print('USD IMPORT OPTIONS',options)
bpy.ops.wm.usd_import(**options)
sc=bpy.context.scene
collider_names=set(x['name'] for x in json.loads((ROOT/'validation/articulation-model.json').read_text())['colliders'])
hidden=[]
for obj in sc.objects:
    if obj.type=='MESH' and obj.name in collider_names:
        obj.hide_render=True;hidden.append(obj.name)
def material(name,rgba,rough):
    m=bpy.data.materials.new(name);m.diffuse_color=rgba;m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=rgba;p.inputs['Roughness'].default_value=rough
    return m
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-0.001))
floor=bpy.context.object;floor.name='Preview floor';floor.data.materials.append(material('Preview floor material',(0.30,0.32,0.34,1),0.86))
world=bpy.data.worlds.new('Preview environment');sc.world=world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs['Color'].default_value=(0.35,0.39,0.44,1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value=0.30
def aim(obj,target):obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
def area(name,location,power,size,target):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);sc.collection.objects.link(o);o.location=location;aim(o,target)
area('Key',(2.8,-3.8,4.6),600,3,(0,0,1.0))
area('Fill',(-3,-1,2.7),350,3,(0,0,1.0))
area('Rim',(0,3,3.8),450,2.4,(0,0,1.3))
camdata=bpy.data.cameras.new('Preview Camera');cam=bpy.data.objects.new('Preview Camera',camdata);sc.collection.objects.link(cam);sc.camera=cam
sc.render.engine='CYCLES';sc.cycles.samples=16;sc.cycles.use_denoising=True
sc.render.resolution_x=900;sc.render.resolution_y=900;sc.render.resolution_percentage=100
sc.render.image_settings.file_format='PNG';sc.render.film_transparent=False
camdata.type='ORTHO';camdata.ortho_scale=2.85;cam.location=(3.4,-4.7,2.8);aim(cam,(0,0,1.15))
sc.render.filepath=str(ROOT/'previews/articulated-overview.png');bpy.ops.render.render(write_still=True)
camdata.ortho_scale=0.26;cam.location=(0.48,-0.85,1.58);aim(cam,(0.184,0.11,1.45))
sc.render.filepath=str(ROOT/'previews/articulated-display.png');bpy.ops.render.render(write_still=True)
# Posed visual illustration only: these transforms do not simulate USD joints.
yaw_body=sc.objects['Display_Yaw'];tilt_body=sc.objects['Display_Tilt']
yaw_body.rotation_mode='QUATERNION';tilt_body.rotation_mode='QUATERNION'
camdata.ortho_scale=0.42
for label,yaw,tilt in [('negative',-.45,-.25),('positive',.45,.25)]:
    yaw_body.rotation_quaternion=Quaternion((0,0,1),yaw)
    tilt_body.rotation_quaternion=Quaternion((0,0,1),yaw) @ Quaternion((1,0,0),tilt)
    bpy.context.view_layer.update()
    sc.render.filepath=str(ROOT/('previews/display-pose-'+label+'.png'));bpy.ops.render.render(write_still=True)
yaw_body.rotation_quaternion=Quaternion((1,0,0,0));tilt_body.rotation_quaternion=Quaternion((1,0,0,0))
bpy.context.view_layer.update()
floor.hide_render=True
world.node_tree.nodes['Background'].inputs['Color'].default_value=(0,0,0,1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value=0
camdata.ortho_scale=2.85;cam.location=(3.4,-4.7,2.8);aim(cam,(0,0,1.15))
sc.render.resolution_x=256;sc.render.resolution_y=256;sc.cycles.samples=32
thumbnail=ROOT/'asset/seca_scale_up_ultra_articulated/usd/.thumbs/256x256/seca_scale_up_ultra_articulated.usda.png'
thumbnail.parent.mkdir(parents=True,exist_ok=True)
sc.render.filepath=str(thumbnail);bpy.ops.render.render(write_still=True)
print(json.dumps({'imported_objects':len(sc.objects),'hidden_collider_objects':len(hidden),'hidden_names':hidden,'render_engine':'Cycles CPU','samples':16},indent=2))
