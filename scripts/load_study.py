"""Optional idealized four-support force study. Not a real seca load-cell model."""
import bpy,json,math
from mathutils import Vector
from bpy.props import BoolProperty,FloatProperty,FloatVectorProperty,PointerProperty,StringProperty

math_ns={'__name__':'seca_load_math'};exec(bpy.data.texts['load_math.py'].as_string(),math_ns);solve=math_ns['solve']
geometry_ns={'__name__':'seca_platform_geometry'};exec(bpy.data.texts['platform_geometry.py'].as_string(),geometry_ns);platform_surface_z=geometry_ns['platform_surface_z']
LABELS=('front left','front right','rear left','rear right')
_busy=False
_orientation={}

def show(obj,visible):
    if obj:obj.hide_set(not visible);obj.hide_render=not visible

def platform_samples(scene,depsgraph=None):
    return [platform_surface_z(scene,x,y,depsgraph) for x,y in ((0,.070),(-.10,.070),(.10,.070),(0,-.030),(0,.170))]

def orientation_signature(scene,root,depsgraph):
    up=root.evaluated_get(depsgraph).matrix_world.to_3x3()@Vector((0,0,1))
    direction=tuple(up.normalized()) if up.length>1e-9 else (0,0,0)
    return direction+tuple(-1000.0 if v is None else v for v in platform_samples(scene,depsgraph))

def calculate(scene):
    v=scene.seca_load;root=scene.objects.get('CONTROL • product root')
    if not root:raise ValueError('Product root missing')
    evaluated=root.evaluated_get(bpy.context.evaluated_depsgraph_get());up=evaluated.matrix_world.to_3x3()@Vector((0,0,1))
    if up.length<1e-9 or up.normalized().dot(Vector((0,0,1)))<.999999:raise ValueError('Study assumes a horizontal platform')
    samples=platform_samples(scene)
    if any(z is None for z in samples):raise ValueError('Platform surface unavailable')
    if max(samples)-min(samples)>.0005:raise ValueError('Study assumes horizontal glass')
    data=solve(v.body_mass,(v.platform_x,v.platform_y),v.rail_fraction,(v.rail_x,v.rail_y),v.rail_transfer,v.half_x,v.half_y,list(v.stiffness),list(v.gains))
    data['platform_z_m']=samples[0]
    data['inputs']={'body_mass_kg':v.body_mass,'platform_xy_m':[v.platform_x,v.platform_y],'rail_fraction':v.rail_fraction,'rail_xy_m':[v.rail_x,v.rail_y],'rail_transfer':v.rail_transfer,'support_halfspan_m':[v.half_x,v.half_y],'relative_stiffness':list(v.stiffness),'relative_gain':list(v.gains)}
    return data

def update_study(self,context):
    global _busy
    if _busy or not context or not context.scene or not hasattr(context.scene,'seca_load'):return
    _busy=True
    try:
        scene=context.scene;v=scene.seca_load;v.applied=False
        for o in scene.objects:
            if o.get('load_study_visual',False):show(o,v.enabled)
        if not v.enabled:v.valid=False;v.message='Study disabled';_orientation.pop(scene.as_pointer(),None);return
        root=scene.objects.get('CONTROL • product root')
        if root:
            deps=bpy.context.evaluated_depsgraph_get();_orientation[scene.as_pointer()]=orientation_signature(scene,root,deps)
        try:data=calculate(scene)
        except (ValueError,ArithmeticError) as exc:
            v.valid=False;v.report_json='';v.message=str(exc)
            for obj in scene.objects:
                if obj.get('load_study_visual',False):show(obj,False)
            return
        v.valid=True;v.report_json=json.dumps(data,separators=(',',':'));v.message='Study inputs changed — apply to simulator'
        base_z=data['platform_z_m']+.002
        coords=[(-v.half_x,-v.half_y),(v.half_x,-v.half_y),(-v.half_x,v.half_y),(v.half_x,v.half_y)]
        for i,((x,y),reaction) in enumerate(zip(coords,data['reactions_n'])):
            bar=scene.objects.get(f'LOAD • {i} bar');tip=scene.objects.get(f'LOAD • {i} tip');label=scene.objects.get(f'LOAD • {i} label')
            h=.014+.12*reaction/max(1,data['total_weight_n'])
            if bar:bar.location=(x,y,base_z+h/2);bar.scale.z=h;show(bar,reaction>1e-6)
            if tip:tip.location=(x,y,base_z+h+.007);show(tip,reaction>1e-6)
            if label:label.location=(x,y,base_z+h+.025);label.data.body=f'{reaction:.0f} N';show(label,True)
        for kind,x,y,visible in [('body',v.platform_x,v.platform_y,v.body_mass>0),('rail',v.rail_x,v.rail_y,v.body_mass>0 and v.rail_fraction>0)]:
            for suffix in ('shaft','tip','label'):
                obj=scene.objects.get(f'LOAD • {kind} {suffix}')
                if obj:
                    obj.location.x=x;obj.location.y=y;obj.location.z=data['platform_z_m']+float(obj.get('load_datum_offset',0));show(obj,visible)
            label=scene.objects.get(f'LOAD • {kind} label')
            if label:label.data.body=(f'PLATFORM {data["platform_n"]:.0f} N' if kind=='body' else f'RAIL INPUT {data["rail_n"]:.0f} N')
    finally:_busy=False

def changed(self,context):update_study(self,context)

class SECA_PG_load(bpy.types.PropertyGroup):
    enabled:BoolProperty(name='Show schematic overlay',default=False,update=changed)
    body_mass:FloatProperty(name='Synthetic body mass (kg)',default=70,min=0,max=500,precision=2,update=changed)
    platform_x:FloatProperty(name='Platform load X (m)',default=0,min=-1,max=1,precision=3,update=changed)
    platform_y:FloatProperty(name='Platform load Y (m)',default=0,min=-1,max=1,precision=3,update=changed)
    rail_fraction:FloatProperty(name='Fraction supported through rail',default=0,min=0,max=1,precision=3,update=changed)
    rail_transfer:FloatProperty(name='Rail force routed to supports',default=0,min=0,max=1,precision=3,update=changed)
    rail_x:FloatProperty(name='Assumed rail load X (m)',default=0,min=-1,max=1,precision=3,update=changed)
    rail_y:FloatProperty(name='Assumed rail load Y (m)',default=.18,min=-1,max=1,precision=3,update=changed)
    half_x:FloatProperty(name='Support half-width (m)',default=.25,min=.05,max=.5,precision=3,update=changed)
    half_y:FloatProperty(name='Support half-depth (m)',default=.18,min=.05,max=.5,precision=3,update=changed)
    stiffness:FloatVectorProperty(name='Relative support stiffness',size=4,default=(1,1,1,1),min=.05,max=10,precision=3,update=changed)
    gains:FloatVectorProperty(name='Relative sensor gains',size=4,default=(1,1,1,1),min=.1,max=2,precision=4,update=changed)
    valid:BoolProperty(default=False)
    applied:BoolProperty(default=False)
    report_json:StringProperty(default='')
    last_applied_json:StringProperty(default='')
    message:StringProperty(default='Study disabled')

class SECA_OT_load_apply(bpy.types.Operator):
    bl_idname='seca_load.apply';bl_label='Apply synthetic gross load';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        scene=context.scene;v=scene.seca_load
        if not v.enabled:self.report({'WARNING'},'Enable the study first');return {'CANCELLED'}
        if not hasattr(scene,'seca_study'):self.report({'WARNING'},'Run seca_simulator.py first');return {'CANCELLED'}
        context.view_layer.update()
        try:data=calculate(scene)
        except (ValueError,ArithmeticError) as exc:v.valid=False;v.message=str(exc);self.report({'WARNING'},str(exc));return {'CANCELLED'}
        if data['reading_kg']>500:
            v.valid=False;v.message='Reading exceeds synthetic input limit';self.report({'WARNING'},v.message);return {'CANCELLED'}
        # The simulator's existing input callback invalidates an active result.
        scene.seca_study.gross_kg=data['reading_kg'];v.valid=True;v.applied=True;v.report_json=json.dumps(data,separators=(',',':'));v.last_applied_json=v.report_json;v.message='Synthetic gross input applied; remeasure if loaded'
        return {'FINISHED'}

class SECA_PT_load(bpy.types.Panel):
    bl_label='Load distribution study — approximate';bl_idname='SECA_PT_load';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='seca study'
    def draw(self,context):
        l=self.layout;v=context.scene.seca_load;l.label(text='Assumed supports; not device calibration',icon='INFO');l.prop(v,'enabled')
        if not v.enabled:return
        l.prop(v,'body_mass');row=l.row(align=True);row.prop(v,'platform_x');row.prop(v,'platform_y')
        l.prop(v,'rail_fraction');l.prop(v,'rail_transfer');row=l.row(align=True);row.prop(v,'rail_x');row.prop(v,'rail_y')
        row=l.row(align=True);row.prop(v,'half_x');row.prop(v,'half_y');l.prop(v,'stiffness');l.prop(v,'gains');l.operator('seca_load.apply')
        l.label(text=v.message)
        if v.valid:
            data=json.loads(v.report_json);l.label(text=f'Synthetic reading: {data["reading_kg"]:.2f} kg')
            l.label(text=f'Glass datum: {data["platform_z_m"]*1000:.1f} mm')
            l.label(text=f'Platform input: {data["platform_n"]:.1f} N')
            l.label(text=f'Rail coupled: {data["coupled_rail_n"]:.1f} N')
            l.label(text=f'Rail bypass: {data["bypassed_rail_n"]:.1f} N')
            for label,value in zip(LABELS,data['reactions_n']):l.label(text=f'{label}: {value:.1f} N')

classes=(SECA_PG_load,SECA_OT_load_apply,SECA_PT_load)
def _watch_load_orientation(scene,depsgraph):
    if _busy or not hasattr(scene,'seca_load') or not scene.seca_load.enabled or bpy.context.scene!=scene:return
    root=scene.objects.get('CONTROL • product root')
    if not root:return
    key=scene.as_pointer();value=orientation_signature(scene,root,depsgraph)
    old=_orientation.get(key);_orientation[key]=value
    if old is not None and max(abs(a-b) for a,b in zip(old,value))>1e-7:update_study(scene.seca_load,bpy.context)
_watch_load_orientation._seca_load_watch=True
def remove_watchers():
    for handler in list(bpy.app.handlers.depsgraph_update_post):
        if getattr(handler,'_seca_load_watch',False):bpy.app.handlers.depsgraph_update_post.remove(handler)
    _orientation.clear()
def register():
    remove_watchers()
    if hasattr(bpy.types.Scene,'seca_load'):del bpy.types.Scene.seca_load
    for c in reversed(classes):
        old=getattr(bpy.types,c.__name__,None)
        if old:bpy.utils.unregister_class(old)
    for c in classes:bpy.utils.register_class(c)
    bpy.types.Scene.seca_load=PointerProperty(type=SECA_PG_load);update_study(bpy.context.scene.seca_load,bpy.context);bpy.app.handlers.depsgraph_update_post.append(_watch_load_orientation)
def unregister():
    remove_watchers()
    if hasattr(bpy.types.Scene,'seca_load'):del bpy.types.Scene.seca_load
    for c in reversed(classes):bpy.utils.unregister_class(c)
if __name__=='__main__':register()
