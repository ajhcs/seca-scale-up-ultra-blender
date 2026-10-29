"""Generate a kinematic tilt/arc/lower timeline in a saved copy of the study.

Run seca_simulator.py first, unload, disconnect cables, and remove the guard
and study rod. Existing
animation on the three transport controls is preserved by refusing to replace it.
This visualization is not a physical or manufacturer-calibrated simulation.
"""
import bpy,math

scene=bpy.context.scene
if not hasattr(scene,'seca_study'):
    raise RuntimeError('Run seca_simulator.py first, then disconnect cables in the study controls.')
s=scene.seca_study
if (scene.get('seca_level_active',False) or (hasattr(scene,'seca_level') and scene.seca_level.enabled)):
    raise RuntimeError('Exit the leveling study before generating transport animation.')
if not s.disconnected or s.loaded:
    raise RuntimeError('Unload and mark cables disconnected before generating the animation.')
if not s.drip_guard_removed or s.cal_rod_placed:
    raise RuntimeError('Remove the drip guard and study rod before generating the animation.')
controls=[bpy.data.objects.get(n) for n in ('CONTROL • transport pivot','CONTROL • wheel L','CONTROL • wheel R')]
if any(o is None for o in controls):raise RuntimeError('Transport controls are missing.')
for o in controls:
    ad=o.animation_data
    if ad and (ad.action or len(ad.nla_tracks) or len(ad.drivers)):
        raise RuntimeError('Existing animation on '+o.name+' was preserved; use a separate copy.')
control,left,right=controls
if abs(control.rotation_euler.x)>1e-5:
    raise RuntimeError('Lower the device before generating the timeline.')

cfg=scene.get('transport_animation_config',{})
distance=float(cfg.get('distance_m',.6));turn=float(cfg.get('turn_radians',math.pi/4));tilt=float(cfg.get('tilt_radians',math.radians(15)))
first=int(cfg.get('start_frame',1));tilt_frames=int(cfg.get('tilt_frames',24));travel_frames=int(cfg.get('travel_frames',96));lower_frames=int(cfg.get('lower_frames',24));fps=int(cfg.get('fps',24))
if not(-5<=distance<=5 and -2*math.pi<=turn<=2*math.pi and 0<=tilt<=math.radians(25) and first>=1 and min(tilt_frames,travel_frames,lower_frames)>=2 and 1<=fps<=120):
    raise ValueError('Transport animation settings are outside the study control limits.')
radius=.043;track=.46
start_x,start_y,start_z=control.location;heading=control.rotation_euler.z;left0=left.rotation_euler.x;right0=right.rotation_euler.x
finish_tilt=first+tilt_frames;finish_travel=finish_tilt+travel_frames;finish=finish_travel+lower_frames
def smooth(t):
    t=max(0,min(1,t));return t*t*(3-2*t)
for frame in range(first,finish+1):
    if frame<=finish_tilt:
        pitch=tilt*smooth((frame-first)/tilt_frames);u=0
    elif frame<=finish_travel:
        pitch=tilt;u=smooth((frame-finish_tilt)/travel_frames)
    else:
        pitch=tilt*(1-smooth((frame-finish_travel)/lower_frames));u=1
    angle=turn*u;ds=distance*u
    if abs(turn)<1e-9:
        x=start_x-math.sin(heading)*ds;y=start_y+math.cos(heading)*ds
    else:
        x=start_x+(math.cos(heading+angle)-math.cos(heading))*distance/turn
        y=start_y+(math.sin(heading+angle)-math.sin(heading))*distance/turn
    control.location=(x,y,start_z);control.rotation_euler.x=-pitch;control.rotation_euler.z=heading+angle
    left.rotation_euler.x=left0-(ds-track*angle/2)/radius+pitch
    right.rotation_euler.x=right0-(ds+track*angle/2)/radius+pitch
    control.keyframe_insert(data_path='location',frame=frame,group='Transport path')
    control.keyframe_insert(data_path='rotation_euler',index=0,frame=frame,group='Tilt')
    control.keyframe_insert(data_path='rotation_euler',index=2,frame=frame,group='Heading')
    left.keyframe_insert(data_path='rotation_euler',index=0,frame=frame,group='Left wheel')
    right.keyframe_insert(data_path='rotation_euler',index=0,frame=frame,group='Right wheel')
for obj in controls:
    action=obj.animation_data.action;action.name='Transport study • '+obj.name
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                for fc in channelbag.fcurves:
                    for kp in fc.keyframe_points:kp.interpolation='LINEAR'
for name,frame in [('Tilt begins',first),('Roll begins',finish_tilt),('Lower begins',finish_travel),('Transport ends',finish)]:
    m=scene.timeline_markers.new(name);m.frame=frame
scene.frame_start=first;scene.frame_end=finish;scene.render.fps=fps;scene.render.fps_base=1
scene['transport_animation_scope']='Kinematic visualization only; radius, track, tilt and timing are uncalibrated; not a physical simulation.'
scene.frame_set(first)
print('TRANSPORT_TIMELINE_GENERATED',first,finish,flush=True)
