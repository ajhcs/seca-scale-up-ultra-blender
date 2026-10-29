"""Sample the modeled glass surface in product coordinates; not device metrology."""
import bpy,math
from mathutils import Vector

def platform_surface_z(scene,x=0.0,y=.070,depsgraph=None):
    root=scene.objects.get('CONTROL • product root');glass=scene.objects.get('654 • Bearclaw glass top')
    if not root or not glass or glass.type!='MESH':return None
    try:
        deps=depsgraph or bpy.context.evaluated_depsgraph_get();evaluated=glass.evaluated_get(deps)
        # The cast is isolated to the evaluated glass mesh so printed graphics,
        # feet, subjects and annotations cannot become the platform datum.
        root_world=root.evaluated_get(deps).matrix_world;glass_world=evaluated.matrix_world
        if abs(root_world.determinant())<1e-12 or abs(glass_world.determinant())<1e-12:return None
        origin_world=root_world@Vector((float(x),float(y),3.0));direction_world=root_world.to_3x3()@Vector((0,0,-1))
        inv_glass=glass_world.inverted();direction=inv_glass.to_3x3()@direction_world
        if direction.length<1e-12:return None
        hit,point,normal,index=evaluated.ray_cast(inv_glass@origin_world,direction.normalized())
        if not hit:return None
        z=(root_world.inverted()@glass_world@point).z
        return float(z) if math.isfinite(z) else None
    except (ValueError,RuntimeError,ReferenceError,ZeroDivisionError):return None
