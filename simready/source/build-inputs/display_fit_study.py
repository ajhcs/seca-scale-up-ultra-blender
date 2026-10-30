"""On-demand, modeled display surface crossings; not a physical clearance test."""
import bpy
from mathutils.bvhtree import BVHTree
MOVING=('Display • articulated cable lead','ID display rear shell','ID display glass bezel','Display • transparent cover','Display • rear cover','Display • data plug','Display bottom swivel housing')
FIXED=('455 • continuous handrail','455 • rear bridge mount','257 • vertical column extrusion','257 • vertical column extrusion section 2','257 • vertical column extrusion section 3','257 • column joint 1','257 • column joint 2')
def evaluate_display_crossings(scene):
    missing=[n for n in MOVING+FIXED if n not in scene.objects]
    if missing:return {'status':'UNAVAILABLE','missing':missing,'crossings':[]}
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
    def tree(obj):
        ev=obj.evaluated_get(deps);mesh=ev.to_mesh()
        if mesh is None:raise ValueError('No evaluated mesh: '+obj.name)
        try:
            if not mesh.vertices or not mesh.polygons:raise ValueError('Empty evaluated mesh: '+obj.name)
            return BVHTree.FromPolygons([ev.matrix_world@v.co for v in mesh.vertices],[list(p.vertices) for p in mesh.polygons],all_triangles=False)
        finally:ev.to_mesh_clear()
    try:
        fixed={n:tree(scene.objects[n]) for n in FIXED};hits=[]
        for name in MOVING:
            part=tree(scene.objects[name])
            for other,target in fixed.items():
                count=len(part.overlap(target))
                if count:hits.append({'moving':name,'fixed':other,'overlapping_polygon_pairs':count})
        return {'status':'CROSSINGS' if hits else 'NO_CROSSINGS_DETECTED','missing':[],'crossings':hits}
    except (ValueError,RuntimeError,ReferenceError) as exc:return {'status':'UNAVAILABLE','missing':[str(exc)],'crossings':[]}

class SECA_OT_display_crossings(bpy.types.Operator):
    """Check selected modeled surfaces at the current pose; not a clearance or safety assessment."""
    bl_idname='seca_display_fit.check';bl_label='Check modeled display crossings'
    def execute(self,context):
        result=evaluate_display_crossings(context.scene)
        if result['status']=='UNAVAILABLE':self.report({'WARNING'},'Display check unavailable: '+', '.join(result['missing']))
        elif result['crossings']:self.report({'WARNING'},f"{len(result['crossings'])} modeled surface pair(s) intersect; see system console")
        else:self.report({'INFO'},'No selected surface crossings detected; containment and clearance untested')
        print('seca display fit study:',result)
        return {'FINISHED'}
class SECA_PT_display_crossings(bpy.types.Panel):
    bl_label='Display fit — modeled study';bl_idname='SECA_PT_display_fit_study';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='seca study'
    def draw(self,context):
        l=self.layout;l.label(text='Current pose; selected surfaces only',icon='INFO');l.operator('seca_display_fit.check');l.label(text='No continuous sweep or containment check');l.label(text='No verified physical stops or clearance')
classes=(SECA_OT_display_crossings,SECA_PT_display_crossings)
def register():
    for cls in reversed(classes):
        identifier=cls.bl_idname if issubclass(cls,bpy.types.Panel) else 'SECA_DISPLAY_FIT_OT_check'
        existing=cls.__bases__[0].bl_rna_get_subclass_py(identifier,None)
        if existing:bpy.utils.unregister_class(existing)
    for cls in classes:bpy.utils.register_class(cls)
def unregister():
    for cls in reversed(classes):
        try:bpy.utils.unregister_class(cls)
        except RuntimeError:pass
if __name__=='__main__':register()
