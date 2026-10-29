"""Optional, conservative, snapshot-only clearance study for a kinematic arc.

Run seca_simulator.py first. This is not a physical collision solver, a
measurement of the real device, or a safety certification.
"""
import bpy,math,json,hashlib,struct
from array import array
from mathutils import Vector,Matrix,Euler
from mathutils.bvhtree import BVHTree
from bpy.props import BoolProperty,FloatProperty,PointerProperty,StringProperty

PARTS=[
 ('base','654 • lower platform chassis'),('glass','654 • Bearclaw glass top'),('glass backing','654 • visual underside backing (estimated)'),
 ('fascia','654 • wrapped side fascia'),('rear deck center','654 • rear deck center'),('rear deck left','654 • rear deck wing L'),('rear deck right','654 • rear deck wing R'),('rear connector housing','654 • rear connector enclosure'),
 ('rail','455 • continuous handrail'),('rail mount','455 • rear bridge mount'),
 ('rail foot L','455 • base flange -1'),('rail foot R','455 • base flange 1'),
 ('rail support L','455 • lower support arm -1'),('rail support R','455 • lower support arm 1'),
 ('rail crossbar','455 • underside transverse support'),
 ('mast lower','257 • vertical column extrusion'),('mast middle','257 • vertical column extrusion section 2'),('mast upper','257 • vertical column extrusion section 3'),
 ('mast foot','257 • tapered foot cover'),('head upper','257 • head upper shell'),('head lower','257 • head lower shell'),
 ('display shell','ID display rear shell'),('display bezel','ID display glass bezel'),('display cover','Display • transparent cover'),('display arm','Display arm from mast'),('display lead','Display • articulated cable lead'),
 ('wheel guard L','Wheel guard shell -1'),('wheel guard R','Wheel guard shell 1'),('wheel housing L','Wheel stationary side housing -1'),('wheel housing R','Wheel stationary side housing 1'),
 ('wheel L','Transport wheel tread'),('wheel R','Transport wheel tread.001'),
]+[(f'foot {i}',name) for i,name in enumerate(('Adjustable leveling foot','Adjustable leveling foot.001','Adjustable leveling foot.002','Adjustable leveling foot.003'))]+[(f'foot collar {i}',name) for i,name in enumerate(('Foot lock collar','Foot lock collar.001','Foot lock collar.002','Foot lock collar.003'))]+[(f'foot stem {i}',f'Study • foot shaft {i}') for i in range(4)]+[(f'platform cap {i}',name) for i,name in enumerate(('Platform visible fastening • inferred','Platform visible fastening • inferred.001','Platform visible fastening • inferred.002','Platform visible fastening • inferred.003'))]+[(f'platform cap outline {i}',f'654 • platform cap outline {i}') for i in range(4)]

# V77–78 service pieces travel with the product and must be represented in
# the same snapshot as the earlier shells and mounting hardware.
PARTS += [(f'channel cover {i}',f'257 • removable channel cover {i} (estimated)') for i in range(1,4)]
PARTS += [(f'channel strap {i}',f'257 • retaining strap {i} (study)') for i in range(1,6)]
PARTS += [(f'channel strap leg {i} {side}',f'257 • retaining leg {i} {side} (study)') for i in range(1,6) for side in (-1,1)]
PARTS += [(f'column cable {i}',n) for i,n in enumerate(('257 • head cable routed segment (study)','257 • display cable routed segment (study)','257 • head cable upper connection (study)','257 • display cable upper connection (study)','257 • head cable base connection (study)'))]
PARTS += [(f'{label} socket {wall}',f'257 • {label} socket {wall} (study)') for label in ('head cable','display cable','base cable') for wall in ('left','right','bottom','top')]

def bbox(points):
    return tuple(min(p[i] for p in points) for i in range(3)),tuple(max(p[i] for p in points) for i in range(3))

def transform_box(lo,hi,m):
    c=Vector(tuple((lo[i]+hi[i])*.5 for i in range(3)));h=tuple((hi[i]-lo[i])*.5 for i in range(3));w=m@c
    ext=tuple(sum(abs(m[i][j])*h[j] for j in range(3)) for i in range(3))
    return tuple(w[i]-ext[i] for i in range(3)),tuple(w[i]+ext[i] for i in range(3))

def boxes_overlap(a,b,margin=0):
    return all(a[0][i]-margin<=b[1][i] and a[1][i]+margin>=b[0][i] for i in range(3))

def make_proxy(label,lo,hi):
    c=tuple((lo[i]+hi[i])*.5 for i in range(3));h=tuple(max(.0001,(hi[i]-lo[i])*.5) for i in range(3))
    radius=math.sqrt(sum((abs(c[i])+h[i])**2 for i in range(3)))
    return {'part':label,'lo':tuple(c[i]-h[i] for i in range(3)),'hi':tuple(c[i]+h[i] for i in range(3)),'radius':radius}

def product_proxies(scene):
    pivot=scene.objects.get('CONTROL • transport pivot')
    if not pivot:raise ValueError('Transport pivot missing')
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();inv=pivot.matrix_world.inverted();result=[];missing=[]
    for label,name in PARTS:
        obj=scene.objects.get(name)
        if not obj:missing.append(name);continue
        ev=obj.evaluated_get(deps);mesh=ev.to_mesh()
        if mesh is None or not mesh.vertices:
            if mesh is not None:ev.to_mesh_clear()
            missing.append(name);continue
        relative=inv@ev.matrix_world;vertices=[relative@v.co for v in mesh.vertices]
        if label.startswith('wheel ') and label in {'wheel L','wheel R'}:
            # A rotationally symmetric envelope covers the modeled wheel during spin.
            center=inv@obj.parent.matrix_world.translation if obj.parent else sum(vertices,Vector())/len(vertices)
            radius=max((v-center).length for v in vertices);lo=tuple(center[i]-radius for i in range(3));hi=tuple(center[i]+radius for i in range(3));result.append(make_proxy(label,lo,hi))
        elif label in {'rail','fascia'}:
            # Cluster the evaluated rail surface triangles into small boxes;
            # avoid replacing its hollow arch by one large filled box.
            mesh.calc_loop_triangles();cells={};cell=.08
            for tri in mesh.loop_triangles:
                pts=[vertices[i] for i in tri.vertices];center=sum(pts,Vector())/3;key=tuple(math.floor(x/cell) for x in center)
                group=cells.setdefault(key,[]);group.extend(pts)
            for pts in cells.values():result.append(make_proxy(label,*bbox(pts)))
        else:result.append(make_proxy(label,*bbox(vertices)))
        ev.to_mesh_clear()
    if missing:raise ValueError('Missing model parts: '+', '.join(missing))
    return result

def obstacle_boxes(scene,include_demo):
    deps=bpy.context.evaluated_depsgraph_get();out=[]
    for obj in scene.objects:
        if not obj.get('clearance_obstacle',False) or (obj.get('clearance_demo',False) and not include_demo):continue
        if obj.type!='MESH':raise ValueError('Obstacle must be a mesh: '+obj.name)
        ev=obj.evaluated_get(deps);out.append((obj.name,bbox([ev.matrix_world@Vector(c) for c in ev.bound_box])))
    if not out:raise ValueError('No tagged obstacles; enable the example or tag a mesh')
    return out

def arc_position(x,y,heading,distance,turn,fraction):
    a=turn*fraction
    if abs(turn)<1e-8:return x-math.sin(heading)*distance*fraction,y+math.cos(heading)*distance*fraction,heading+a
    return x+(math.cos(heading+a)-math.cos(heading))*distance/turn,y+(math.sin(heading+a)-math.sin(heading))*distance/turn,heading+a

def path_matrix(scene,fraction):
    s=scene.seca_study;pivot=scene.objects['CONTROL • transport pivot'];x,y,heading=arc_position(s.transport_x,.267+s.transport_y,s.transport_yaw,s.arc_distance,s.arc_yaw,fraction)
    return Matrix.Translation((x,y,pivot.location.z))@Euler((-s.transport_angle,0,heading),'XYZ').to_matrix().to_4x4()

def update_preview(scene,positions,marker=None):
    obj=scene.objects.get('CLEARANCE • axle path');spot=scene.objects.get('CLEARANCE • possible overlap marker');ghost=scene.objects.get('CLEARANCE • sampled part ghost')
    if obj:
        obj.data.splines.clear()
        if positions:
            sp=obj.data.splines.new('POLY');sp.points.add(len(positions)-1)
            for p,v in zip(sp.points,positions):p.co=(v.x,v.y,.014,1)
        obj.hide_set(not bool(positions));obj.hide_render=not bool(positions)
    if spot:
        if marker is not None:spot.location=marker
        spot.hide_set(marker is None);spot.hide_render=marker is None
    if ghost:ghost.hide_set(True);ghost.hide_render=True

# The report is a snapshot. Hash the evaluated surfaces and transforms which
# feed both passes, the obstacle set and the controls that define their path.
# This detects edits to the tracked inputs, not unrelated scene state.
_clearance_watch_guard=False
def snapshot_signature(scene,depsgraph=None):
    try:
        deps=depsgraph or bpy.context.evaluated_depsgraph_get();v=scene.seca_clearance;s=scene.seca_study
        pivot=scene.objects.get('CONTROL • transport pivot')
        if not pivot:return None
        d=hashlib.sha256()
        def put(x):
            b=str(x).encode('utf-8');d.update(struct.pack('<I',len(b)));d.update(b)
        for x in (v.show_demo,v.step_m,v.step_deg,s.transport_x,s.transport_y,s.transport_yaw,s.transport_angle,s.arc_distance,s.arc_yaw,s.previous_distance,s.previous_yaw,s.disconnected,s.loaded,s.drip_guard_removed,s.cal_rod_placed,scene.get('seca_level_active',False),bool(hasattr(scene,'seca_level') and scene.seca_level.enabled)):
            put(x)
        for row in pivot.evaluated_get(deps).matrix_world:
            for x in row:d.update(struct.pack('<d',float(x)))
        objects=[('part:'+label,scene.objects.get(name)) for label,name in PARTS]
        objects += [('obstacle:'+o.name,o) for o in sorted(scene.objects,key=lambda o:o.name) if o.get('clearance_obstacle',False) and not (o.get('clearance_demo',False) and not v.show_demo)]
        for label,obj in objects:
            put(label)
            if obj is None:put('MISSING');continue
            put(obj.name);put(obj.type)
            ev=obj.evaluated_get(deps)
            for row in ev.matrix_world:
                for x in row:d.update(struct.pack('<d',float(x)))
            mesh=ev.to_mesh()
            if mesh is None:put('NO_MESH');continue
            try:
                coords=array('f',[0.0])*(len(mesh.vertices)*3);mesh.vertices.foreach_get('co',coords);d.update(coords.tobytes())
                mesh.calc_loop_triangles();faces=array('i',[0])*(len(mesh.loop_triangles)*3);mesh.loop_triangles.foreach_get('vertices',faces);d.update(faces.tobytes())
                put((len(mesh.vertices),len(mesh.loop_triangles)))
            finally:ev.to_mesh_clear()
        return d.hexdigest()
    except (ValueError,RuntimeError,ReferenceError,AttributeError,TypeError):return None

def clear_stale(scene,reason='scene or path inputs changed'):
    v=scene.seca_clearance;v.status='Not checked — '+reason;v.refinement_status='Not run';v.report_json='';scene.pop('seca_clearance_signature',None);scene.pop('seca_clearance_display_pose',None);update_preview(scene,[])

def watch_snapshot(scene,depsgraph):
    global _clearance_watch_guard
    if _clearance_watch_guard or not hasattr(scene,'seca_clearance'):return
    v=scene.seca_clearance;previous=scene.get('seca_clearance_signature')
    if not v.report_json:return
    if previous is None:
        try:
            if json.loads(v.report_json).get('status')=='NOT_CHECKED':return
        except (ValueError,TypeError):pass
    _clearance_watch_guard=True
    try:
        current=snapshot_signature(scene,depsgraph)
        if previous is None or current is None or current!=previous:clear_stale(scene)
    finally:_clearance_watch_guard=False
watch_snapshot._seca_clearance_display_watcher=True

def remove_display_watchers():
    for h in list(bpy.app.handlers.depsgraph_update_post):
        if getattr(h,'_seca_clearance_display_watcher',False):bpy.app.handlers.depsgraph_update_post.remove(h)

def sync_demo(self,context):
    if not context or not context.scene:return
    for o in context.scene.objects:
        if o.get('clearance_demo',False):o.hide_set(not self.show_demo);o.hide_render=not self.show_demo
    self.status='Not checked — study settings changed';self.refinement_status='Not run';self.report_json='';update_preview(context.scene,[])

def settings_changed(self,context):
    self.status='Not checked — study settings changed';self.refinement_status='Not run';self.report_json=''
    if context and context.scene:update_preview(context.scene,[])

def analyze(scene):
    v=scene.seca_clearance
    v.report_json='';scene.pop('seca_clearance_signature',None)
    v.refinement_status='Not run'
    def fail(reason):
        v.status='NOT CHECKED: '+reason;v.report_json=json.dumps({'status':'NOT_CHECKED','reason':reason});update_preview(scene,[]);return None
    if not hasattr(scene,'seca_study'):return fail('Run seca_simulator.py first')
    s=scene.seca_study;pivot=scene.objects.get('CONTROL • transport pivot')
    if not pivot:return fail('Transport pivot missing')
    if scene.get('seca_level_active',False) or (hasattr(scene,'seca_level') and scene.seca_level.enabled):return fail('Exit leveling study')
    if not s.disconnected or s.loaded or not s.drip_guard_removed or s.cal_rod_placed or abs(s.transport_angle)<1e-4:return fail('Unload, disconnect, remove guard and rod, tilt')
    if not(-5<=s.previous_distance+s.arc_distance<=5 and -2*math.pi<=s.previous_yaw+s.arc_yaw<=2*math.pi):return fail('Arc exceeds transport control limits')
    bpy.context.view_layer.update();start=path_matrix(scene,0)
    if max(abs(start[i][j]-pivot.matrix_world[i][j]) for i in range(4) for j in range(4))>1e-4:return fail('Transport pose and controls differ')
    try:proxies=product_proxies(scene);obstacles=obstacle_boxes(scene,v.show_demo)
    except ValueError as exc:return fail(str(exc))
    n=max(1,math.ceil(abs(s.arc_distance)/v.step_m),math.ceil(abs(s.arc_yaw)/math.radians(v.step_deg)))
    if n>1000:return fail('Sampling limit exceeded')
    positions=[];first=None
    max_margin=max(abs(s.arc_distance)/(2*n)+2*p['radius']*math.sin(abs(s.arc_yaw)/(4*n))+.0001 for p in proxies)
    for i in range(n+1):
        f=i/n;m=path_matrix(scene,f);positions.append(m.translation.copy())
        if first is not None:continue
        for proxy in proxies:
            # Any point on the arc within half a sample interval can move no
            # farther than arc length plus this yaw chord. This inflates the
            # sampled AABB; it is not a signed clearance or contact solver.
            margin=abs(s.arc_distance)/(2*n)+2*proxy['radius']*math.sin(abs(s.arc_yaw)/(4*n))+.0001
            box=transform_box(proxy['lo'],proxy['hi'],m)
            for obstacle,ob in obstacles:
                if boxes_overlap(box,ob,margin):
                    center=Vector(tuple((proxy['lo'][j]+proxy['hi'][j])*.5 for j in range(3)));first={'fraction':f,'sample':i,'part':proxy['part'],'obstacle':obstacle,'margin_m':margin,'marker':tuple(m@center)};break
            if first is not None:break
    report={'status':'POSSIBLE_OVERLAP' if first else 'NO_PROXY_OVERLAP','samples':n+1,'proxy_count':len(proxies),'obstacles':[{'name':name,'bounds_m':bounds} for name,bounds in obstacles],'start':{'x_m':s.transport_x,'y_m':.267+s.transport_y,'heading_rad':s.transport_yaw},'step_m':v.step_m,'step_deg':v.step_deg,'distance_m':s.arc_distance,'turn_rad':s.arc_yaw,'tilt_rad':s.transport_angle,'max_margin_m':max_margin,'first':first,'scope':'Conservative axis-aligned proxy envelopes, frozen articulation and sampled arc; no physical collision or safety validation.'}
    signature=snapshot_signature(scene)
    if signature is None:clear_stale(scene,'snapshot inputs unavailable');return None
    scene['seca_clearance_signature']=signature
    v.report_json=json.dumps(report,separators=(',',':'))
    v.status=(f"Possible overlap: {first['part']} / {first['obstacle']} near {100*first['fraction']:.0f}%" if first else f'No proxy overlap in {n+1} samples')
    update_preview(scene,positions,Vector(first['marker']) if first else None);return report

def mesh_snapshot(obj,deps,space):
    """Copy evaluated triangle surfaces in the requested coordinate space."""
    ev=obj.evaluated_get(deps);mesh=ev.to_mesh()
    if mesh is None:raise ValueError('Cannot evaluate mesh: '+obj.name)
    try:
        mesh.calc_loop_triangles();transform=space@ev.matrix_world
        vertices=[transform@v.co for v in mesh.vertices]
        triangles=[tuple(t.vertices) for t in mesh.loop_triangles]
        if not vertices or not triangles:raise ValueError('No triangle surface: '+obj.name)
        return vertices,triangles
    finally:ev.to_mesh_clear()

def mesh_tree(vertices,triangles,matrix=None):
    points=[matrix@v for v in vertices] if matrix is not None else vertices
    tree=BVHTree.FromPolygons(points,triangles,all_triangles=True,epsilon=0)
    if tree is None:raise ValueError('Triangle tree could not be built')
    return tree

def refine(scene):
    """Test evaluated triangle surfaces at samples; not continuous or volumetric."""
    v=scene.seca_clearance;report=analyze(scene)
    if report is None:return None
    s=scene.seca_study;deps=bpy.context.evaluated_depsgraph_get();pivot=scene.objects['CONTROL • transport pivot'];inverse=pivot.matrix_world.inverted()
    try:
        proxies=product_proxies(scene);obstacles=obstacle_boxes(scene,v.show_demo)
        part_mesh={label:mesh_snapshot(scene.objects[name],deps,inverse) for label,name in PARTS}
        obstacle_mesh={name:mesh_snapshot(scene.objects[name],deps,Matrix.Identity(4)) for name,_ in obstacles}
        obstacle_trees={name:mesh_tree(*obstacle_mesh[name]) for name,_ in obstacles}
    except (ValueError,RuntimeError) as exc:
        v.refinement_status='Not checked: '+str(exc);report['mesh_refinement']={'status':'NOT_CHECKED','reason':str(exc)};v.report_json=json.dumps(report,separators=(',',':'));return report
    n=report['samples']-1;first=None;tested_pairs=0;tree_builds=0;sampled=0;limit=500;incomplete=False;failure=''
    for i in range(n+1):
        f=i/n;m=path_matrix(scene,f);candidates={}
        for proxy in proxies:
            box=transform_box(proxy['lo'],proxy['hi'],m)
            for obstacle,ob in obstacles:
                if boxes_overlap(box,ob):candidates.setdefault(proxy['part'],set()).add(obstacle)
        for label in sorted(candidates):
            if tree_builds>=limit:incomplete=True;failure='build limit reached';break
            vertices,triangles=part_mesh[label]
            try:tree=mesh_tree(vertices,triangles,m)
            except (ValueError,RuntimeError) as exc:incomplete=True;failure=str(exc);break
            tree_builds+=1
            for obstacle in sorted(candidates[label]):
                tested_pairs+=1
                try:pairs=tree.overlap(obstacle_trees[obstacle])
                except (ValueError,RuntimeError) as exc:incomplete=True;failure=str(exc);break
                if pairs:
                    pidx,oidx=pairs[0];triangle=triangles[pidx];center=sum((vertices[j] for j in triangle),Vector())/3
                    first={'fraction':f,'sample':i,'part':label,'obstacle':obstacle,'triangle_pair_count':len(pairs),'marker':tuple(m@center)};break
            if first or incomplete:break
        sampled=i+1
        if first or incomplete:break
    status='SAMPLED_SURFACE_OVERLAP' if first else 'INCOMPLETE' if incomplete else 'NO_SAMPLED_SURFACE_OVERLAP'
    report['mesh_refinement']={'status':status,'samples_examined':sampled,'sample_count':n+1,'tree_builds':tree_builds,'pair_tests':tested_pairs,'build_limit':limit,'failure':failure,'first':first,'scope':'Triangle-surface tests at discrete poses, frozen articulation and wheel orientation; containment and between-sample contact are not excluded.'}
    v.report_json=json.dumps(report,separators=(',',':'))
    if first:
        v.refinement_status=f"Sampled surfaces overlap: {first['part']} / {first['obstacle']} near {100*first['fraction']:.0f}%"
        spot=scene.objects.get('CLEARANCE • possible overlap marker')
        if spot:spot.location=Vector(first['marker']);spot.hide_set(False);spot.hide_render=False
        ghost=scene.objects.get('CLEARANCE • sampled part ghost')
        if ghost:
            vertices,triangles=part_mesh[first['part']];m=path_matrix(scene,first['fraction'])
            edges=sorted({tuple(sorted((a,b))) for tri in triangles for a,b in ((tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0]))})
            stride=max(1,math.ceil(len(edges)/3000));ghost.data.splines.clear()
            for a,b in edges[::stride]:
                sp=ghost.data.splines.new('POLY');sp.points.add(1)
                for point,index in zip(sp.points,(a,b)):
                    p=m@vertices[index];point.co=(p.x,p.y,p.z,1)
            ghost.hide_set(False);ghost.hide_render=False
    elif incomplete:v.refinement_status='Mesh pass incomplete: '+failure
    else:v.refinement_status=('No sampled surface overlap; proxy warning still applies' if report['status']=='POSSIBLE_OVERLAP' else 'No sampled surface or proxy overlap')
    return report

class SECA_PG_clearance(bpy.types.PropertyGroup):
    show_demo:BoolProperty(name='Show example doorway',default=False,update=sync_demo)
    step_m:FloatProperty(name='Distance step (m)',default=.025,min=.005,max=.1,precision=3,update=settings_changed)
    step_deg:FloatProperty(name='Yaw step (degrees)',default=2,min=.25,max=10,precision=2,update=settings_changed)
    status:StringProperty(default='Not checked')
    refinement_status:StringProperty(default='Not run')
    report_json:StringProperty(default='')

class SECA_OT_clearance(bpy.types.Operator):
    bl_idname='seca_clearance.analyze';bl_label='Check planned arc';bl_options={'REGISTER'}
    def execute(self,context):analyze(context.scene);return {'FINISHED'}

class SECA_OT_clearance_refine(bpy.types.Operator):
    bl_idname='seca_clearance.refine';bl_label='Check sampled mesh surfaces';bl_options={'REGISTER'}
    def execute(self,context):refine(context.scene);return {'FINISHED'}

class SECA_PT_clearance(bpy.types.Panel):
    bl_label='Clearance study — approximate';bl_idname='SECA_PT_clearance';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='seca study'
    def draw(self,context):
        l=self.layout;s=context.scene.seca_clearance;l.label(text='Snapshot only; not a safety check',icon='INFO');l.prop(s,'show_demo');l.prop(s,'step_m');l.prop(s,'step_deg');l.operator('seca_clearance.analyze');l.label(text=s.status);l.operator('seca_clearance.refine');l.label(text=s.refinement_status);l.label(text='Tracked input edits clear the snapshot');l.label(text='Recheck after other scene edits')

classes=(SECA_PG_clearance,SECA_OT_clearance,SECA_OT_clearance_refine,SECA_PT_clearance)
def register():
    remove_display_watchers()
    if hasattr(bpy.types.Scene,'seca_clearance'):del bpy.types.Scene.seca_clearance
    for c in reversed(classes):
        old=getattr(bpy.types,c.__name__,None)
        if old:bpy.utils.unregister_class(old)
    for c in classes:bpy.utils.register_class(c)
    bpy.types.Scene.seca_clearance=PointerProperty(type=SECA_PG_clearance)
    sync_demo(bpy.context.scene.seca_clearance,bpy.context)
    bpy.app.handlers.depsgraph_update_post.append(watch_snapshot)
def unregister():
    remove_display_watchers()
    if hasattr(bpy.types.Scene,'seca_clearance'):del bpy.types.Scene.seca_clearance
    for c in reversed(classes):bpy.utils.unregister_class(c)
if __name__=='__main__':register()
