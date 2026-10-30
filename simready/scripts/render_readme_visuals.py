"""Render USD collision proxies and an illustrative display-motion frame sequence.

The motion sets imported visual transforms; it is not a USD physics simulation.
Set SECA_FRAME_DIR to a workspace path for frames, then assemble them separately.
"""
import bpy,json,math,os,pathlib
from mathutils import Vector,Quaternion
ROOT=pathlib.Path(__file__).resolve().parents[1]
frames=pathlib.Path(os.environ.get('SECA_FRAME_DIR',str(ROOT/'previews/.animation-frames')));frames.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=str(ROOT/'asset/seca_scale_up_ultra_articulated/usd/seca_scale_up_ultra_articulated.usda'),import_guide=True,import_proxy=True)
scene=bpy.context.scene
colliders=[];visuals=[]
for obj in scene.objects:
 if obj.type!='MESH':continue
 parent=obj.parent;ancestry=[]
 while parent:ancestry.append(parent.name);parent=parent.parent
 if any(name.startswith('Colliders') for name in ancestry):colliders.append((obj,ancestry))
 else:visuals.append(obj)
assert len(colliders)==42 and len(visuals)==272,(len(colliders),len(visuals))
def mat(name,color):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=.55
 return m
palette={'base':mat('Proxy • base',(.12,.33,.45)),'wheel':mat('Proxy • wheel',(.90,.42,.10)),'yaw':mat('Proxy • collar',(.15,.58,.55)),'tilt':mat('Proxy • display',(.14,.58,.55))}
for obj,parents in colliders:
 key='wheel' if any(n in parents for n in ('Wheel_L','Wheel_R')) else ('yaw' if 'Display_Yaw' in parents else ('tilt' if 'Display_Tilt' in parents else 'base'))
 obj.data.materials.clear();obj.data.materials.append(palette[key]);obj.hide_render=False
for obj in visuals:obj.hide_render=True
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.001));floor=bpy.context.object;floor.name='Preview floor';floor.data.materials.append(mat('Preview floor',(.76,.79,.8)))
world=bpy.data.worlds.new('Preview environment');scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(.42,.47,.50,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=.36
def aim(o,target):o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
def area(name,location,power,size,target):
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=location;aim(o,target)
area('Key',(2.8,-3.8,4.6),600,3,(0,0,1));area('Fill',(-3,-1,2.7),350,3,(0,0,1));area('Rim',(0,3,3.8),450,2.4,(0,0,1.3))
camd=bpy.data.cameras.new('Preview camera');cam=bpy.data.objects.new('Preview camera',camd);scene.collection.objects.link(cam);scene.camera=cam
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.image_settings.file_format='PNG';scene.render.resolution_percentage=100
scene.render.resolution_x=1000;scene.render.resolution_y=1000;camd.type='ORTHO';camd.ortho_scale=2.85;cam.location=(3.4,-4.7,2.8);aim(cam,(0,0,1.15))
scene.render.filepath=str(ROOT/'previews/usd-collision-proxies.png');bpy.ops.render.render(write_still=True)
for obj,_ in colliders:obj.hide_render=True
for obj in visuals:obj.hide_render=False
scene.render.resolution_x=640;scene.render.resolution_y=480;scene.cycles.samples=12
camd.ortho_scale=.43;cam.location=(.50,-.85,1.58);aim(cam,(.184,.115,1.45))
yaw_body=scene.objects['Display_Yaw'];tilt_body=scene.objects['Display_Tilt'];yaw_body.rotation_mode='QUATERNION';tilt_body.rotation_mode='QUATERNION'
poses=[]
for frame in range(36):
 t=2*math.pi*frame/36;yaw=.35*math.sin(t);tilt=.18*math.cos(t)
 yaw_body.rotation_quaternion=Quaternion((0,0,1),yaw)
 tilt_body.rotation_quaternion=Quaternion((0,0,1),yaw)@Quaternion((1,0,0),tilt)
 bpy.context.view_layer.update();scene.render.filepath=str(frames/f'frame-{frame:03}.png');bpy.ops.render.render(write_still=True)
 poses.append({'frame':frame,'yaw_rad':yaw,'tilt_rad':tilt})
report={'usd_visual_meshes':len(visuals),'usd_collider_meshes':len(colliders),'fps':12,'frames':len(poses),'poses':poses,
 'scope':'Blender imported USD. Collider image shows solid guide-purpose collision proxies by link; animation sets visual transforms manually and is not physics playback or evidence of actual device range.'}
(ROOT/'validation/readme-visuals.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'visual_meshes':len(visuals),'colliders':len(colliders),'frames':len(poses)},indent=2))
