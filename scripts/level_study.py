"""Install the optional seca setup-level study in this Blender session.

The 10 mm screw limit and four screws are documented; dimensions, COM, bubble
sensitivity and rigid planar contacts are study assumptions, not calibration.
Run seca_simulator.py and then this text manually. Not for device operation.
"""
import bpy, math
from mathutils import Vector
from bpy.props import BoolProperty,FloatProperty,FloatVectorProperty,PointerProperty,StringProperty
from bpy.types import PropertyGroup,Panel
math_ns={'__name__':'seca_level_math'};exec(bpy.data.texts['level_math.py'].as_string(),math_ns)
solve_support=math_ns['support'];FEET=math_ns['FEET'];_level_busy=False
FOOT_NAMES=('Adjustable leveling foot','Adjustable leveling foot.001','Adjustable leveling foot.002','Adjustable leveling foot.003')
BUBBLE_NAME='Spirit level bubble • static';FLOOR_NAME='Study • leveling floor';STAGE_NAME='Studio cyclorama'
# Pitch is a visual/mechanical study assumption, not a manufacturer's value.
THREAD_PITCH=.0015
LOCK_TRAVEL=.0008
COLLAR_UNLOCKED_Z=.0082
COLLAR_NAMES=('Foot lock collar','Foot lock collar.001','Foot lock collar.002','Foot lock collar.003')

def sync_locks(scene):
 if not hasattr(scene,'seca_level'):return
 s=scene.seca_level
 for i,name in enumerate(COLLAR_NAMES):
  obj=bpy.data.objects.get(name)
  if obj:
   locked=getattr(s,f'lock_{i}')
   obj.location.z=COLLAR_UNLOCKED_Z+(LOCK_TRAVEL if locked else 0.0)
   obj.rotation_euler.z=(2*math.pi*LOCK_TRAVEL/THREAD_PITCH) if locked else 0.0

def _lock_update(self,context):
 if context and context.scene:sync_locks(context.scene)

def _set_ext(index):
 def setter(self,val):
  if getattr(self,f'lock_{index}'):
   self.message='Unlock that foot before adjusting it';self['blocked_adjustment']=True
  else:self[f'ext_{index}_stored']=max(0.0,min(.010,float(val)))
 return setter

def _get_ext(index):
 def getter(self):return float(self.get(f'ext_{index}_stored',0.0))
 return getter

def _update(self,context):
 if self.get('blocked_adjustment',False):
  del self['blocked_adjustment'];return
 if context and context.scene:apply_level(context.scene)

def signal_setup_change(scene):
 # Persist until the simulator is registered, including across a saved file.
 scene['seca_setup_dirty']=True
 handler=bpy.app.driver_namespace.get('seca_setup_changed')
 if callable(handler) and hasattr(scene,'seca_study'):
  handler(scene);return
 # A saved visual snapshot must not present a stale current result while the
 # measurement script is absent. Historical recall and outbox data are kept.
 for name,value in (('SIM • weight','---'),('SIM • height','---.-'),('SIM • bmi',''),('SIM • state','---'),('SIM • message','Setup changed')):
  obj=bpy.data.objects.get(name)
  if obj and obj.type=='FONT':obj.data.body=value
 for obj in bpy.data.objects:
  if obj.name.startswith(('REVIEW • ','MEASURE • ','CAL • ','OVERVIEW • ')):
   obj.hide_render=True;obj.hide_set(True)

def apply_level(scene):
 global _level_busy
 if _level_busy:return
 _level_busy=True
 try:
  s=scene.seca_level;root=bpy.data.objects.get('CONTROL • product root');pivot=bpy.data.objects.get('CONTROL • transport pivot');bubble=bpy.data.objects.get(BUBBLE_NAME);floor=bpy.data.objects.get(FLOOR_NAME);stage=bpy.data.objects.get(STAGE_NAME)
  if not all((root,pivot,bubble,floor,stage)):
   s.message='Level study objects are missing';return
  if s.enabled and not s.stage_active:
   # The floor and COM calculations assume the original untranslated setup.
   if any(abs(v)>1e-5 for v in pivot.rotation_euler) or abs(pivot.location.x)>1e-5 or abs(pivot.location.y-.267)>1e-5 or abs(pivot.location.z-.043)>1e-5:
    s.enabled=False;scene['seca_level_active']=False;s.message='Return transport to its original pose first';return
   s.stage_prev_render=stage.hide_render;s.stage_prev_hidden=stage.hide_get();s.stage_active=True
  scene['seca_level_active']=bool(s.enabled)
  if not s.enabled:
   if s.stage_active:
    changed=(abs(root.location.z)>1e-7 or max(abs(root.rotation_euler.x),abs(root.rotation_euler.y))>1e-7 or any(abs(bpy.data.objects[n].location.z-.014)>1e-7 for n in FOOT_NAMES) or any(abs(v.co.z)>1e-7 for v in floor.data.vertices))
    root.location=(0,0,0);root.rotation_euler=(0,0,0)
    for i,name in enumerate(FOOT_NAMES):
     o=bpy.data.objects.get(name)
     if o:o.location.z=.014;o.rotation_euler.z=0.0
    bubble.location=(.097,.300,.0751);floor.hide_render=True;floor.hide_set(True)
    stage.hide_render=s.stage_prev_render;stage.hide_set(s.stage_prev_hidden);s.stage_active=False
    if changed:signal_setup_change(scene)
   return
  ax=math.tan(s.floor_x);ay=math.tan(s.floor_y);ext=[getattr(s,f'ext_{i}') for i in range(4)]
  try:result=solve_support(ext,ax,ay,(s.com_x,s.com_y,.55))
  except ValueError as e:s.valid=False;s.message=str(e);return
  floor_points=((-1.,-1.),(1.,-1.),(1.,1.),(-1.,1.))
  changed=(abs(root.location.z-result['height'])>1e-7
           or abs(root.rotation_euler.x-result['roll'])>1e-7
           or abs(root.rotation_euler.y-result['pitch'])>1e-7
           or any(abs(bpy.data.objects[n].location.z-(.014-ext[i]))>1e-7 for i,n in enumerate(FOOT_NAMES))
           or any(abs(v.co.z-(ax*x+ay*y))>1e-7 for v,(x,y) in zip(floor.data.vertices,floor_points)))
  root.location=(0,0,result['height']);root.rotation_euler=(result['roll'],result['pitch'],0)
  for i,name in enumerate(FOOT_NAMES):
   # Pad, solid shaft and thread travel together as a fixed-length screw.
   # Pitch and rotation direction are illustrative, not measured hardware.
   foot=bpy.data.objects[name];foot.location.z=.014-ext[i];foot.rotation_euler.z=-2*math.pi*ext[i]/THREAD_PITCH
  for v,(x,y) in zip(floor.data.vertices,((-1.,-1.),(1.,-1.),(1.,1.),(-1.,1.))):v.co=(x,y,ax*x+ay*y)
  floor.data.update();floor.hide_render=False;floor.hide_set(False);stage.hide_render=True;stage.hide_set(True)
  # Bubble moves toward local-up: an uncalibrated bubble sensitivity and travel.
  # The transport pivot is required to be neutral, so local-up follows the
  # solved Euler angles directly; do not force a dependency-graph update
  # from inside an interactive property callback.
  local_up_x=-math.sin(result['pitch']);local_up_y=math.cos(result['pitch'])*math.sin(result['roll'])
  dx,dy=.08*local_up_x,.08*local_up_y;distance=math.hypot(dx,dy);limit=.0019
  if distance>limit:dx*=limit/distance;dy*=limit/distance
  bubble.location=(.097+dx,.300+dy,.0751)
  s.gaps=result['gaps'];s.roll_deg=math.degrees(result['roll']);s.pitch_deg=math.degrees(result['pitch']);s.valid=True
  s.message='Study solution; bubble sensitivity and contacts uncalibrated'
  if changed:
   signal_setup_change(scene);s.message='Setup changed; recalibrate study'
 finally:_level_busy=False

class SECALEVEL_PG_settings(PropertyGroup):
 enabled: BoolProperty(name='Enable setup study',default=False,update=_update)
 floor_x: FloatProperty(name='Floor slope X',subtype='ANGLE',default=0,min=-.05,max=.05,update=_update)
 floor_y: FloatProperty(name='Floor slope Y',subtype='ANGLE',default=0,min=-.05,max=.05,update=_update)
 com_x: FloatProperty(name='Assumed COM X',default=0,min=-.10,max=.10,precision=3,update=_update)
 com_y: FloatProperty(name='Assumed COM Y',default=.03,min=-.10,max=.10,precision=3,update=_update)
 ext_0: FloatProperty(name='Front left',get=_get_ext(0),set=_set_ext(0),min=0,max=.010,precision=4,step=.1,update=_update)
 ext_1: FloatProperty(name='Rear left',get=_get_ext(1),set=_set_ext(1),min=0,max=.010,precision=4,step=.1,update=_update)
 ext_2: FloatProperty(name='Front right',get=_get_ext(2),set=_set_ext(2),min=0,max=.010,precision=4,step=.1,update=_update)
 ext_3: FloatProperty(name='Rear right',get=_get_ext(3),set=_set_ext(3),min=0,max=.010,precision=4,step=.1,update=_update)
 lock_0: BoolProperty(name='Lock',default=False,update=_lock_update);lock_1: BoolProperty(name='Lock',default=False,update=_lock_update);lock_2: BoolProperty(name='Lock',default=False,update=_lock_update);lock_3: BoolProperty(name='Lock',default=False,update=_lock_update)
 gaps: FloatVectorProperty(size=4,default=(0,0,0,0));roll_deg: FloatProperty(default=0);pitch_deg: FloatProperty(default=0)
 valid: BoolProperty(default=False);message: StringProperty(default='Setup study disabled')
 stage_active: BoolProperty(default=False);stage_prev_render: BoolProperty(default=False);stage_prev_hidden: BoolProperty(default=False)

class SECALEVEL_PT_setup(Panel):
 bl_label='seca leveling — study';bl_idname='SECALEVEL_PT_setup';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='seca study'
 def draw(self,context):
  s=context.scene.seca_level;l=self.layout;l.prop(s,'enabled')
  if not s.enabled:l.label(text='Enable at original transport pose');return
  l.label(text='Rigid contacts / bubble sensitivity assumed',icon='INFO');l.prop(s,'floor_x');l.prop(s,'floor_y')
  for i in range(4):
   row=l.row(align=True);row.prop(s,f'ext_{i}');row.prop(s,f'lock_{i}',text='',icon='LOCKED' if getattr(s,f'lock_{i}') else 'UNLOCKED');row.label(text=f'{getattr(s,f"ext_{i}")*1000:.1f} mm')
  box=l.box();box.label(text='Assumed center of mass');box.prop(s,'com_x');box.prop(s,'com_y')
  if s.valid:
   l.label(text=f'Roll {s.roll_deg:+.2f}° / pitch {s.pitch_deg:+.2f}°');l.label(text='Foot gaps (mm): '+', '.join(f'{max(0,g)*1000:.1f}' for g in s.gaps))
  l.label(text=s.message)

def register():
 if hasattr(bpy.types.Scene,'seca_level'):del bpy.types.Scene.seca_level
 for c in (SECALEVEL_PT_setup,SECALEVEL_PG_settings):
  old=getattr(bpy.types,c.__name__,None)
  if old:bpy.utils.unregister_class(old)
 for c in (SECALEVEL_PG_settings,SECALEVEL_PT_setup):bpy.utils.register_class(c)
 bpy.types.Scene.seca_level=PointerProperty(type=SECALEVEL_PG_settings)
 sync_locks(bpy.context.scene)
 if bpy.context.scene.seca_level.enabled:apply_level(bpy.context.scene)

def unregister():
 if hasattr(bpy.types.Scene,'seca_level'):del bpy.types.Scene.seca_level
 for c in (SECALEVEL_PT_setup,SECALEVEL_PG_settings):
  old=getattr(bpy.types,c.__name__,None)
  if old:bpy.utils.unregister_class(old)
if __name__=='__main__':register()
