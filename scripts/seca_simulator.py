"""Interactive, explicitly simulated seca Scale-up study for Blender 5.2.

Run from Blender's Text Editor. No network connections or patient data are used.
"""
import bpy, math, time, json
from bpy.props import BoolProperty, FloatProperty, IntProperty, EnumProperty, StringProperty, PointerProperty
from bpy_extras import view3d_utils
from mathutils import Vector

_geometry_ns={'__name__':'seca_platform_geometry'}
exec(bpy.data.texts['platform_geometry.py'].as_string(),_geometry_ns)
platform_surface_z=_geometry_ns['platform_surface_z']

# Deliberately approximate study profiles, not recovered firmware parameters.
FILTER_PROFILES={'LOW':(.20,.35,.08),'MEDIUM':(.45,.70,.08),'HIGH':(.75,1.20,.08)}
_sample_windows={}

# seca 654/655 manual (firmware 2.1), pp. 83 and 85: 0.5 kg is the
# voice-guided measurement trigger for applicable combinations, and 1 kg is
# the minimum capacity of the non-verified seca 654. These are distinct from
# the adjustable, hypothetical gate used by this study's manual height action.
VOICE_TRIGGER_KG = 0.5
SECA_654_MIN_CAPACITY_KG = 1.0
SECA_654_MAX_CAPACITY_KG = 360.0

def load_reference_status(s):
    """Describe synthetic gross input against published figures, without emulating firmware."""
    if s.disconnected or not s.loaded:
        return 'NO_LOAD'
    if s.gross_kg > SECA_654_MAX_CAPACITY_KG:
        return 'OVER_CAPACITY'
    if s.gross_kg < SECA_654_MIN_CAPACITY_KG:
        return 'BELOW_MINIMUM'
    return 'IN_RANGE'

def voice_reference_reached(s):
    # Study threshold event; hysteresis and device timing remain unverified.
    return not s.disconnected and s.loaded and s.gross_kg >= VOICE_TRIGGER_KG

# Reference-supported sequence only: the placeholder rod dimensions, timing and
# pass criteria are assumptions, and no device calibration is performed.
def sync_calibration_rod(scene,reposition=True):
    s=scene.seca_study;o=bpy.data.objects.get('CONTROL • calibration rod')
    if not o:return
    if reposition:o.location.x=s.cal_rod_x;o.location.y=s.cal_rod_y
    for child in o.children:
        child.hide_set(not s.cal_rod_placed);child.hide_render=not s.cal_rod_placed

def rod_centered(scene):
    root=bpy.data.objects.get('CONTROL • product root');rod=bpy.data.objects.get('CONTROL • calibration rod')
    if not root or not rod:return False
    bpy.context.view_layer.update();p=root.matrix_world.inverted()@rod.matrix_world.translation
    return math.hypot(p.x,p.y+.075)<=.02

def calibration_fail(scene,message):
    s=scene.seca_study;s.cal_stage='FAILED';s.cal_valid=False;s.cal_elapsed=0;s.message=message

def calibration_rod_changed(self,context,reposition=True):
    if not context or not context.scene or not hasattr(context.scene,'seca_study'):return
    scene=context.scene;s=scene.seca_study;sync_calibration_rod(scene,reposition)
    if s.cal_stage=='WAIT_ROD' and s.cal_rod_placed:
        if s.disconnected or s.loaded or not s.cal_area_clear:calibration_fail(scene,'Calibration conditions changed')
        elif not rod_centered(scene):calibration_fail(scene,'Study rod is off center')
        else:s.cal_stage='ROD_SCAN';s.cal_elapsed=0;s.cal_duration_snapshot=s.cal_duration;s.message='Study rod scan in progress'
    elif s.cal_stage=='ROD_SCAN' and (not s.cal_rod_placed or not rod_centered(scene)):
        calibration_fail(scene,'Study rod moved or removed')
    refresh(scene)

def calibration_conditions_changed(self,context):
    if not context or not context.scene or not hasattr(context.scene,'seca_study'):return
    scene=context.scene;s=scene.seca_study
    if s.cal_stage in {'EMPTY_SCAN','ROD_SCAN'} and not s.cal_area_clear:calibration_fail(scene,'Calibration clearance changed')
    refresh(scene)

def advance_calibration(scene,seconds):
    if check_platform_change(scene):return True
    s=scene.seca_study
    if s.cal_stage not in {'EMPTY_SCAN','ROD_SCAN'}:return False
    if s.disconnected or s.loaded or not s.cal_area_clear:
        calibration_fail(scene,'Calibration conditions changed');refresh(scene);return True
    if s.cal_stage=='EMPTY_SCAN' and s.cal_rod_placed:
        calibration_fail(scene,'Remove study rod for empty scan');refresh(scene);return True
    if s.cal_stage=='ROD_SCAN' and (not s.cal_rod_placed or not rod_centered(scene)):
        calibration_fail(scene,'Study rod moved or removed');refresh(scene);return True
    s.cal_elapsed+=max(0,min(float(seconds),60))
    # RNA float properties accumulate small rounding error across 50 ms ticks.
    if s.cal_elapsed+1e-5*max(1.0,s.cal_duration_snapshot)>=s.cal_duration_snapshot:
        if s.cal_stage=='EMPTY_SCAN':s.cal_stage='WAIT_ROD';s.message='Place study rod centrally'
        else:s.cal_stage='SUCCESS';s.message='Study calibration complete'
        s.cal_elapsed=0
    refresh(scene);return True

def calibration_screen(scene):
    s=scene.seca_study
    content={
      'INTRO':('Calibration requires','the supplied rod.','Study only.','OK'),
      'WAIT_EMPTY':('Unload the scale.','Keep the area clear.','Then press Start.','START'),
      'EMPTY_SCAN':('Empty-platform scan','in progress.','','WAIT'),
      'WAIT_ROD':('Place the study rod','at the center of','the foot outlines.','WAIT'),
      'ROD_SCAN':('Study rod scan','in progress.','','WAIT'),
      'SUCCESS':('Study calibration','completed.','Remove the rod next.','OK'),
      'REMOVE_ROD':('Remove the study rod','from the platform.','','DONE'),
      'FAILED':('Study calibration failed.','Check the conditions.','Retry if appropriate.','RETRY'),
    }
    lines=content.get(s.cal_stage,('','','',''))
    for i in range(3):
        o=bpy.data.objects.get('CAL • line %d'%i)
        if o:o.data.body=lines[i]
    o=bpy.data.objects.get('CAL • next')
    if o:o.data.body=lines[3]

def sync_phantom(scene):
    s=scene.seca_study;visible=s.height_source in {'GEOMETRY','ARRAY','FAN'} and s.cal_stage=='IDLE'
    for o in bpy.data.objects:
        if o.name.startswith('PHANTOM • '):o.hide_set(not visible);o.hide_render=not visible
    datum=platform_surface_z(scene,0,.070)
    if datum is None:
        for o in bpy.data.objects:
            if o.name.startswith('PHANTOM • '):o.hide_set(True);o.hide_render=True
        return
    h=s.height_cm/100
    head=bpy.data.objects.get('PHANTOM • head')
    if head:head.location=(0,.070,datum+h-.10)
    torso=bpy.data.objects.get('PHANTOM • torso')
    if torso:torso.location=(0,.070,datum+h*.64);torso.scale.z=h*.24
    for side in ('L','R'):
        leg=bpy.data.objects.get('PHANTOM • leg '+side)
        if leg:leg.location.z=datum+h*.24;leg.scale.z=h*.24

# Nominal coordinates are retained for reference and older study scripts only.
# The live rays use evaluated aperture object transforms, not these constants.
ARRAY_POSITIONS=[(-.0145,-.006),(.0145,-.006),(-.0145,.046),(.0145,.046),(-.0145,.098),(.0145,.098)]
SENSOR_OBJECTS=[f'257 • sensor opening appearance {i} {side}' for i in range(1,4) for side in ('L','R')]
HEAD_REFERENCE_OBJECTS=['257 • head lower shell']+SENSOR_OBJECTS

def study_ray(scene,name,local_origin,deps):
    obj=scene.objects.get(name)
    if obj is None:return None
    try:
        m=obj.evaluated_get(deps).matrix_world
        if abs(m.determinant())<1e-12:return None
        origin=m@Vector(local_origin);direction=m.to_3x3()@Vector((0,0,-1))
        if direction.length<1e-12 or not all(math.isfinite(v) for v in (*origin,*direction)):return None
        return origin,direction.normalized()
    except (ValueError,RuntimeError,ReferenceError):return None

def geometry_height(scene):
    root=scene.objects.get('CONTROL • product root');head=scene.objects.get('PHANTOM • head')
    if not root or not head:return None,'Subject geometry missing'
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();ray=study_ray(scene,'257 • head lower shell',(0,-.030,-.008),deps)
    if ray is None:return None,'Head geometry unavailable'
    inverse=root.evaluated_get(deps).matrix_world.inverted();hit,point,normal,index,obj,matrix=scene.ray_cast(deps,*ray)
    if not hit or obj!=head:return None,'Sensor ray obstructed'
    target=inverse@point;datum=platform_surface_z(scene,target.x,target.y,deps)
    if datum is None:return None,'Platform surface unavailable'
    return (target.z-datum)*100,''

# The local start lies just below the modeled opening to avoid self-occlusion.
# Rays, offsets, pairing and aggregation are study assumptions, not acoustics.
def array_height(scene):
    s=scene.seca_study;root=scene.objects.get('CONTROL • product root');head=scene.objects.get('PHANTOM • head')
    if not root or not head:return None,'Subject geometry missing',''
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();inverse=root.evaluated_get(deps).matrix_world.inverted();readings=[]
    for name in SENSOR_OBJECTS:
        ray=study_ray(scene,name,(0,0,-.0132),deps)
        if ray is None:
            s.array_valid_pairs=0;s.array_spread_cm=0;s.array_detail_json='[]'
            return None,'Head geometry unavailable',''
        origin,direction=ray;hit,point,normal,index,obj,matrix=scene.ray_cast(deps,origin,direction)
        sample=inverse@(point if hit and obj==head else origin);datum=platform_surface_z(scene,sample.x,sample.y,deps)
        if datum is None:
            s.array_valid_pairs=0;s.array_spread_cm=0;s.array_detail_json='[]'
            return None,'Platform surface unavailable',''
        readings.append(round((sample.z-datum)*100,4) if hit and obj==head else None)
    pairs=[(readings[i]+readings[i+1])/2 for i in (0,2,4) if readings[i] is not None and readings[i+1] is not None]
    s.array_valid_pairs=len(pairs);s.array_spread_cm=max(pairs)-min(pairs) if pairs else 0
    signature=json.dumps(readings,separators=(',',':'));s.array_detail_json=signature
    if len(pairs)<s.array_min_pairs:return None,'Not enough valid sensor pairs',signature
    ordered=sorted(pairs);n=len(ordered);value=ordered[n//2] if n%2 else (ordered[n//2-1]+ordered[n//2])/2
    return value,'',signature

# A geometric first-return fan study, not an acoustic wave solver or
# recovered device algorithm; every beam and material parameter is adjustable.
def fan_height(scene):
    s=scene.seca_study;root=scene.objects.get('CONTROL • product root');head=scene.objects.get('PHANTOM • head')
    def failed(message):
        s.array_valid_pairs=0;s.array_spread_cm=0;s.array_detail_json='[]';s.fan_trace_json='[]';s.fan_summary=message
        return None,message,''
    if not root or not head:return failed('Subject geometry missing')
    if any(o.get('fan_diagnostic_visual',False) and not o.hide_get() for o in scene.objects):return failed('Hide diagnostic rays before sampling')
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();inverse=root.evaluated_get(deps).matrix_world.inverted()
    sound_speed=331.3+.606*s.fan_temperature_c;readings=[];sources=[];scores=[];trace=[];actual_hits=0;other_hits=0
    spread=math.radians(s.fan_half_angle_deg)
    directions=[(0.0,0.0)]
    if spread>1e-9:
        for ring,count in ((1,6),(2,12)):
            for k in range(count):directions.append((spread*ring/2,2*math.pi*k/count))
    for name in SENSOR_OBJECTS:
        sensor=scene.objects.get(name)
        if sensor is None:return failed('Head geometry unavailable')
        mat=sensor.evaluated_get(deps).matrix_world
        if abs(mat.determinant())<1e-12:return failed('Head geometry unavailable')
        origin=mat@Vector((0,0,-.0132));candidates=[]
        for theta,phi in directions:
            local=Vector((math.sin(theta)*math.cos(phi),math.sin(theta)*math.sin(phi),-math.cos(theta)))
            direction=mat.to_3x3()@local
            if direction.length<1e-12:continue
            direction.normalize();hit,point,normal,index,obj,matrix=scene.ray_cast(deps,origin,direction,distance=s.fan_max_distance_m)
            end=point if hit else origin+direction*s.fan_max_distance_m
            is_head=bool(hit and obj==head);reflectivity=0.0;score=0.0;distance=(end-origin).length
            if hit:
                if is_head:actual_hits+=1
                else:other_hits+=1
                try:reflectivity=float(obj.get('study_ultrasound_reflectivity',1.0 if is_head else .5))
                except (ValueError,TypeError):reflectivity=0.0
                if not math.isfinite(reflectivity):reflectivity=0.0
                reflectivity=max(0.0,min(1.0,reflectivity));incidence=abs(normal.normalized().dot(direction))
                score=reflectivity*(incidence**2)*math.exp(-s.fan_attenuation_per_m*distance)/max(.01,distance*distance)
                if score>=s.fan_threshold and reflectivity>0:candidates.append((score,distance,direction.copy(),obj.name))
            trace.append({'sensor':name,'origin':[round(v,6) for v in origin],'end':[round(v,6) for v in end],'object':obj.name if hit else '', 'head':is_head,'strength':round(score,6),'distance_m':round(distance,6)})
        if not candidates:
            readings.append(None);sources.append('');scores.append(None);continue
        strength,distance,direction,source=max(candidates,key=lambda v:v[0]);estimated_distance=distance*s.fan_assumed_speed_mps/sound_speed
        estimated=inverse@(origin+direction*estimated_distance);datum=platform_surface_z(scene,estimated.x,estimated.y,deps)
        readings.append(round((estimated.z-datum)*100,4) if datum is not None else None);sources.append(source);scores.append(round(strength,4))
    pairs=[(readings[i]+readings[i+1])/2 for i in (0,2,4) if readings[i] is not None and readings[i+1] is not None]
    s.array_valid_pairs=len(pairs);s.array_spread_cm=max(pairs)-min(pairs) if pairs else 0
    s.fan_summary=f'{actual_hits} head hits, {other_hits} other hits; {len(pairs)} pairs';s.fan_trace_json=json.dumps(trace,separators=(',',':'))
    signature=json.dumps(readings+sources+scores,separators=(',',':'));s.array_detail_json=signature
    if len(pairs)<s.array_min_pairs:return None,'Not enough valid fan pairs',signature
    ordered=sorted(pairs);n=len(ordered);value=ordered[n//2] if n%2 else (ordered[n//2-1]+ordered[n//2])/2
    return value,'',signature

def fan_parameter_changed(self,context):
    if context and context.scene and hasattr(context.scene,'seca_study') and self.height_source=='FAN':source_changed(self,context)

def height_candidate(scene):
    s=scene.seca_study
    if s.height_source=='FAN':return fan_height(scene)
    if s.height_source=='ARRAY':return array_height(scene)
    if s.height_source=='GEOMETRY':
        value,error=geometry_height(scene);return value,error,''
    return s.height_cm,'',''

def array_changed(before,after):
    if not before and not after:return False
    try:a=json.loads(before);b=json.loads(after)
    except (TypeError,ValueError):return True
    if len(a)!=len(b):return True
    for x,y in zip(a,b):
        if (x is None)!=(y is None):return True
        if x is None:continue
        if isinstance(x,str) or isinstance(y,str):
            if x!=y:return True
        elif abs(x-y)>.05:return True
    return False

# Synthesized substitutes only. The reference describes short/long beeps, but
# does not supply waveform, cadence, volume calibration or voice recordings.
AUDIO_FREQUENCY=880.0
AUDIO_INTERVAL=.5
AUDIO_DURATIONS={'short':.08,'long':.40}
_audio_device=None
_audio_handles=[]
_voice_handles=[]
_voice_next_end=0.0

def stop_beeps():
    global _audio_handles
    for handle in _audio_handles:
        try:handle.stop()
        except Exception:pass
    _audio_handles=[]

def stop_voice(kind=None):
    global _voice_handles,_voice_next_end
    kept=[];now=time.monotonic()
    for handle,category,end in _voice_handles:
        if kind is None or kind==category:
            try:handle.stop()
            except Exception:pass
        elif end>now:kept.append((handle,category,end))
    _voice_handles=kept;_voice_next_end=max([end for _,_,end in kept],default=now)

def stop_audio():
    stop_beeps();stop_voice()


def audio_setting_changed(self,context):
    if not context or not context.scene or not hasattr(context.scene,'seca_study'):return
    if self.audio_volume==0:stop_audio();self.audio_status='Audio muted'
    elif not self.beeps_enabled:stop_beeps();self.audio_status='Beeps muted'
    else:self.audio_status='No playback requested'
    refresh(context.scene)

def synthesized_beep(kind,level):
    import aud
    duration=AUDIO_DURATIONS[kind]
    return aud.Sound.sine(AUDIO_FREQUENCY).limit(0,duration).fadein(0,.005).fadeout(duration-.005,.005).volume(.08*level/5)

def emit_beep(scene,kind,elapsed):
    global _audio_device
    s=scene.seca_study
    if s.disconnected or not s.beeps_enabled or s.audio_volume<=0:return
    s.audio_sequence+=1
    try:events=json.loads(s.audio_events or '[]')
    except (ValueError,TypeError):events=[]
    events.append({'sequence':s.audio_sequence,'kind':kind,'elapsed_s':round(elapsed,4),'duration_s':AUDIO_DURATIONS[kind],'volume_level':s.audio_volume})
    s.audio_events=json.dumps(events[-128:],separators=(',',':'))
    if bpy.app.background:s.audio_status='Background: event logged';return
    try:
        import aud
        if _audio_device is None:_audio_device=aud.Device()
        tone=synthesized_beep(kind,s.audio_volume)
        _audio_handles.append(_audio_device.play(tone));s.audio_status='Playback requested'
    except Exception:
        s.audio_status='Audio output unavailable'

# These English study phrases and event timings are invented placeholders,
# not transcriptions or recordings of the device's voice prompts.
VOICE_PHRASES={
 'guidance_clothing':'Remove heavy items before measuring.',
 'guidance_id':'Scan the fictional identification.',
 'guidance_weight':'Stand still for the weight measurement.',
 'guidance_height':'Stand upright for height measurement.',
 'guidance_finished':'The measurement is complete.'}

def voice_settings_changed(self,context):
    if not context or not context.scene or not hasattr(context.scene,'seca_study'):return
    if not self.voice_guidance_enabled:stop_voice('guidance')
    if not self.voice_results_enabled:stop_voice('results')
    refresh(context.scene)

def voice_integer_tokens(n):
    if n<20:return ['n_'+str(n)]
    if n<100:return ['n_'+str((n//10)*10)]+([] if n%10==0 else ['n_'+str(n%10)])
    if n<1000:return ['n_'+str(n//100),'hundred']+([] if n%100==0 else voice_integer_tokens(n%100))
    if n<1000000:return voice_integer_tokens(n//1000)+['thousand']+([] if n%1000==0 else voice_integer_tokens(n%1000))
    return ['n_'+c for c in str(n)]

def voice_number_tokens(value):
    value=str(value);negative=value.startswith('-');value=value.lstrip('-');head,sep,tail=value.partition('.')
    tokens=(['minus'] if negative else [])+voice_integer_tokens(int(head or '0'))
    if sep:tokens+=['point']+['n_'+c for c in tail if c.isdigit()]
    return tokens

def voice_result(s):
    weight=weight_display(displayed_gross(s)-s.tare_kg,s.weight_units)
    wu='kilograms' if s.weight_units=='KG' else 'pounds'
    parts=['Weight '+weight+' '+wu];tokens=['weight']+voice_number_tokens(weight)+[wu]
    height=s.measured_height_cm if s.state=='RESULT' else 0
    if height>0:
        h=height_display(height,s.height_units)
        if s.height_units=='CM':
            parts.append('Height '+h+' centimeters');tokens+=['height']+voice_number_tokens(h)+['centimeters']
        else:
            eighths=int(math.floor(height/2.54*8+0.5));feet,eighths=divmod(eighths,96);inches,num=divmod(eighths,8)
            parts.append('Height '+h+' feet and inches');tokens+=['height']+voice_number_tokens(str(feet))+['feet']+voice_number_tokens(str(inches))
            if num:
                div=math.gcd(num,8);tokens+=voice_number_tokens(str(num//div))+['over']+voice_number_tokens(str(8//div))
            tokens+=['inches']
        if s.indicator=='BMI':
            display_bmi=body_size(quantize(displayed_gross(s)-s.tare_kg,.05),height,'BMI')
            if display_bmi:
                bmi=display_bmi.split()[0];parts.append('BMI '+bmi);tokens+=['bmi']+voice_number_tokens(bmi)
    return '; '.join(parts),tokens

def voice_sound(pack_dir,tokens):
    # User-provided clips are normalized to a common format and concatenated;
    # no patient or other arbitrary strings are used to form file names.
    import aud
    if pack_dir:
        from pathlib import Path
        directory=Path(bpy.path.abspath(pack_dir))/'en'
        files=[directory/(token+'.wav') for token in tokens]
        missing=[p.name for p in files if not p.is_file()]
        if missing:return None,missing
        sounds=[aud.Sound.file(str(p)).resample(48000).rechannel(1) for p in files]
    else:
        import io,wave,numpy as np
        clips=[bpy.data.sounds.get('STUDY VOICE • '+token) for token in tokens]
        missing=[token+'.wav' for token,clip in zip(tokens,clips) if clip is None or clip.packed_file is None]
        if missing:return None,missing
        sounds=[]
        for clip in clips:
            with wave.open(io.BytesIO(bytes(clip.packed_file.data)),'rb') as w:
                if w.getsampwidth()!=2 or w.getnchannels()!=1:raise ValueError('Unsupported embedded WAV')
                rate=w.getframerate();samples=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32).reshape(-1,1)/32768.0
            sounds.append(aud.Sound.buffer(samples,rate).resample(48000).rechannel(1))
    if not sounds:return None,[]
    sound=sounds[0]
    for part in sounds[1:]:sound=sound.join(part)
    return sound,[]

def emit_voice(scene,kind,cue):
    global _audio_device,_voice_handles,_voice_next_end
    s=scene.seca_study
    if s.disconnected or (kind=='guidance' and not s.voice_guidance_enabled) or (kind=='results' and not s.voice_results_enabled):return
    if kind=='results':text_value,tokens=voice_result(s)
    else:text_value=VOICE_PHRASES[cue];tokens=[cue]
    status='muted' if s.audio_volume<=0 else 'no voice pack'
    missing=[];sound=None
    if s.audio_volume>0:
        try:
            sound,missing=voice_sound(s.voice_pack_dir,tokens)
            status='missing clips' if missing else 'prepared'
        except Exception:status='voice pack unavailable'
    if sound is not None:
        if bpy.app.background:status='prepared in background'
        else:
            try:
                import aud
                if _audio_device is None:_audio_device=aud.Device()
                now=time.monotonic();_voice_handles=[entry for entry in _voice_handles if entry[2]>now]
                delay=max(0.0,_voice_next_end-now);duration=max(0.0,sound.length/sound.specs[0]);end=now+delay+duration
                _voice_handles.append((_audio_device.play(sound.volume(.08*s.audio_volume/5).delay(delay)),kind,end));_voice_next_end=end;status='playback requested'
            except Exception:status='audio output unavailable'
    s.voice_sequence+=1
    try:events=json.loads(s.voice_events or '[]')
    except (ValueError,TypeError):events=[]
    events.append({'sequence':s.voice_sequence,'kind':kind,'cue':cue,'language':s.voice_language,'text':text_value,'tokens':tokens,'volume_level':s.audio_volume,'status':status,'missing':missing})
    s.voice_events=json.dumps(events[-128:],separators=(',',':'));s.voice_status=status

def begin_height_audio(scene):
    stop_audio();s=scene.seca_study;s.audio_next_beep=AUDIO_INTERVAL;emit_beep(scene,'short',0)

def progress_height_audio(scene,elapsed,duration):
    s=scene.seca_study
    while s.audio_next_beep<duration-1e-6 and s.audio_next_beep<=elapsed+1e-6:
        emit_beep(scene,'short',s.audio_next_beep);s.audio_next_beep+=AUDIO_INTERVAL

def cancel_height(scene,message):
    s=scene.seca_study
    stop_audio()
    if not s.height_measuring:return
    s.height_measuring=False;s.height_elapsed=0
    if s.view_mode=='MEASURING':s.view_mode='MAIN'
    if s.measurement_mode=='SELF' and s.self_stage=='HEIGHT_RUNNING':s.self_stage='HEIGHT_PREP';s.view_mode='SELF'
    s.message=message

def finish_height(scene,value,signature):
    s=scene.seca_study;was_timed=s.height_measuring;s.height_measuring=False;s.height_elapsed=0
    if value is None:s.state='WEIGHED';s.measured_height_cm=0;s.view_mode='MAIN';s.message='Sensor reading unavailable'
    elif not 100<=quantize(value,.1)<=220:s.state='WEIGHED';s.measured_height_cm=0;s.view_mode='MAIN';s.message='Height outside 100–220 cm'
    else:
        emit_beep(scene,'long',s.height_duration_snapshot if was_timed else 0)
        s.geometry_snapshot_cm=value;s.array_snapshot_json=signature;s.preview_height_cm=quantize(value,.1);s.measured_height_cm=0;s.state='WEIGHED';s.view_mode='HEIGHT';s.message='Review simulated height'
    if s.measurement_mode=='SELF' and s.self_stage=='HEIGHT_RUNNING':
        s.self_stage='HEIGHT_READ' if value is not None and 100<=quantize(value,.1)<=220 else 'HEIGHT_PREP'
        s.view_mode='SELF'

def advance_height(scene,seconds):
    s=scene.seca_study
    if not s.height_measuring:return False
    if s.disconnected or not s.loaded or s.state!='WEIGHED' or s.view_mode!='MEASURING':
        cancel_height(scene,'Height measurement interrupted');refresh(scene);return True
    value,error,signature=height_candidate(scene)
    if value is None or abs(value-s.geometry_snapshot_cm)>.05 or array_changed(s.array_snapshot_json,signature):
        cancel_height(scene,error or 'Geometry changed; remeasure');refresh(scene);return True
    s.height_elapsed+=max(0,min(float(seconds),60))
    progress_height_audio(scene,s.height_elapsed,s.height_duration_snapshot)
    # Keep the simulated duration boundary robust to float32 tick accumulation.
    if s.height_elapsed+1e-5*max(1.0,s.height_duration_snapshot)>=s.height_duration_snapshot:finish_height(scene,value,signature)
    refresh(scene);return True

def invalidate_changed_geometry(scene):
    s=scene.seca_study
    if (s.height_result_manual and s.state=='RESULT') or s.height_source not in {'GEOMETRY','ARRAY','FAN'} or not s.loaded or not(s.state=='RESULT' or s.view_mode=='HEIGHT'):return False
    value,error,signature=height_candidate(scene)
    if value is None or abs(value-s.geometry_snapshot_cm)>.05 or array_changed(s.array_snapshot_json,signature):
        clear_held(s);s.state='WEIGHED';s.view_mode='MAIN';s.measured_height_cm=0;s.message='Geometry changed; remeasure'
        if s.measurement_mode=='SELF':s.self_stage='WEIGHT';s.view_mode='SELF'
        return True
    return False

def clear_samples(scene):
    _sample_windows.pop(scene.as_pointer(),None)

def displayed_gross(s):
    return s.filtered_kg if s.dynamic_weight and s.loaded else s.gross_kg

def update_tare_total(s):
    base=0 if s.preset_suppressed else (s.clothing_kg if s.clothing_active else s.pre_tare_kg)
    total=base+s.additional_kg+s.scanned_kg+s.adult_kg
    if total>360.00001:return False
    s.tare_kg=total
    return True

def set_tare_component(s,name,value):
    if value<0 or value>360:return False
    old=getattr(s,name);setattr(s,name,value)
    if update_tare_total(s):return True
    setattr(s,name,old);update_tare_total(s);return False

def clear_temporary_tares(s,suppress_preset=False):
    s.clothing_active=False;s.clothing_kg=0;s.additional_kg=0;s.scanned_kg=0;s.adult_kg=0
    s.preset_suppressed=suppress_preset;s.mother_stage='NONE';update_tare_total(s)

def clear_held(s):
    s.held_valid=False;s.manual_hold=False;s.held_net_kg=0;s.held_height_cm=0;s.held_tare_kg=0;s.held_elapsed=0

def invalidate_after_setup_change(scene):
    """Conservative study rule, not a claim about seca firmware behavior.

    The current reading and synthetic calibration no longer describe the
    modeled setup. Historical recall and the immutable mock outbox are kept.
    """
    if not hasattr(scene,'seca_study'):return
    s=scene.seca_study
    clear_samples(scene);clear_held(s);cancel_height(scene,'Setup changed; remeasure')
    s.cal_valid=False;s.setup_remeasure_required=True
    if s.cal_stage!='IDLE':calibration_fail(scene,'Setup changed; recalibrate study')
    elif s.view_mode in {'HEIGHT','MEASURING','OVERVIEW','MANUAL_HEIGHT'}:s.view_mode='MAIN'
    s.measured_height_cm=0;s.height_result_manual=False
    if s.mother_stage!='NONE':s.mother_stage='NONE';s.adult_kg=0;update_tare_total(s)
    if s.loaded and not s.disconnected and s.state!='OVERLOAD':
        s.filtered_kg=0;s.sample_time=0;s.state='UNSTABLE'
    elif not s.loaded or s.disconnected:s.state='READY'
    if s.measurement_mode=='SELF':s.self_stage='WEIGHT' if s.loaded else 'READY';s.view_mode='SELF'
    s.message='Setup changed; recalibrate study'
    refresh(scene)
    scene['seca_setup_dirty']=False

def effective_hold(s):
    return s.autohold or s.mock_network

def retention_policy(s):
    # Network workflows are configuration-dependent; this study uses reload.
    return 'RELOAD' if s.mock_network else s.clear_policy

def advance_retention(scene,seconds):
    s=scene.seca_study
    if s.state!='HELD' or s.loaded or s.disconnected or retention_policy(s)!='TIMEOUT':return False
    s.held_elapsed+=max(0,min(float(seconds),60))
    if s.held_elapsed>=s.clear_timeout:
        clear_held(s);s.state='READY';s.message='Scale ready';refresh(scene);return True
    return False

# Mock-network Clear Data study, based on the documented menu and bounds.
# The clock-start, interruption and snapshot-retention rules are study assumptions.
def arm_network_clear(scene):
    s=scene.seca_study
    if s.mock_network and not s.disconnected and not s.net_clear_busy:
        s.net_clear_elapsed=0;s.net_clear_armed=True

def patient_id_changed(self,context):
    if not context or not context.scene or not hasattr(context.scene,'seca_study'):return
    s=context.scene.seca_study
    if s.synthetic_id.strip() and not s.net_clear_busy:arm_network_clear(context.scene)
    refresh(context.scene)

def advance_network_clear(scene,seconds):
    s=scene.seca_study
    if not s.mock_network or s.disconnected or not s.net_clear_armed:return False
    dt=float(seconds)
    if not math.isfinite(dt) or dt<=0:return False
    s.net_clear_elapsed=min(s.net_clear_seconds,s.net_clear_elapsed+min(dt,60))
    if s.net_clear_elapsed+1e-5 < s.net_clear_seconds:return False
    s.net_clear_busy=True
    try:
        stop_audio();cancel_height(scene,'Mock clear-data timeout');clear_samples(scene);clear_held(s);clear_temporary_tares(s)
        s.synthetic_id='';s.self_id='';s.has_last=False;s.last_kg=0;s.last_net_kg=0;s.last_height_cm=0;s.measured_height_cm=0;s.height_result_manual=False
        s.net_data_expired=True;s.net_clear_armed=False;s.net_clear_elapsed=0
        if s.loaded:s.state='UNSTABLE';s.setup_remeasure_required=True
        else:s.state='READY'
        if s.view_mode!='SETTINGS':
            if s.measurement_mode=='SELF':s.self_stage='READY';s.view_mode='SELF'
            else:s.view_mode='MAIN'
        s.message='Mock displayed data cleared'
    finally:s.net_clear_busy=False
    refresh(scene);return True

def mock_link_ready(s):
    # These are local exercise states only, not real link or service checks.
    if not s.mock_network or s.disconnected:return False
    if s.mock_transport=='LAN':return s.mock_lan_state=='CONNECTED'
    return s.mock_wifi_signal in {'VERY_WEAK','WEAK','GOOD','OPTIMAL'} and s.mock_wifi_associated

def mock_link_description(s):
    if not s.mock_network:return 'Standalone'
    if s.mock_transport=='LAN':return 'LAN: '+{'CONNECTED':'connected','UNPLUGGED':'unavailable','DISABLED':'disabled'}[s.mock_lan_state]
    return 'Wi-Fi: '+{'DISABLED':'disabled','NO_SIGNAL':'no signal','VERY_WEAK':'very weak','WEAK':'weak','GOOD':'good','OPTIMAL':'optimal'}[s.mock_wifi_signal]+(' / associated' if s.mock_wifi_associated else ' / not associated')

def insert_fixture_scan(scene):
    s=scene.seca_study;value=s.scan_fixture.strip()
    if s.disconnected:s.message='Connect power first'
    elif not s.scanner_attached:s.message='Attach mock scanner first'
    elif not s.mock_network:s.message='Enable mock network first'
    elif not value:s.message='Enter a fictional scan value'
    elif s.measurement_mode=='SELF' and (s.self_stage!='ID' or s.scan_fixture_target!='PATIENT'):s.message='Scanner available at self ID step'
    elif s.measurement_mode!='SELF' and s.view_mode!='MAIN':s.message='Open main screen first'
    elif s.scan_fixture_target=='PATIENT':s.synthetic_id=value;s.message='Fictional patient ID scanned'
    else:s.synthetic_user_id=value;s.message='Fictional user ID scanned'
    refresh(scene)

def transfer_failed(s, reason):
    s.transfer_state='FAILED';s.transfer_elapsed=0;s.transfer_error=reason
    s.message='Mock transfer failed: '+reason

def sampling_window_missing(scene):
    s=scene.seca_study
    return bool(s.dynamic_weight and s.loaded and not s.disconnected and s.state in {'WEIGHED','RESULT'} and scene.as_pointer() not in _sample_windows)

def require_live_sampling(scene):
    """Invalidate a stable synthetic result if its runtime history is absent."""
    if not sampling_window_missing(scene):return False
    input_changed(scene.seca_study,bpy.context)
    scene.seca_study.message='Sampling restarted; weight unstable';refresh(scene);return True

def start_transfer(scene):
    s=scene.seca_study
    if require_live_sampling(scene):return
    if s.transfer_state in {'PENDING','RETRY_WAIT'}:
        s.message='Mock transfer already in progress';return
    if not mock_link_ready(s):s.message='Mock link unavailable';return
    # Immutable serialized snapshot; no device, database or network is contacted.
    s.transfer_serial+=1
    payload={'id':f'study-{s.transfer_serial:06d}','synthetic_id':s.synthetic_id.strip(),
             'gross_kg':round(displayed_gross(s),6),'tare_kg':round(s.tare_kg,6),
             'net_kg':round(displayed_gross(s)-s.tare_kg,6),
             'height_cm':round(s.measured_height_cm,6) if s.state=='RESULT' else None,
             'result_type':'mother_child' if s.mother_stage=='DONE' else ('weight_only' if s.measurement_mode=='SELF' and s.self_weight_only_snapshot else 'weight_height'),
             'synthetic_user_id':s.synthetic_user_id.strip()}
    s.transfer_payload=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False)
    s.transfer_attempts=1;s.transfer_remaining=s.transfer_failures
    s.transfer_mode_snapshot=s.transfer_failure_mode;s.transfer_max_snapshot=s.transfer_max_attempts
    s.transfer_latency_snapshot=s.transfer_latency;s.transfer_elapsed=0;s.transfer_error=''
    s.transfer_state='PENDING';s.message='Mock transfer pending'

def advance_transfer(scene, seconds):
    # Local deterministic receiver. The serialized outbox and receipts remain in
    # the blend file; nothing is sent outside this scene.
    s=scene.seca_study
    if s.transfer_state not in {'PENDING','RETRY_WAIT'}:return False
    if not mock_link_ready(s):
        transfer_failed(s,'power or mock link unavailable');refresh(scene);return True
    remaining=max(0.0,min(float(seconds),60.0));changed=False
    while s.transfer_state in {'PENDING','RETRY_WAIT'}:
        duration=s.transfer_latency_snapshot if s.transfer_state=='PENDING' else .4
        needed=max(0.0,duration-s.transfer_elapsed)
        if remaining+1e-8<needed:
            s.transfer_elapsed+=remaining;break
        remaining=max(0,remaining-needed);s.transfer_elapsed=0;changed=True
        if s.transfer_state=='RETRY_WAIT':
            s.transfer_attempts+=1;s.transfer_state='PENDING';s.message='Mock transfer pending'
            continue
        payload=json.loads(s.transfer_payload);records=json.loads(s.receiver_records or '{}')
        failed=s.transfer_remaining>0 and s.transfer_mode_snapshot!='NONE'
        if failed:s.transfer_remaining-=1
        if not failed or s.transfer_mode_snapshot=='ACK_LOST':
            previous=records.get(payload['id'])
            if previous is not None and previous!=payload:
                transfer_failed(s,'receiver ID conflict');break
            records[payload['id']]=payload
            s.receiver_records=json.dumps(records,sort_keys=True,separators=(',',':'),allow_nan=False)
        if not failed:
            s.transfer_state='ACKNOWLEDGED';s.transfer_error='';s.message='Mock receipt acknowledged';break
        s.transfer_error='acknowledgement lost' if s.transfer_mode_snapshot=='ACK_LOST' else 'receiver unavailable'
        if s.transfer_attempts>=s.transfer_max_snapshot:
            transfer_failed(s,s.transfer_error);break
        s.transfer_state='RETRY_WAIT';s.message='Mock transfer retry pending'
    if changed:refresh(scene)
    return changed

def retry_transfer(scene):
    s=scene.seca_study
    if s.transfer_state!='FAILED' or not s.transfer_payload:
        s.message='No failed mock transfer';return
    if not mock_link_ready(s):
        s.message='Connect power and mock link first';return
    s.transfer_attempts=1;s.transfer_remaining=s.transfer_failures
    s.transfer_mode_snapshot=s.transfer_failure_mode;s.transfer_max_snapshot=s.transfer_max_attempts
    s.transfer_latency_snapshot=s.transfer_latency;s.transfer_elapsed=0;s.transfer_error=''
    s.transfer_state='PENDING';s.message='Mock retry pending'

def retention_changed(self,context):
    if not context or not context.scene or not hasattr(context.scene,'seca_study'):return
    scene=context.scene;s=scene.seca_study
    if s.state=='HELD' and retention_policy(s)=='UNLOAD':
        clear_held(s);s.state='READY';s.message='Scale ready'
    else:advance_retention(scene,0)
    advance_transfer(scene,0)
    if s.mock_network and not s.net_clear_armed and not s.net_data_expired and (s.synthetic_id.strip() or s.has_last):arm_network_clear(scene)
    elif not s.mock_network:s.net_clear_armed=False;s.net_clear_elapsed=0
    refresh(scene)

def finish_weight(scene):
    s=scene.seca_study;s.state='WEIGHED';s.view_mode='MAIN';s.measured_height_cm=0;s.setup_remeasure_required=False
    arm_network_clear(scene)
    if s.mother_stage=='WAIT_ADULT':
        s.view_mode='MOTHER';adult=displayed_gross(s)-s.tare_kg
        if adult<=0 or not set_tare_component(s,'adult_kg',adult):s.message='Invalid adult baseline';return
        s.mother_stage='ADULT_READY';s.message='Adult saved; continue';return
    if s.mother_stage=='WAIT_CHILD':
        s.view_mode='MOTHER'
        if displayed_gross(s)<=s.tare_kg+1e-5:s.message='Add child before measurement';return
        s.mother_stage='CHILD_READY';s.message='Child weight ready';return
    s.message='Weight stable (simulated)'
    s.last_kg=displayed_gross(s);s.last_net_kg=s.last_kg-s.tare_kg;s.last_height_cm=0;s.has_last=True
    if s.measurement_mode=='GUIDED':emit_voice(scene,'results','result')
    if s.measurement_mode=='SELF' and s.self_stage=='WEIGHT':s.view_mode='SELF'

def advance_sampling(scene,seconds):
    """Continue the synthetic filter after stability and invalidate lost stability.

    Filter constants and loss behavior are study assumptions, not measured
    load-cell, hold, timing or seca firmware behavior.
    """
    s=scene.seca_study
    active_self={'WEIGHT','HEIGHT_PREP','HEIGHT_RUNNING','HEIGHT_READ','RESULT','FINISHED'}
    if s.net_data_expired or not s.dynamic_weight or not s.loaded or s.disconnected or s.state not in {'UNSTABLE','WEIGHED','RESULT'} or (s.measurement_mode=='SELF' and s.self_stage not in active_self):return False
    dt_total=float(seconds)
    if not math.isfinite(dt_total) or dt_total<=0:return False
    tau,window,limit=FILTER_PROFILES[s.sensitivity]
    key=scene.as_pointer();samples=_sample_windows.get(key)
    if samples is None and s.state in {'WEIGHED','RESULT'}:
        # The sample window is intentionally not serialized.
        return require_live_sampling(scene)
    if samples is None:samples=_sample_windows.setdefault(key,[])
    remaining=min(dt_total,60.0)
    while remaining>1e-8 and s.loaded and s.state in {'UNSTABLE','WEIGHED','RESULT'}:
        dt=min(.05,remaining);remaining-=dt;s.sample_time+=dt
        target=s.gross_kg+s.motion_kg*math.sin(2*math.pi*1.7*s.sample_time)
        s.filtered_kg+=(target-s.filtered_kg)*(1-math.exp(-dt/tau))
        samples.append((s.sample_time,s.filtered_kg))
        while len(samples)>1 and s.sample_time-samples[0][0]>window+.05:samples.pop(0)
        if len(samples)>1 and s.sample_time-samples[0][0]>=window:
            span=max(x[1] for x in samples)-min(x[1] for x in samples)
            if s.state=='UNSTABLE' and span<=limit:
                finish_weight(scene)
            elif s.state in {'WEIGHED','RESULT'} and span>limit:
                # Reuse the existing input-change invalidation path, including
                # current height/mother-child state and immutable mock outbox.
                input_changed(s,bpy.context);s.message='Study motion; weight unstable';break
    refresh(scene);return True

def quantize(v,step):
    # Proposed half-up rule; unit-specific device behavior remains unverified.
    return math.floor(v/step+0.5)*step

def weight_display(kg,units):
    return f'{quantize(kg,0.05):.2f}' if units=='KG' else f'{quantize(kg/0.45359237,0.1):.1f}'

def height_display(cm,units):
    if units=='CM':return f'{quantize(cm,0.1):.1f}'
    eighths=int(math.floor(cm/2.54*8+0.5));feet,eighths=divmod(eighths,96);inches,num=divmod(eighths,8)
    if not num:return f"{feet}' {inches}\""
    div=math.gcd(num,8);return f"{feet}' {inches} {num//div}/{8//div}\""

def format_pre_tare(kg,units):
    # Study formatting, independent of the scale reading increment.
    return f'{(kg if units=="KG" else kg/.45359237):.2f}'

def body_size(weight,height,mode):
    if weight<=0 or height<=0 or mode=='OFF':return ''
    if mode=='BMI':return f'{weight/(height/100)**2:.1f} BMI'
    if mode=='MOSTELLER':value=math.sqrt(height*weight/3600)
    elif mode=='DUBOIS':value=.007184*weight**.425*height**.725
    else:value=.024265*weight**.5378*height**.3964
    return f'{value:.2f} BSA'

# The on-device-like status strip is small. The detailed view is explicitly a
# study aid, not a claim about seca firmware. Measure with the scene's real font.
_message_layout_cache={}
def layout_message(value):
    probe=bpy.data.objects.get('SIM • message')
    if not probe:return value,[[value]]
    key=(value,probe.data.size,probe.data.font.name if probe.data.font else '')
    if key in _message_layout_cache:return _message_layout_cache[key]
    previous=probe.data.body
    def width(txt):
        probe.data.body=txt;bpy.context.view_layer.update()
        ev=probe.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return max(v[0] for v in ev.bound_box)-min(v[0] for v in ev.bound_box) if txt else 0.0
    def prefix(txt,limit,suffix=''):
        lo,hi=0,len(txt)
        while lo<hi:
            mid=(lo+hi+1)//2
            if width(txt[:mid]+suffix)<=limit:lo=mid
            else:hi=mid-1
        return lo
    flat=' '.join(value.splitlines())
    preview=flat if width(flat)<=.078 else flat[:prefix(flat,.078,'...')].rstrip()+'...'
    lines=[]
    for paragraph in value.split('\n'):
        if not paragraph:lines.append('');continue
        while paragraph:
            n=prefix(paragraph,.078)
            if n==0:n=1
            if n<len(paragraph):
                last=paragraph.rfind(' ',0,n+1)
                if last>0:n=last+1
            lines.append(paragraph[:n].rstrip());paragraph=paragraph[n:]
    pages=[lines[i:i+10] for i in range(0,len(lines),10)] or [['']]
    probe.data.body=previous
    if len(_message_layout_cache)>=128:_message_layout_cache.clear()
    _message_layout_cache[key]=(preview,pages)
    return preview,pages

# Manual describes five brightness stages and factory stage 4, not luminance.
BRIGHTNESS_LEVELS=(.45,.90,1.35,1.80,2.25)
def apply_display_brightness(scene):
    group=bpy.data.node_groups.get('Display • relative luminance (study)')
    node=group.nodes.get('Relative screen brightness (estimate)') if group else None
    if node:node.outputs[0].default_value=BRIGHTNESS_LEVELS[scene.seca_study.display_brightness-1]
def display_brightness_changed(self,context):
    if not context or not context.scene or not hasattr(context.scene,'seca_study'):return
    apply_display_brightness(context.scene);refresh(context.scene)

def standby_setting_changed(self,context):
    if not context or not context.scene or not hasattr(context.scene,'seca_study'):return
    s=context.scene.seca_study;s.idle_elapsed=0
    if s.standby_seconds<=0:s.display_standby=False
    refresh(context.scene)

def wake_display(scene):
    s=scene.seca_study
    if s.disconnected:return False
    changed=s.display_standby;s.display_standby=False;s.idle_elapsed=0;refresh(scene);return changed

def advance_standby(scene,seconds):
    """Advance an illustrative idle timer; real timeout activity rules are unknown."""
    s=scene.seca_study
    if s.disconnected or s.display_standby or s.standby_seconds<=0:return False
    # Study policy: pause during active calibration, timed height or a fault.
    if s.fault_active!='NONE' or s.height_measuring or s.cal_stage!='IDLE':return False
    dt=float(seconds)
    if not math.isfinite(dt) or dt<=0:return False
    s.idle_elapsed=min(s.standby_seconds,s.idle_elapsed+dt)
    if s.idle_elapsed+1e-5>=s.standby_seconds:
        s.display_standby=True;refresh(scene);return True
    return False

# Reference-informed partial menu. Rows and selection states are generated from
# the same data that dispatches actions; no network or service settings exist.
def demo_name(mode):
    return {'GIVEN_FAMILY':'Demo Patient','GIVEN_COMMA_FAMILY':'Demo, Patient','FAMILY_GIVEN':'Patient Demo','FAMILY_COMMA_GIVEN':'Patient, Demo'}[mode]

def demo_date(mode):
    return {'YMD_DOT':'1980.06.05','DMY_DOT':'05.06.1980','MDY_DOT':'06.05.1980','YMD_SLASH':'1980/06/05','DMY_SLASH':'05/06/1980','MDY_SLASH':'06/05/1980'}[mode]

def menu_spec(s):
    can_clear = not s.mock_network and s.autohold
    table={
      'ROOT':('Settings',[('Display','DISPLAY',False,True),('Weight','WEIGHT',False,True),('Network','NETWORK',False,True),('RS-232','UNAVAILABLE',False,False),('Audio','AUDIO',False,True),('Battery','UNAVAILABLE',False,False)]),
      'DISPLAY':('Display',[('Language','UNAVAILABLE',False,False),('Units','UNITS',False,True),('Clear Values','CLEAR_VALUES',False,can_clear),('Brightness','BRIGHTNESS',False,True),('Standby','STANDBY',False,True),('Name Format','NAME_FORMAT',False,True),('Date Format','DATE_FORMAT',False,True)]),
      'DISPLAY_MORE':('Display',[('BMI/BSA','BODY_OPTIONS',False,True)]),
      'NAME_FORMAT':('Name Format',[(label,'NAME_'+value,s.name_format==value,True) for label,value in (('Demo Patient','GIVEN_FAMILY'),('Demo, Patient','GIVEN_COMMA_FAMILY'),('Patient Demo','FAMILY_GIVEN'),('Patient, Demo','FAMILY_COMMA_GIVEN'))]),
      'DATE_FORMAT':('Date Format',[(label,'DATE_'+value,s.date_format==value,True) for label,value in (('YYYY.MM.DD','YMD_DOT'),('DD.MM.YYYY','DMY_DOT'),('MM.DD.YYYY','MDY_DOT'),('YYYY/MM/DD','YMD_SLASH'),('DD/MM/YYYY','DMY_SLASH'),('MM/DD/YYYY *','MDY_SLASH'))]),
      'BODY_OPTIONS':('BMI/BSA',[('None','BODY_OFF',s.indicator=='OFF',True),('BMI','BODY_BMI',s.indicator=='BMI',True),('BSA (DuBois)','BODY_DUBOIS',s.indicator=='DUBOIS',True),('BSA (Haycock)','BODY_HAYCOCK',s.indicator=='HAYCOCK',True),('BSA (Mosteller)','BODY_MOSTELLER',s.indicator=='MOSTELLER',True)]),
      'NETWORK':('Network',[('Identification','NET_IDENTIFICATION',False,True)]),
      'NET_IDENTIFICATION':('Identification',[('Clear Data','NET_CLEAR_DATA',False,True)]),
      'NET_CLEAR_DATA':('Clear Data',[]),
      'WEIGHT':('Weight',[('Autohold','AUTOHOLD',False,True),('Pre-Tare Presets','UNAVAILABLE',False,False),('Sensitivity','SENSITIVITY',False,True),('Tare-By-Scanning','UNAVAILABLE',False,False),('Pre-tare','PRETARE',False,True)]),
      'PRETARE':('Pre-tare',[]),
      'PRETARE_EDIT':('Pre-tare',[]),
      'UNITS':('Units',[('Metric','UNIT_METRIC',s.weight_units=='KG' and s.height_units=='CM',True),('Imperial','UNIT_IMPERIAL',s.weight_units=='LB' and s.height_units=='IMPERIAL',True)]),
      'AUTOHOLD':('Autohold',[('On','HOLD_ON',effective_hold(s),True),('Off','HOLD_OFF',not effective_hold(s),not s.mock_network)]),
      'SENSITIVITY':('Sensitivity',[(v.title(),'SENS_'+v,s.sensitivity==v,True) for v in ('LOW','MEDIUM','HIGH')]),
      'BRIGHTNESS':('Brightness',[]),
      'STANDBY':('Standby',[('Off','STANDBY_OFF',s.standby_seconds==0,True),('1 min','STANDBY_1MIN',abs(s.standby_seconds-60)<.001,True),('3 min','STANDBY_3MIN',abs(s.standby_seconds-180)<.001,True),('5 min','STANDBY_5MIN',abs(s.standby_seconds-300)<.001,True)]),
      'AUDIO':('Audio',[('Beeps','BEEPS_TOGGLE',s.beeps_enabled,True),('Guidance','VOICE_GUIDANCE_TOGGLE',s.voice_guidance_enabled,True),('Results','VOICE_RESULTS_TOGGLE',s.voice_results_enabled,True),('Language','AUDIO_LANGUAGE',False,True),('Volume','AUDIO_VOLUME',False,True)]),
      'AUDIO_LANGUAGE':('Language',[('English','VOICE_LANG_EN',s.voice_language=='EN',True)]),
      'AUDIO_BEEPS':('Beeps',[('On','BEEPS_ON',s.beeps_enabled,True),('Off','BEEPS_OFF',not s.beeps_enabled,True)]),
      'AUDIO_VOLUME':('Volume',[]),
      'CLEAR_VALUES':('Clear Values',[('On Reload','CLEAR_RELOAD',s.clear_policy=='RELOAD',can_clear),('On Unload','CLEAR_UNLOAD',s.clear_policy=='UNLOAD',can_clear),('Set Timeout','TIMEOUT',s.clear_policy=='TIMEOUT',can_clear)]),
      'TIMEOUT':('Set Timeout',[('− 5 seconds','TIMEOUT_MINUS',False,can_clear),(f'{s.menu_timeout_draft} seconds','INFO',False,False),('+ 5 seconds','TIMEOUT_PLUS',False,can_clear),('Save','TIMEOUT_SAVE',False,can_clear)])}
    return table[s.menu_page]

def menu_select(scene,index):
    s=scene.seca_study
    if s.disconnected or s.view_mode!='SETTINGS':return
    _,items=menu_spec(s)
    if not 0<=index<len(items) or not items[index][3]:return
    action=items[index][1]
    if action=='BRIGHTNESS':s.brightness_draft=s.display_brightness;s.menu_page='BRIGHTNESS'
    elif action=='AUDIO_VOLUME':s.volume_draft=s.audio_volume;s.menu_page='AUDIO_VOLUME'
    elif action=='NET_CLEAR_DATA':s.net_clear_draft=str(s.net_clear_seconds);s.net_clear_replace=True;s.net_clear_overflow=False;s.net_clear_status='';s.menu_page='NET_CLEAR_DATA'
    elif action in {'DISPLAY','NAME_FORMAT','DATE_FORMAT','BODY_OPTIONS','WEIGHT','PRETARE','UNITS','AUTOHOLD','SENSITIVITY','CLEAR_VALUES','STANDBY','AUDIO','AUDIO_BEEPS','AUDIO_LANGUAGE','NETWORK','NET_IDENTIFICATION'}:s.menu_page=action
    elif action=='TIMEOUT':s.menu_timeout_draft=max(1,min(3600,round(s.clear_timeout)));s.menu_page='TIMEOUT'
    elif action.startswith('NAME_') and action[5:] in {'GIVEN_FAMILY','GIVEN_COMMA_FAMILY','FAMILY_GIVEN','FAMILY_COMMA_GIVEN'}:s.name_format=action[5:]
    elif action.startswith('DATE_') and action[5:] in {'YMD_DOT','DMY_DOT','MDY_DOT','YMD_SLASH','DMY_SLASH','MDY_SLASH'}:s.date_format=action[5:]
    elif action.startswith('BODY_') and action[5:] in {'OFF','BMI','DUBOIS','HAYCOCK','MOSTELLER'}:s.indicator=action[5:]
    elif action=='UNIT_METRIC':s.weight_units='KG';s.height_units='CM'
    elif action=='UNIT_IMPERIAL':s.weight_units='LB';s.height_units='IMPERIAL'
    elif action=='HOLD_ON':s.autohold=True
    elif action=='HOLD_OFF':s.autohold=False
    elif action.startswith('SENS_'):
        s.sensitivity=action[5:]
        # The sampling callback invalidates a loaded current value; keep the
        # user in Settings so they can see the new selection.
        s.view_mode='SETTINGS'
    elif action=='STANDBY_OFF':s.standby_seconds=0
    elif action=='STANDBY_1MIN':s.standby_seconds=60
    elif action=='STANDBY_3MIN':s.standby_seconds=180
    elif action=='STANDBY_5MIN':s.standby_seconds=300
    elif action=='VOICE_GUIDANCE_TOGGLE':s.voice_guidance_enabled=not s.voice_guidance_enabled
    elif action=='VOICE_RESULTS_TOGGLE':s.voice_results_enabled=not s.voice_results_enabled
    elif action=='VOICE_LANG_EN':s.voice_language='EN'
    elif action=='BEEPS_TOGGLE':s.beeps_enabled=not s.beeps_enabled
    elif action=='BEEPS_ON':s.beeps_enabled=True
    elif action=='BEEPS_OFF':s.beeps_enabled=False
    elif action.startswith('VOLUME_'):s.audio_volume=int(action.split('_')[1])
    elif action.startswith('CLEAR_'):s.clear_policy=action[6:]
    elif action=='TIMEOUT_MINUS':s.menu_timeout_draft=max(1,s.menu_timeout_draft-5)
    elif action=='TIMEOUT_PLUS':s.menu_timeout_draft=min(3600,s.menu_timeout_draft+5)
    elif action=='TIMEOUT_SAVE':s.clear_timeout=s.menu_timeout_draft;s.clear_policy='TIMEOUT';s.menu_page='CLEAR_VALUES'

def menu_back(s):
    s.menu_page={'ROOT':'ROOT','DISPLAY':'ROOT','DISPLAY_MORE':'ROOT','NAME_FORMAT':'DISPLAY','DATE_FORMAT':'DISPLAY','BODY_OPTIONS':'DISPLAY_MORE','WEIGHT':'ROOT','PRETARE':'WEIGHT','PRETARE_EDIT':'PRETARE','UNITS':'DISPLAY','AUTOHOLD':'WEIGHT','SENSITIVITY':'WEIGHT','CLEAR_VALUES':'DISPLAY','TIMEOUT':'CLEAR_VALUES','STANDBY':'DISPLAY','BRIGHTNESS':'DISPLAY','AUDIO':'ROOT','AUDIO_BEEPS':'AUDIO','AUDIO_VOLUME':'AUDIO','AUDIO_LANGUAGE':'AUDIO','NETWORK':'ROOT','NET_IDENTIFICATION':'NETWORK','NET_CLEAR_DATA':'NET_IDENTIFICATION'}[s.menu_page]

def body_size_available(s):
    if s.disconnected or s.display_standby or s.view_mode!='MAIN' or s.indicator=='OFF' or s.setup_remeasure_required:return False
    if s.state=='HELD':return s.held_height_cm>0 and s.held_net_kg>0
    return s.state=='RESULT' and s.loaded and s.measured_height_cm>0 and displayed_gross(s)-s.tare_kg>0

def main_measurement_ready(s):
    # Reference-informed availability for this study; hardware/firmware state
    # rules and any thresholds remain unverified.
    return (not s.disconnected and not s.display_standby and s.view_mode=='MAIN'
            and s.measurement_mode=='GUIDED' and s.loaded
            and s.state in {'WEIGHED','RESULT'} and s.mother_stage=='NONE'
            and not s.setup_remeasure_required)

def refresh(scene):
    s=scene.seca_study
    if s.fault_active!='NONE' and not s.disconnected:s.view_mode='FAULT';s.state='FAULT'
    touch=bpy.data.objects.get('TOUCH • pressed feedback')
    if touch and (s.disconnected or s.display_standby or (not touch.hide_get() and touch.get('touch_view')!=s.view_mode)):
        touch.hide_set(True);touch.hide_render=True
    footprint=bpy.data.materials.get('Illuminated footprint')
    if footprint and footprint.use_nodes:
        footprint.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value=0 if s.disconnected else 2.0
    for name,active in [('Indicator • rear power',not s.disconnected),('Indicator • rear network',not s.disconnected and s.mock_network),('Ultrasonic power indicator',not s.disconnected and not s.height_measuring)]:
        o=bpy.data.objects.get(name)
        if o and o.data.materials:
            m=bpy.data.materials.get('Indicator • powered' if active else 'Indicator • unlit')
            if m:o.data.materials[0]=m
    rear=bpy.data.objects.get('Indicator • rear network')
    if rear and rear.data.materials:
        enabled=(s.mock_network and not s.disconnected and (s.mock_transport=='LAN' and s.mock_lan_state!='DISABLED' or s.mock_transport=='WIFI' and s.mock_wifi_signal!='DISABLED'))
        m=bpy.data.materials.get('Indicator • powered' if enabled and mock_link_ready(s) else ('Indicator • interrupted' if enabled else 'Indicator • unlit'))
        if m:rear.data.materials[0]=m
    def text(name,value):
        o=bpy.data.objects.get(name)
        if o: o.data.body=value
    def show(o,visible):
        o.hide_set(not visible);o.hide_render=not visible
    for o in bpy.data.objects:
        if o.name.startswith('SIM • '):show(o,not s.disconnected and not s.display_standby and s.view_mode=='MAIN')
        elif o.name.startswith('REVIEW • '):show(o,not s.disconnected and s.view_mode=='HEIGHT')
        elif o.name.startswith('MANUALH • '):show(o,not s.disconnected and s.view_mode=='MANUAL_HEIGHT')
        elif o.name.startswith('RECALL • '):show(o,not s.disconnected and s.view_mode=='RECALL')
        elif o.name.startswith('TAREMENU • '):show(o,not s.disconnected and s.view_mode=='TARE_MENU')
        elif o.name.startswith('TAREEDIT • '):show(o,not s.disconnected and s.view_mode=='TARE_EDIT')
        elif o.name.startswith('MOTHER • '):show(o,not s.disconnected and not s.display_standby and s.view_mode=='MOTHER')
        elif o.name.startswith('MSG • '):show(o,not s.disconnected and s.view_mode=='MESSAGE')
        elif o.name.startswith('MEASURE • '):show(o,not s.disconnected and s.view_mode=='MEASURING')
        elif o.name.startswith('CAL • '):show(o,not s.disconnected and s.view_mode=='CALIBRATION')
        elif o.name.startswith('OVERVIEW • '):show(o,not s.disconnected and s.view_mode=='OVERVIEW')
        elif o.name.startswith('SECMENU • '):show(o,not s.disconnected and s.view_mode=='SETTINGS')
        elif o.name.startswith('BRIGHT • '):
            show(o,not s.disconnected and not s.display_standby and s.view_mode=='SETTINGS' and s.menu_page in {'BRIGHTNESS','AUDIO_VOLUME'} and (s.menu_page=='BRIGHTNESS' or not o.name.startswith('BRIGHT • sun')))
        elif o.name.startswith('VOLUME • '):show(o,not s.disconnected and not s.display_standby and s.view_mode=='SETTINGS' and s.menu_page=='AUDIO_VOLUME')
        elif o.name.startswith('PAGING • '):show(o,not s.disconnected and not s.display_standby and s.view_mode=='SETTINGS' and s.menu_page in {'DISPLAY','DISPLAY_MORE'})
        elif o.name.startswith('PRETARE • '):show(o,not s.disconnected and not s.display_standby and s.view_mode=='SETTINGS' and s.menu_page=='PRETARE')
        elif o.name.startswith('PRETAREKEY • '):show(o,not s.disconnected and not s.display_standby and s.view_mode=='SETTINGS' and s.menu_page=='PRETARE_EDIT')
        elif o.name.startswith('CLEARDATA • '):show(o,not s.disconnected and not s.display_standby and s.view_mode=='SETTINGS' and s.menu_page=='NET_CLEAR_DATA')
        elif o.name.startswith('AUDIOSWITCH • '):show(o,not s.disconnected and not s.display_standby and s.view_mode=='SETTINGS' and s.menu_page=='AUDIO' and ((' • on ' in o.name)==s.beeps_enabled))
        elif o.name.startswith(('VOICE GUIDANCE • ','VOICE RESULTS • ')):
            active=s.voice_guidance_enabled if o.name.startswith('VOICE GUIDANCE') else s.voice_results_enabled
            show(o,not s.disconnected and not s.display_standby and s.view_mode=='SETTINGS' and s.menu_page=='AUDIO' and ((' • on ' in o.name)==active))
        elif o.name.startswith('SELF • '):show(o,not s.disconnected and s.view_mode=='SELF')
        elif o.name.startswith('SELFART • '):show(o,not s.disconnected and s.view_mode=='SELF' and s.self_stage in o.get('self_stages','').split())
        elif o.name.startswith('FAULT • '):show(o,not s.disconnected and s.view_mode=='FAULT')
    # The header only represents the local study.  A dot means that an ID
    # string was entered; it is not real identity or network verification.
    if s.display_standby:
        for o in bpy.data.objects:
            if o.name.startswith(('REVIEW • ','MANUALH • ','RECALL • ','TAREMENU • ','TAREEDIT • ','MOTHER • ','MSG • ','MEASURE • ','CAL • ','OVERVIEW • ','SECMENU • ','SELF • ','SELFART • ','FAULT • ')):show(o,False)
    header_active=not s.disconnected and not s.display_standby and s.view_mode=='MAIN' and s.mock_network
    for o in bpy.data.objects:
        if o.name.startswith('SIM • identity '):show(o,header_active)
        elif o.name.startswith('SIM • connection wifi '):show(o,header_active and s.mock_transport=='WIFI')
        elif o.name.startswith('SIM • connection '):
            show(o,header_active and s.mock_transport=='LAN')
            if o.data and o.data.materials:o.data.materials[0]=bpy.data.materials['UI • ink' if mock_link_ready(s) else 'UI • secondary']
    levels={'DISABLED':0,'NO_SIGNAL':0,'VERY_WEAK':1,'WEAK':2,'GOOD':3,'OPTIMAL':4}
    for i in range(4):
        icon=bpy.data.objects.get('SIM • connection wifi '+str(i+1))
        if icon and icon.data.materials:icon.data.materials[0]=bpy.data.materials['UI • ink' if i<levels[s.mock_wifi_signal] else 'UI • secondary']
    for kind,present in [('patient',bool(s.synthetic_id.strip())),('user',bool(s.synthetic_user_id.strip()))]:
        dot=bpy.data.objects.get('SIM • identity '+kind+' dot')
        if dot:dot.data.materials[0]=bpy.data.materials['UI • overview green ink' if present else 'UI • divider']
    screen=bpy.data.objects.get('ID display active image')
    if screen:
        material=bpy.data.materials.get('Display • power off' if s.disconnected or s.display_standby else 'Display backlight')
        if material:screen.data.materials[0]=material
    tile=bpy.data.objects.get('SIM • confirm tile');send=bpy.data.objects.get('SIM • button send')
    if tile and send:
        tile.data.materials[0]=bpy.data.materials['UI • confirm' if s.mock_network else 'UI • white']
        send.data.materials[0]=bpy.data.materials['UI • white' if s.mock_network else 'UI • ink']
    if s.disconnected:
        for name in ('weight','height','bmi','tare','state','network'):text('SIM • '+name,'')
        text('SIM • message','Power disconnected')
        return
    if s.display_standby:return
    if s.view_mode=='MOTHER':
        intro=s.mother_stage=='INTRO';ready=s.mother_stage in {'ADULT_READY','CHILD_READY'} and s.state=='WEIGHED'
        for name in ('MOTHER • value panel','MOTHER • weight','MOTHER • unit'):
            ob=bpy.data.objects.get(name)
            if ob:show(ob,not intro)
        ob=bpy.data.objects.get('MOTHER • intro illustration')
        if ob:show(ob,intro)
        for name in ('MOTHER • tare panel','MOTHER • tare value'):
            ob=bpy.data.objects.get(name)
            if ob:show(ob,not intro and s.adult_kg>0)
        for name in ('MOTHER • repeat region','MOTHER • repeat icon','MOTHER • repeat outline','MOTHER • stable lock'):
            ob=bpy.data.objects.get(name)
            if ob:show(ob,ready)
        for name in ('MOTHER • action region','MOTHER • action outline'):
            ob=bpy.data.objects.get(name)
            if ob:show(ob,intro or ready)
        ob=bpy.data.objects.get('MOTHER • action region')
        if ob:ob.location.x=0 if intro else .010;ob.scale.x=(.090/.068) if intro else 1
        for name,visible in [('MOTHER • action label',intro),('MOTHER • action icon',ready)]:
            ob=bpy.data.objects.get(name)
            if ob:show(ob,visible)
        value=displayed_gross(s)-s.tare_kg if s.loaded else 0
        text('MOTHER • weight','OVER' if s.state=='OVERLOAD' else weight_display(value,s.weight_units));text('MOTHER • unit','kg' if s.weight_units=='KG' else 'lb')
        text('MOTHER • tare value','T   -'+weight_display(s.tare_kg,s.weight_units)+' '+('kg' if s.weight_units=='KG' else 'lb'))
        content={'INTRO':('Ask accompanying adult','to step onto the scale','without the child.'),'WAIT_ADULT':('Waiting for stable','accompanying adult','weight.'),'ADULT_READY':('Accompanying adult','weight captured.','Continue.'),'WAIT_CHILD':('Adult remains on scale','and takes the child.','Wait for a stable value.'),'CHILD_READY':('Child weight','ready for review.','')}.get(s.mother_stage,('','',''))
        for i,line in enumerate(content,1):text('MOTHER • line '+str(i),line)
        text('MOTHER • action label','Start')
    if s.view_mode=='CALIBRATION':calibration_screen(scene)
    if s.view_mode=='SELF':self_screen(scene)
    if s.view_mode=='FAULT':fault_screen(scene)
    if s.view_mode=='SETTINGS':
        title,items=menu_spec(s);text('SECMENU • title',title)
        for i in range(7):
            row=bpy.data.objects.get(f'SECMENU • row {i+1}');label=bpy.data.objects.get(f'SECMENU • label {i+1}');mark=bpy.data.objects.get(f'SECMENU • mark {i+1}')
            visible=s.menu_page not in {'BRIGHTNESS','AUDIO_VOLUME','PRETARE','PRETARE_EDIT','NET_CLEAR_DATA'} and i<len(items)
            for o in (row,label,mark):
                if o:show(o,visible)
            if visible:
                name,command,selected,enabled=items[i]
                if label:label.data.body=name;label.data.materials[0]=bpy.data.materials['UI • ink' if enabled else 'UI • secondary']
                if mark:
                    mark.data.body='' if command in {'BEEPS_TOGGLE','VOICE_GUIDANCE_TOGGLE','VOICE_RESULTS_TOGGLE'} else '›' if command in {'DISPLAY','NAME_FORMAT','DATE_FORMAT','WEIGHT','UNITS','AUTOHOLD','SENSITIVITY','CLEAR_VALUES','TIMEOUT','STANDBY','BRIGHTNESS','BODY_OPTIONS','PRETARE','AUDIO','AUDIO_BEEPS','AUDIO_VOLUME','AUDIO_LANGUAGE','NETWORK','NET_IDENTIFICATION','NET_CLEAR_DATA','UNAVAILABLE'} else (('●' if selected else '○') if command.startswith(('UNIT_','HOLD_','SENS_','CLEAR_','STANDBY_','BEEPS_','VOLUME_','BODY_','VOICE_LANG_','NAME_','DATE_')) else '')
                    mark.data.materials[0]=bpy.data.materials['UI • overview green ink' if command=='BEEPS_TOGGLE' and selected else ('UI • ink' if enabled else 'UI • secondary')]
    if s.view_mode=='SETTINGS' and s.menu_page in {'DISPLAY','DISPLAY_MORE'}:
        for name,active in [('PAGING • previous icon',s.menu_page=='DISPLAY_MORE'),('PAGING • next icon',s.menu_page=='DISPLAY'),('PAGING • dot 1',s.menu_page=='DISPLAY'),('PAGING • dot 2',s.menu_page=='DISPLAY_MORE')]:
            ob=bpy.data.objects.get(name)
            if ob:ob.data.materials[0]=bpy.data.materials['UI • ink' if active else 'UI • secondary']
    if s.view_mode=='SETTINGS' and s.menu_page in {'BRIGHTNESS','AUDIO_VOLUME'}:
        level=s.brightness_draft if s.menu_page=='BRIGHTNESS' else s.volume_draft
        for i in range(1,6):
            dot=bpy.data.objects.get(f'BRIGHT • level dot {i}')
            if dot:dot.data.materials[0]=bpy.data.materials['UI • ink' if i<=level else 'UI • secondary']
    if s.view_mode=='SETTINGS' and s.menu_page in {'PRETARE','PRETARE_EDIT'}:
        text('PRETARE • value',format_pre_tare(s.pre_tare_kg,s.weight_units));text('PRETARE • unit','kg' if s.weight_units=='KG' else 'lb')
        text('PRETAREKEY • value',s.pre_tare_draft);text('PRETAREKEY • unit','kg' if s.pre_tare_edit_units=='KG' else 'lb');text('PRETAREKEY • status',s.pre_tare_edit_status)
    if s.view_mode=='SETTINGS' and s.menu_page=='NET_CLEAR_DATA':
        text('CLEARDATA • value',s.net_clear_draft);text('CLEARDATA • unit','sec');text('CLEARDATA • status',s.net_clear_status)
    text('MEASURE • unit','cm' if s.height_units=='CM' else 'ft/in')
    text('MANUALH • value',s.manual_height_draft)
    text('MANUALH • unit','cm' if s.manual_height_units=='CM' else 'in (study)')
    text('MANUALH • status',s.manual_height_status)
    text('REVIEW • value',height_display(s.preview_height_cm,s.height_units))
    text('REVIEW • unit','cm' if s.height_units=='CM' else 'ft/in')
    text('REVIEW • step','Steps:      0.5 cm' if s.height_units=='CM' else 'Steps:      1/8 in')
    text('RECALL • weight',weight_display(s.last_net_kg,s.weight_units))
    text('RECALL • unit','kg' if s.weight_units=='KG' else 'lb')
    text('RECALL • height',height_display(s.last_height_cm,s.height_units) if s.last_height_cm else '---.-')
    text('RECALL • height unit','cm' if s.height_units=='CM' else 'ft/in')
    text('RECALL • bmi',body_size(quantize(s.last_net_kg,.05),s.last_height_cm,s.indicator))
    # The overview uses fictional identifiers only; green means text was entered
    # in this local study, not that an identity was verified by a real system.
    if s.view_mode=='OVERVIEW':
        def label_id(value):
            value=value.strip()
            return value if len(value)<=16 else value[:15]+'…'
        fixture=bool(s.show_demo_identity and s.synthetic_id.strip())
        text('OVERVIEW • patient note',('Example: '+demo_name(s.name_format)) if fixture else 'Fictional patient')
        text('OVERVIEW • fictional date','DOB '+demo_date(s.date_format) if fixture else '')
        date=bpy.data.objects.get('OVERVIEW • fictional date')
        if date:show(date,fixture and not s.disconnected and not s.display_standby)
        text('OVERVIEW • patient value',label_id(s.synthetic_id) or 'Not scanned')
        text('OVERVIEW • user value',label_id(s.synthetic_user_id) or 'Not scanned')
        text('OVERVIEW • status','' if s.message=='Review synthetic IDs' else s.message[:28])
        net=displayed_gross(s)-s.tare_kg
        weight=weight_display(net,s.weight_units)
        text('OVERVIEW • weight',weight)
        weight_obj=bpy.data.objects.get('OVERVIEW • weight')
        if weight_obj:weight_obj.data.size=.020 if len(weight)>5 else .024
        height_obj=bpy.data.objects.get('OVERVIEW • height')
        if height_obj:height_obj.data.size=.0065 if s.height_units=='IMPERIAL' else .010
        text('OVERVIEW • weight unit','kg' if s.weight_units=='KG' else 'lb')
        height=s.measured_height_cm if s.state=='RESULT' else None
        text('OVERVIEW • height',height_display(height,s.height_units) if height else '---.-')
        text('OVERVIEW • height unit','cm' if s.height_units=='CM' else 'ft/in')
        for name,present in [('patient',bool(s.synthetic_id.strip())),('user',bool(s.synthetic_user_id.strip()))]:
            dot=bpy.data.objects.get('OVERVIEW • '+name+' indicator')
            if dot:dot.data.materials[0]=bpy.data.materials['UI • overview green ink' if present else 'UI • divider']
            text('OVERVIEW • '+name+' check','✓' if present else '')
        send=bpy.data.objects.get('OVERVIEW • send region')
        if send:send.data.materials[0]=bpy.data.materials['UI • overview send' if s.mock_network else 'UI • white']
    text('TAREEDIT • value',weight_display(s.clothing_draft_kg,s.weight_units))
    text('TAREEDIT • unit','kg' if s.weight_units=='KG' else 'lb')
    text('TAREEDIT • step','Steps: 0.5 kg' if s.weight_units=='KG' else 'Steps: 1 lb')
    if s.state=='OVERLOAD':
        text('SIM • weight','OVER');text('SIM • height','---');text('SIM • bmi','')
    else:
        net=s.held_net_kg if s.state=='HELD' else (displayed_gross(s)-s.tare_kg) if s.loaded else -s.tare_kg
        # Simulator rounding rule, not an experimentally verified device rule.
        value=quantize(net,0.05)
        text('SIM • weight','---' if s.loaded and s.setup_remeasure_required else weight_display(net,s.weight_units))
        h=s.held_height_cm if s.state=='HELD' and s.held_height_cm else s.measured_height_cm if s.state=='RESULT' else None
        text('SIM • height',height_display(h,s.height_units) if h is not None else '---.-')
        text('SIM • bmi',body_size(value,h,s.indicator) if h else '')
    text('SIM • kg','kg' if s.weight_units=='KG' else 'lb')
    text('SIM • cm','cm' if s.height_units=='CM' else 'ft/in')
    tare=s.held_tare_kg if s.state=='HELD' else s.tare_kg
    text('SIM • tare',f'-{weight_display(tare,s.weight_units)} {"kg" if s.weight_units=="KG" else "lb"}' if tare else '')
    tare_visible=s.view_mode=='MAIN' and not s.disconnected and not s.display_standby and tare>0
    status=bpy.data.objects.get('SIM • state')
    if status:show(status,s.view_mode=='MAIN' and not s.disconnected and not s.display_standby and not tare_visible)
    for name in ('SIM • tare','SIM • tare bar background','SIM • tare bar icon','SIM • tare clear region','SIM • tare clear icon','SIM • net label'):
        ob=bpy.data.objects.get(name)
        if ob:show(ob,tare_visible)

    for name in ('SIM • height','REVIEW • value','RECALL • height'):
        o=bpy.data.objects.get(name)
        if o:o.data.size=(.009 if name=='SIM • height' else .012) if s.height_units=='IMPERIAL' else (.014 if name=='SIM • height' else .022 if name=='REVIEW • value' else .013)
    preview,pages=layout_message(s.message)
    text('SIM • message',preview)
    if s.view_mode=='MESSAGE':
        s.message_page=min(s.message_page,len(pages)-1)
        for i in range(10):text('MSG • line %02d'%i,pages[s.message_page][i] if i<len(pages[s.message_page]) else '')
        text('MSG • page',f'{s.message_page+1} / {len(pages)}')
        for name,visible in [('MSG • previous',s.message_page>0),('MSG • next',s.message_page+1<len(pages))]:
            o=bpy.data.objects.get(name)
            if o:show(o,visible)
    text('SIM • network','')  # The model's connection icon replaces study text.
    text('SIM • state','OVERLOAD' if s.state=='OVERLOAD' else 'UNSTABLE' if s.state=='UNSTABLE' else 'HOLD' if s.state=='HELD' else 'STABLE' if s.loaded else 'READY')
    # Main-screen measurement controls share their visible geometry and hit
    # regions. A completed current height exposes a repeat control; a stable
    # weight without height exposes the start button.
    ready_for_measurement=main_measurement_ready(s)
    has_height=s.state=='RESULT' and s.measured_height_cm>0
    show_previous=s.state=='HELD' and s.held_height_cm>0
    for n in ('height','cm','bmi'):
        o=bpy.data.objects.get('SIM • '+n)
        if o:show(o,s.view_mode=='MAIN' and (has_height or show_previous))
    region=bpy.data.objects.get('SIM • body size region')
    if region:show(region,body_size_available(s))
    for prefix,visible in (('SIM • weight repeat ',ready_for_measurement),
                           ('SIM • height start ',ready_for_measurement and not has_height),
                           ('SIM • height repeat ',ready_for_measurement and has_height)):
        for obj in bpy.data.objects:
            if obj.name.startswith(prefix):show(obj,visible)
    state_obj=bpy.data.objects.get('SIM • state')
    if state_obj and ready_for_measurement:show(state_obj,False)
    for n in ('ready foot L','ready foot R','ready label'):
        o=bpy.data.objects.get('SIM • '+n)
        if o:show(o,s.view_mode=='MAIN' and not s.loaded and s.state!='HELD')
    ready=bpy.data.objects.get('SIM • ready label')
    if ready and s.message!='Scale ready':show(ready,False)
    message=bpy.data.objects.get('SIM • message')
    if message and not s.loaded and s.message=='Scale ready':show(message,False)

def input_changed(self,context):
    if not context or not context.scene or not hasattr(context.scene,'seca_study'):return
    s=context.scene.seca_study
    cancel_height(context.scene,'Weight changed; remeasure')
    if s.loaded:
        clear_held(s)
        s.measured_height_cm=0;s.height_result_manual=False
        if s.mother_stage=='ADULT_READY':
            s.adult_kg=0;update_tare_total(s);s.mother_stage='WAIT_ADULT'
        elif s.mother_stage in {'CHILD_READY','DONE'}:s.mother_stage='WAIT_CHILD'
        s.view_mode='MOTHER' if s.mother_stage in {'WAIT_ADULT','ADULT_READY','WAIT_CHILD','CHILD_READY'} else 'MAIN'
        clear_samples(context.scene)
        if s.gross_kg>360:
            s.state='OVERLOAD';s.message='Capacity exceeded'
        else:
            s.state='UNSTABLE';s.message='Input changed; remeasure'
    if s.loaded and s.measurement_mode=='GUIDED' and s.mother_stage=='NONE' and not s.voice_guided_sent and voice_reference_reached(s):
        s.voice_guided_sent=True;emit_voice(context.scene,'guidance','guidance_weight')
    if s.measurement_mode=='SELF' and s.self_stage=='CLOTHING' and not s.voice_clothing_sent and voice_reference_reached(s):
        s.voice_clothing_sent=True;emit_voice(context.scene,'guidance','guidance_clothing')
    if s.measurement_mode=='SELF' and s.self_stage not in {'READY','SELECT'}:
        if s.self_stage in {'HEIGHT_PREP','HEIGHT_RUNNING','HEIGHT_READ','RESULT','FINISHED'}:s.self_stage='WEIGHT'
        s.view_mode='SELF'
    refresh(context.scene)

def height_changed(self,context):
    if not context or not context.scene or not hasattr(context.scene,'seca_study'):return
    s=context.scene.seca_study
    cancel_height(context.scene,'Height changed; remeasure')
    sync_phantom(context.scene)
    if s.loaded and not s.height_result_manual and (s.state=='RESULT' or s.view_mode=='HEIGHT'):
        clear_held(s);s.measured_height_cm=0;s.state='WEIGHED';s.view_mode='MAIN';s.message='Height changed; remeasure'
    if s.measurement_mode=='SELF' and s.loaded and s.self_stage in {'HEIGHT_PREP','HEIGHT_RUNNING','HEIGHT_READ','RESULT','FINISHED'}:
        s.self_stage='WEIGHT';s.view_mode='SELF';s.measured_height_cm=0
    refresh(context.scene)

def height_units_changed(self,context):
    if not context or not context.scene or not hasattr(context.scene,'seca_study'):return
    s=context.scene.seca_study
    if s.view_mode=='MANUAL_HEIGHT':
        s.view_mode='MAIN';s.manual_height_draft='0';s.message='Units changed; manual entry cancelled'
    refresh(context.scene)

def source_changed(self,context):
    if not context or not context.scene or not hasattr(context.scene,'seca_study'):return
    s=context.scene.seca_study;cancel_height(context.scene,'Source changed; remeasure');sync_phantom(context.scene)
    if s.loaded and not s.height_result_manual and (s.state=='RESULT' or s.view_mode=='HEIGHT'):
        clear_held(s);s.state='WEIGHED';s.view_mode='MAIN';s.measured_height_cm=0;s.message='Source changed; remeasure'
    if s.measurement_mode=='SELF' and s.loaded and s.self_stage in {'HEIGHT_PREP','HEIGHT_RUNNING','HEIGHT_READ','RESULT','FINISHED'}:
        s.self_stage='WEIGHT';s.view_mode='SELF';s.measured_height_cm=0
    refresh(context.scene)

_self_internal=False
FAULT_DETAILS={
 'STARTUP_LOAD':('010-272XX-XXX','Excess startup load','Unload and restart.'),
 'ZERO_MOTION':('013-272XX-XXX','Zero point not found','Stop movement; restart.'),
 'CORNER':('020–023-272XX-XXX','Excess corner load','Redistribute; restart.'),
 'CELL':('001–008-272XX-XXX','Load-cell fault','Service scenario.'),
}
def fault_screen(scene):
    s=scene.seca_study;code,title,remedy=FAULT_DETAILS[s.fault_active]
    values={'code':code,'title':title,'remedy':remedy,'status':s.fault_status,
            'help label':'Close help' if s.fault_help else 'Help',
            'detail':('Injected study condition;\nno real sensor diagnosis.' if s.fault_help else '')}
    for name,value in values.items():
        o=bpy.data.objects.get('FAULT • '+name)
        if o:o.data.body=value

def activate_fault(scene,kind):
    s=scene.seca_study
    stop_audio()
    s.display_standby=False;s.idle_elapsed=0
    cancel_height(scene,'Study fault interrupted height');clear_samples(scene);clear_held(s)
    if s.cal_stage!='IDLE':calibration_fail(scene,'Study fault interrupted calibration');s.cal_stage='IDLE';sync_phantom(scene)
    s.measured_height_cm=0;s.height_result_manual=False;s.setup_remeasure_required=True;s.fault_active=kind;s.fault_help=False;s.fault_status='';s.state='FAULT';s.view_mode='FAULT';s.message='Injected study fault'
    refresh(scene)

def fault_action(scene,action):
    s=scene.seca_study
    if s.disconnected:s.message='Connect power first';refresh(scene);return
    if action=='FAULT_HELP':
        if s.fault_active!='NONE':s.fault_help=not s.fault_help
    elif action=='FAULT_INJECT':
        if s.fault_active!='NONE':s.fault_status='Restart to clear fault'
        elif s.fault_scenario=='CORNER' and not s.loaded:s.message='Load platform for corner study'
        elif s.fault_scenario in {'CORNER','CELL'}:activate_fault(scene,s.fault_scenario);return
        else:s.message='Choose corner or cell scenario'
    elif action=='FAULT_RESTART':
        stop_audio()
        scenario=s.fault_scenario
        if scenario=='STARTUP_LOAD':
            if s.loaded:activate_fault(scene,scenario);return
            s.fault_status='Load platform for this scenario'
        elif scenario=='ZERO_MOTION':activate_fault(scene,scenario);return
        elif scenario in {'CORNER','CELL'} and s.fault_active!='NONE':s.fault_status='Remove study condition first'
        elif s.loaded:s.fault_status='Unload before restart'
        else:
            s.fault_active='NONE';s.fault_help=False;s.fault_status='';s.setup_remeasure_required=False;s.state='READY';s.measured_height_cm=0
            s.self_stage='SELECT';s.view_mode='SELF';s.message='Select measurement mode'
    elif action=='STEP_OFF' and s.fault_active!='NONE':
        clear_samples(scene);clear_held(s);clear_temporary_tares(s);s.loaded=False;s.measured_height_cm=0
        if s.measurement_mode=='SELF':s.self_id='';s.synthetic_id=''
        s.fault_status='Unloaded; restart when ready'
    refresh(scene)

def self_next_enabled(s):
    if s.self_stage in {'SELECT','CLOTHING','HEIGHT_PREP','HEIGHT_READ','RESULT'}:return True
    if s.self_stage=='ID':return bool(s.synthetic_id.strip())
    if s.self_stage=='WEIGHT':return s.state=='WEIGHED'
    return False

def self_screen(scene):
    s=scene.seca_study
    content={
      'SELECT':('Select measurement mode','Choose after restart','','Self-measurement','Guided'),
      'READY':('Step onto the scale.','','','', ''),
      'CLOTHING':('Have you removed\nthe following?','','','Done',''),
      'ID':('Scan your barcode to\nstart the measurement','','','Scan ID','No barcode?'),
      'WEIGHT':('Your weight',weight_display(displayed_gross(s)-s.tare_kg,s.weight_units) if s.state=='WEIGHED' else ('OVER' if s.state=='OVERLOAD' else 'Measuring…'),'', '›','↻'),
      'HEIGHT_PREP':('Before measurement','','','Start',''),
      'HEIGHT_RUNNING':('Measuring height','','','', ''),
      'HEIGHT_READ':('Your height',height_display(s.preview_height_cm,s.height_units),'cm' if s.height_units=='CM' else 'ft/in','›','↻'),
      'RESULT':(s.self_id if s.self_network_snapshot and s.self_id else 'Your results',weight_display(displayed_gross(s)-s.tare_kg,s.weight_units),height_display(s.measured_height_cm,s.height_units) if s.measured_height_cm else 'Weight only','Ok',''),
      'FINISHED':(s.self_id if s.self_network_snapshot and s.self_id else 'Your results',weight_display(displayed_gross(s)-s.tare_kg,s.weight_units),height_display(s.measured_height_cm,s.height_units) if s.measured_height_cm else 'Weight only','',''),
    }
    values=content[s.self_stage]
    for name,value in zip(('title','line 1','line 2','primary label','secondary label'),values):
        o=bpy.data.objects.get('SELF • '+name)
        if o:o.data.body=value
    line1=bpy.data.objects.get('SELF • line 1');line2=bpy.data.objects.get('SELF • line 2')
    if line1:
        line1.data.size=.016 if s.self_stage in {'WEIGHT','HEIGHT_READ'} else .013 if s.self_stage in {'RESULT','FINISHED'} else .0056
        line1.location.z=.016 if s.self_stage in {'RESULT','FINISHED'} else .006 if s.self_stage in {'WEIGHT','HEIGHT_READ'} else .017
    if line2:
        line2.data.size=.010 if s.self_stage in {'RESULT','FINISHED'} and s.measured_height_cm else .0051
        line2.location.z=-.026 if s.self_stage in {'RESULT','FINISHED'} else -.017 if s.self_stage=='HEIGHT_READ' else -.001
    title=bpy.data.objects.get('SELF • title')
    if title:title.data.size=.005 if s.self_stage in {'CLOTHING','ID'} else .0058
    field=bpy.data.objects.get('SELF • value field')
    if field:
        field.hide_set(s.self_stage not in {'WEIGHT','HEIGHT_PREP','HEIGHT_READ','RESULT','FINISHED'});field.hide_render=field.hide_get()
        field.location.z=-.001 if s.self_stage in {'RESULT','FINISHED'} else .006
        field.scale.z=.084/.076 if s.self_stage in {'RESULT','FINISHED'} else 1
    for name,visible in [('primary region',bool(values[3]) and self_next_enabled(s)),('secondary region',bool(values[4]))]:
        o=bpy.data.objects.get('SELF • '+name)
        if o:o.hide_set(not visible);o.hide_render=not visible
    label=bpy.data.objects.get('SELF • primary label')
    if label:label.hide_set(s.self_stage in {'WEIGHT','HEIGHT_READ'} or not(bool(values[3]) and self_next_enabled(s)));label.hide_render=label.hide_get()
    label=bpy.data.objects.get('SELF • secondary label')
    if label:label.hide_set(s.self_stage in {'WEIGHT','HEIGHT_READ'});label.hide_render=label.hide_get()
    arrow=bpy.data.objects.get('SELFART • primary arrow')
    if arrow and not self_next_enabled(s):arrow.hide_set(True);arrow.hide_render=True
    primary=bpy.data.objects.get('SELF • primary region');primary_label=bpy.data.objects.get('SELF • primary label')
    if primary:primary.location.x=.013 if values[4] else 0;primary.scale.x=1 if values[4] else .084/.058
    if primary_label:primary_label.location.x=.013 if values[4] else 0
    if primary:
        primary.data.materials[0]=bpy.data.materials['SELF • white' if s.self_stage in {'CLOTHING','HEIGHT_PREP','ID'} else 'SELF • green']
    if primary_label:primary_label.data.materials[0]=bpy.data.materials['SELF • ink' if s.self_stage in {'CLOTHING','HEIGHT_PREP','ID'} else 'SELF • white']
    for name,value in [('weight unit','kg' if s.weight_units=='KG' else 'lb'),('result weight unit','kg' if s.weight_units=='KG' else 'lb'),('result height unit','cm' if s.height_units=='CM' else 'ft/in')]:
        o=bpy.data.objects.get('SELFART • '+name)
        if o:o.data.body=value
    for name in ('result height label','result height unit'):
        o=bpy.data.objects.get('SELFART • '+name)
        if o and s.self_stage in {'RESULT','FINISHED'} and not s.measured_height_cm:o.hide_set(True);o.hide_render=True
    lock=bpy.data.objects.get('SELFART • stable lock')
    if lock and s.state!='WEIGHED':lock.hide_set(True);lock.hide_render=True
    progress={'SELECT':0,'READY':0,'CLOTHING':0,'ID':0,'WEIGHT':1,'HEIGHT_PREP':2,'HEIGHT_RUNNING':2,'HEIGHT_READ':2,'RESULT':3,'FINISHED':3}[s.self_stage]
    for i in range(3):
        o=bpy.data.objects.get(f'SELF • progress {i}')
        if o:
            o.data.materials[0]=bpy.data.materials['SELF • green' if i<progress else 'SELF • field']
            o.hide_set(s.self_stage in {'SELECT','READY','CLOTHING','ID'});o.hide_render=o.hide_get()

def self_action(scene,action):
    global _self_internal
    s=scene.seca_study
    if s.disconnected:s.message='Connect power first';refresh(scene);return
    if action=='MODE_RESTART':
        stop_audio()
        if s.loaded:s.message='Unload before restart'
        elif s.transfer_state in {'PENDING','RETRY_WAIT'}:s.message='Wait for mock transfer'
        else:s.self_stage='SELECT';s.view_mode='SELF';s.message='Select measurement mode'
        refresh(scene);return
    if s.self_stage=='SELECT':
        if action in {'STEP_OFF','RESET'}:
            clear_samples(scene);clear_held(s);clear_temporary_tares(s);s.loaded=False;s.state='READY';s.measured_height_cm=0;s.self_id='';s.synthetic_id='';s.message='Select measurement mode'
        elif s.loaded:s.message='Unload before selecting mode'
        elif action=='SELF_BACK':s.measurement_mode='GUIDED';s.view_mode='MAIN';s.self_stage='READY';s.message='Guided measurement'
        elif action=='SELF_NEXT':s.measurement_mode='SELF';s.self_stage='READY';s.view_mode='SELF';s.message='Self-measurement'
        refresh(scene);return
    if s.measurement_mode!='SELF':return
    if action in {'STEP_OFF','RESET'}:
        stop_audio()
        cancel_height(scene,'Self study interrupted');clear_samples(scene);clear_held(s);clear_temporary_tares(s)
        s.loaded=False;s.state='READY';s.measured_height_cm=0;s.has_last=False;s.last_kg=0;s.last_net_kg=0;s.last_height_cm=0
        s.synthetic_id='';s.self_id='';s.self_stage='READY';s.view_mode='SELF';s.message='Scale ready';refresh(scene);return
    if action=='STEP_ON':
        if s.loaded:s.message='Already on platform'
        elif transport_is_tilted(scene):s.message='Return to standing first'
        else:
            clear_samples(scene);clear_held(s);s.loaded=True;s.state='READY';s.measured_height_cm=0;s.self_id='';s.net_data_expired=False;s.setup_remeasure_required=False
            s.self_network_snapshot=s.mock_network;s.self_weight_only_snapshot=s.self_weight_only
            s.self_stage='CLOTHING';s.view_mode='SELF';s.message='Remove heavy items'
            s.voice_clothing_sent=False
            if voice_reference_reached(s):s.voice_clothing_sent=True;emit_voice(scene,'guidance','guidance_clothing')
        refresh(scene);return
    if s.loaded and s.self_network_snapshot!=s.mock_network:
        s.message='Connection changed; step off and restart';refresh(scene);return
    if s.self_id and s.synthetic_id.strip()!=s.self_id:
        s.message='ID changed; step off and restart';refresh(scene);return
    if action=='SELF_BACK':
        if s.self_stage=='ID':s.message='No-barcode path not modeled'
        elif s.self_stage=='WEIGHT':
            s.filtered_kg=0;s.sample_time=0;clear_samples(scene);s.state='UNSTABLE'
            if not s.dynamic_weight:finish_weight(scene)
        elif s.self_stage=='HEIGHT_READ':s.self_stage='HEIGHT_PREP'
        refresh(scene);return
    if action!='SELF_NEXT' or not self_next_enabled(s):refresh(scene);return
    entering_weight=False;previous_voice_stage=s.self_stage
    if s.self_stage=='CLOTHING':
        s.self_stage='ID' if s.self_network_snapshot else 'WEIGHT'
        entering_weight=s.self_stage=='WEIGHT'
    elif s.self_stage=='ID':s.self_id=s.synthetic_id.strip();s.self_stage='WEIGHT';entering_weight=True
    elif s.self_stage=='WEIGHT':s.self_stage='RESULT' if s.self_weight_only_snapshot else 'HEIGHT_PREP'
    elif s.self_stage=='HEIGHT_PREP':
        s.self_stage='HEIGHT_RUNNING';s.view_mode='MAIN';_self_internal=True
        try:do_action(scene,'HEIGHT')
        finally:_self_internal=False
        if not s.height_measuring and s.self_stage=='HEIGHT_RUNNING':s.self_stage='HEIGHT_PREP';s.view_mode='SELF'
        refresh(scene);return
    elif s.self_stage=='HEIGHT_READ':
        s.view_mode='HEIGHT';_self_internal=True
        try:do_action(scene,'HEIGHT_ACCEPT')
        finally:_self_internal=False
        s.self_stage='RESULT' if s.state=='RESULT' else 'HEIGHT_PREP'
    elif s.self_stage=='RESULT':
        if s.state not in {'WEIGHED','RESULT'} or s.setup_remeasure_required:s.message='Remeasure first';refresh(scene);return
        if s.self_network_snapshot:
            if not s.self_id:s.message='Synthetic ID required';refresh(scene);return
            if s.transfer_state in {'PENDING','RETRY_WAIT'}:s.message='Mock transfer already in progress';refresh(scene);return
            start_transfer(scene)
            if s.transfer_state!='PENDING':refresh(scene);return
        s.self_stage='FINISHED'
    if entering_weight:
        s.filtered_kg=0;s.sample_time=0;clear_samples(scene)
        if s.gross_kg>SECA_654_MAX_CAPACITY_KG:s.state='OVERLOAD';s.message='Capacity exceeded'
        elif s.dynamic_weight:s.state='UNSTABLE';s.message='Measuring weight'
        else:finish_weight(scene)
    if s.self_stage!=previous_voice_stage:
        cue={'ID':'guidance_id','WEIGHT':'guidance_weight','HEIGHT_PREP':'guidance_height','FINISHED':'guidance_finished'}.get(s.self_stage)
        if cue and voice_reference_reached(s):emit_voice(scene,'guidance',cue)
        if s.self_stage=='RESULT' and s.state in {'WEIGHED','RESULT'}:emit_voice(scene,'results','result')
    s.view_mode='SELF';refresh(scene)

def manual_height_action(scene,action):
    s=scene.seca_study
    if s.disconnected or not s.loaded or s.state!='RESULT' or s.height_units!=s.manual_height_units:
        s.view_mode='MAIN';s.manual_height_status='';s.message='Manual entry interrupted';return
    value=s.manual_height_draft
    if action.startswith('HEIGHT_MANUAL_DIGIT_'):
        digit=action.rsplit('_',1)[1]
        if digit in '0123456789' and len(digit)==1 and len(value)<7:
            value=digit if value=='0' else value+digit
            s.manual_height_draft=value;s.manual_height_status=''
    elif action=='HEIGHT_MANUAL_DOT':
        if '.' not in value and len(value)<7:s.manual_height_draft=value+'.';s.manual_height_status=''
    elif action=='HEIGHT_MANUAL_DELETE':
        s.manual_height_draft=value[:-1] or '0';s.manual_height_status=''
    elif action=='HEIGHT_MANUAL_CANCEL':
        s.view_mode='MAIN';s.manual_height_status='';s.message='Manual entry cancelled'
    elif action=='HEIGHT_MANUAL_APPLY':
        try:entered=float(value);height=entered if s.manual_height_units=='CM' else entered*2.54
        except (ValueError,OverflowError):height=float('nan')
        if not math.isfinite(height) or not 1<=height<=300:
            s.manual_height_status='Study range: 1–300 cm';return
        s.measured_height_cm=quantize(height,.1);s.height_result_manual=True
        s.last_net_kg=displayed_gross(s)-s.tare_kg;s.last_height_cm=s.measured_height_cm;s.has_last=True;s.state='RESULT';s.view_mode='MAIN';s.manual_height_status='';s.message='Manual height captured (simulated)'
        arm_network_clear(scene)
        if s.measurement_mode=='GUIDED':emit_voice(scene,'results','result')

def do_action(scene,action):
    if check_platform_change(scene) and action not in {'CAL_CANCEL','RESET'}:return
    s=scene.seca_study
    if action in {'HEIGHT','HEIGHT_REPEAT','HEIGHT_ACCEPT','HEIGHT_FIELD','HEIGHT_REPEAT_MAIN','CONFIRM','OVERVIEW_SEND','HOLD','MOTHER_ADVANCE','MOTHER_NEXT','MOTHER_ACCEPT','SELF_NEXT'} and require_live_sampling(scene):return
    if action=='WAKE':wake_display(scene);return
    if not s.disconnected and not s.display_standby:s.idle_elapsed=0
    if not _self_internal and action=='MODE_RESTART' and s.fault_scenario in {'STARTUP_LOAD','ZERO_MOTION'}:
        fault_action(scene,'FAULT_RESTART');return
    if not _self_internal and (action in {'FAULT_HELP','FAULT_INJECT','FAULT_RESTART'} or (s.fault_active!='NONE' and action=='STEP_OFF')):
        fault_action(scene,action);return
    if not _self_internal and s.fault_active!='NONE':
        s.fault_status='Clear condition and restart';refresh(scene);return
    if not _self_internal and (action.startswith('SELF_') or action=='MODE_RESTART' or (s.measurement_mode=='SELF' and action in {'STEP_ON','STEP_OFF','RESET'})):
        self_action(scene,action);return
    if not _self_internal and s.self_stage=='SELECT' and s.view_mode=='SELF':
        s.message='Select a measurement mode';refresh(scene);return
    if not _self_internal and s.measurement_mode=='SELF' and action!='PHANTOM_SNAP':
        s.message='Self-measurement uses its guided controls';refresh(scene);return
    if s.cal_stage!='IDLE' and action not in {'CAL_NEXT','CAL_CANCEL','RESET'}:
        s.message='Finish calibration study first';refresh(scene);return
    if action=='RESET' and s.cal_stage!='IDLE':
        s.cal_valid=False;s.cal_stage='IDLE';s.view_mode='MAIN';sync_phantom(scene)
    if s.view_mode=='MANUAL_HEIGHT' and not (action.startswith('HEIGHT_MANUAL_') or action in {'STEP_OFF','RESET'}):
        s.message='Finish manual height entry first';refresh(scene);return
    if s.height_measuring and action not in {'HEIGHT','HEIGHT_CANCEL','PHANTOM_SNAP'}:
        if action in {'RESET','STEP_OFF'}:cancel_height(scene,'Height measurement interrupted')
        else:s.message='Height measurement in progress';refresh(scene);return
    if s.disconnected and action in {'HOLD','RELEASE_HOLD','CLEAR_RESULT','REPEAT','TARE','CLEAR_TARE','TARE_MENU','TARE_CANCEL','TARE_ADDITIONAL','CLOTHING_START','CLOTHING_PLUS','CLOTHING_MINUS','CLOTHING_ACCEPT','MOTHER_START','MOTHER_BEGIN','MOTHER_NEXT','MOTHER_REPEAT','MOTHER_CANCEL','MOTHER_ADVANCE','MOTHER_ACCEPT','APPLY_PRE_TARE','DELETE_PRE_TARE','SCAN_TARE','CLEAR_SCANS'}:
        s.message='Connect power first';refresh(scene);return
    if action in {'HEIGHT_ACCEPT','CONFIRM','OVERVIEW_SEND'} and invalidate_changed_geometry(scene):
        refresh(scene);return
    if action=='RESET':
        stop_audio()
        clear_samples(scene);clear_held(s);s.loaded=False;s.height_result_manual=False;s.setup_remeasure_required=False;clear_temporary_tares(s);s.state='READY';s.message='Scale ready';s.last_kg=0;s.last_net_kg=0;s.last_height_cm=0;s.has_last=False;s.measured_height_cm=0;s.view_mode='MAIN'
    elif action=='STEP_ON':
        if s.disconnected:
            if s.measurement_mode=='SELF':s.self_stage='READY';s.self_id=''
            s.message='Connect power first'
        elif s.mother_stage=='INTRO':
            s.message='Start mother child first'
        elif s.loaded and s.mother_stage in {'ADULT_READY','CHILD_READY'}:
            s.message='Continue or repeat measurement'
        elif transport_is_tilted(scene):
            s.message='Return to standing first'
        elif s.gross_kg>360:
            clear_held(s);s.loaded=True;s.state='OVERLOAD';s.message='Capacity exceeded'
        else:
            s.net_data_expired=False;clear_held(s);s.loaded=True;s.measured_height_cm=0;s.height_result_manual=False;s.view_mode='MOTHER' if s.mother_stage in {'WAIT_ADULT','ADULT_READY','WAIT_CHILD','CHILD_READY'} else 'MAIN';clear_samples(scene)
            s.voice_guided_sent=False
            if s.measurement_mode=='GUIDED' and s.mother_stage=='NONE' and voice_reference_reached(s):s.voice_guided_sent=True;emit_voice(scene,'guidance','guidance_weight')
            if s.dynamic_weight:
                s.filtered_kg=0;s.sample_time=0;s.state='UNSTABLE';s.message='Measuring weight'
            else:finish_weight(scene)
    elif action=='STEP_OFF':
        stop_audio()
        if not s.loaded:s.message='Value held' if s.state=='HELD' else 'Scale ready'
        else:
            eligible=s.state in {'WEIGHED','RESULT'} and s.mother_stage in {'NONE','DONE'}
            retain=eligible and (s.manual_hold or effective_hold(s)) and retention_policy(s)!='UNLOAD'
            if retain:
                s.held_net_kg=displayed_gross(s)-s.tare_kg;s.held_tare_kg=s.tare_kg;s.held_height_cm=s.measured_height_cm if s.state=='RESULT' else 0;s.held_valid=True;s.held_elapsed=0
            else:clear_held(s)
            clear_samples(scene);s.loaded=False;clear_temporary_tares(s);s.state='HELD' if retain else 'READY';s.message='Value held' if retain else 'Scale ready';s.view_mode='MAIN'
    elif action=='HOLD':
        if s.loaded and s.state in {'WEIGHED','RESULT'} and s.mother_stage in {'NONE','DONE'}:s.manual_hold=True;s.message='Hold armed'
        else:s.message='Stable result required'
    elif action=='RELEASE_HOLD':
        clear_held(s)
        if s.state=='HELD':s.state='READY'
        s.message='Hold cleared'
    elif action=='CLEAR_RESULT':
        clear_held(s);s.measured_height_cm=0;s.height_result_manual=False;s.view_mode='MAIN'
        if s.state=='HELD':s.state='READY'
        elif s.loaded and s.state=='RESULT':s.state='WEIGHED'
        s.message='Result cleared'
    elif action=='REPEAT':
        if s.loaded and s.state not in {'OVERLOAD','UNSTABLE'} and s.mother_stage=='NONE':do_action(scene,'STEP_ON');return
        else:s.message='Stable load required'
    elif action=='TRANSPORT_ARC':
        drive_arc(scene);return
    elif action=='TARE':
        if s.mother_stage!='NONE':s.message='Finish mother child first'
        elif s.loaded and s.state in {'WEIGHED','RESULT'}:
            base=s.tare_kg-s.additional_kg
            if displayed_gross(s)>=base and set_tare_component(s,'additional_kg',displayed_gross(s)-base):
                clear_held(s);s.state='WEIGHED';s.measured_height_cm=0;s.view_mode='MAIN';s.message='Tare captured (simulated)'
            else:s.message='Tare exceeds load'
        else:s.message='Load platform to tare'
    elif action=='CLEAR_TARE':
        clear_held(s);clear_temporary_tares(s,True);s.measured_height_cm=0;s.view_mode='MAIN'
        if s.loaded and s.state not in {'OVERLOAD','UNSTABLE'}:s.state='WEIGHED'
        elif not s.loaded:s.state='READY'
        s.message='Tare cleared'
    elif action=='TARE_MENU':s.view_mode='TARE_MENU';s.message='Tare assistant'
    elif action=='TARE_CANCEL':s.view_mode='MAIN';s.message='Tare cancelled'
    elif action=='TARE_ADDITIONAL':do_action(scene,'TARE');return
    elif action=='CLOTHING_START':
        if s.loaded:s.message='Unload before clothing tare'
        else:s.clothing_draft_kg=s.pre_tare_kg;s.view_mode='TARE_EDIT';s.message='Adjust clothing tare'
    elif action in {'CLOTHING_PLUS','CLOTHING_MINUS'}:
        if s.view_mode=='TARE_EDIT':
            step=.5 if s.weight_units=='KG' else .45359237
            s.clothing_draft_kg=max(0,min(360,s.clothing_draft_kg+(step if action=='CLOTHING_PLUS' else -step)))
    elif action=='CLOTHING_ACCEPT':
        if not s.loaded and s.view_mode=='TARE_EDIT':
            old_active,old_value,old_suppressed=s.clothing_active,s.clothing_kg,s.preset_suppressed
            s.clothing_active=True;s.clothing_kg=s.clothing_draft_kg;s.preset_suppressed=False
            if update_tare_total(s):s.view_mode='MAIN';s.message='Clothing tare set'
            else:s.clothing_active=old_active;s.clothing_kg=old_value;s.preset_suppressed=old_suppressed;update_tare_total(s);s.message='Total tare exceeds 360 kg'
    elif action=='MOTHER_START':
        if s.loaded:s.message='Unload before mother child'
        else:s.adult_kg=0;update_tare_total(s);s.mother_stage='INTRO';s.view_mode='MOTHER';s.message='Start mother child study'
    elif action=='MOTHER_BEGIN':
        if not s.loaded and s.view_mode=='MOTHER' and s.mother_stage=='INTRO':s.mother_stage='WAIT_ADULT';s.message='Step on without child'
    elif action=='MOTHER_NEXT':
        if s.loaded and s.state=='WEIGHED' and s.view_mode=='MOTHER' and s.mother_stage=='ADULT_READY':s.mother_stage='WAIT_CHILD';s.message='Adult remains; add child'
    elif action=='MOTHER_REPEAT':
        if s.loaded and s.view_mode=='MOTHER' and s.state=='WEIGHED' and s.mother_stage in {'ADULT_READY','CHILD_READY'}:
            if s.mother_stage=='ADULT_READY':s.adult_kg=0;update_tare_total(s);s.mother_stage='WAIT_ADULT'
            else:s.mother_stage='WAIT_CHILD'
            do_action(scene,'STEP_ON');return
    elif action=='MOTHER_CANCEL':
        if s.view_mode=='MOTHER':s.adult_kg=0;update_tare_total(s);s.mother_stage='NONE';s.view_mode='MAIN';s.message='Mother child study cancelled'
    elif action=='MOTHER_ADVANCE':
        if s.view_mode=='MOTHER':
            target={'INTRO':'MOTHER_BEGIN','ADULT_READY':'MOTHER_NEXT','CHILD_READY':'MOTHER_ACCEPT'}.get(s.mother_stage)
            if target:do_action(scene,target);return
    elif action=='MOTHER_ACCEPT':
        if s.loaded and s.state=='WEIGHED' and s.view_mode=='MOTHER' and s.mother_stage=='CHILD_READY':
            s.mother_stage='DONE';s.view_mode='MAIN';s.last_kg=displayed_gross(s);s.last_net_kg=s.last_kg-s.tare_kg;s.last_height_cm=0;s.has_last=True;s.message='Child result accepted'
            arm_network_clear(scene);emit_voice(scene,'results','result')
        else:s.message='Stable child weight required'
    elif action=='APPLY_PRE_TARE':
        if s.loaded:s.message='Unload before pre-tare'
        elif s.pre_tare_input+s.additional_kg+s.scanned_kg+s.adult_kg>360:s.message='Total tare exceeds 360 kg'
        else:s.pre_tare_kg=s.pre_tare_input;s.preset_suppressed=False;s.clothing_active=False;update_tare_total(s);s.message='Pre-tare saved'
    elif action=='DELETE_PRE_TARE':
        if s.loaded:s.message='Unload before pre-tare'
        else:s.pre_tare_kg=0;s.preset_suppressed=False;s.clothing_active=False;update_tare_total(s);s.message='Pre-tare deleted'
    elif action=='SCAN_TARE':
        if not s.scanner_attached:s.message='Attach mock scanner first'
        elif s.loaded:s.message='Unload before scan'
        elif s.scan_input_kg<=0:s.message='Scan weight must be positive'
        elif set_tare_component(s,'scanned_kg',s.scanned_kg+s.scan_input_kg):s.message='Synthetic tare scanned'
        else:s.message='Total tare exceeds 360 kg'
    elif action=='CLEAR_SCANS':
        s.scanned_kg=0;update_tare_total(s);s.measured_height_cm=0;s.view_mode='MAIN';s.state='WEIGHED' if s.loaded and s.state=='RESULT' else s.state
        if s.loaded and s.mother_stage=='DONE':s.mother_stage='CHILD_READY'
        if s.loaded and s.state=='WEIGHED':s.last_net_kg=displayed_gross(s)-s.tare_kg;s.last_height_cm=0
        s.message='Scanned tares cleared'
    elif action=='CAL_START':
        if s.disconnected:s.message='Connect power first'
        elif s.loaded:s.message='Unload before calibration'
        elif s.height_measuring:s.message='Finish height measurement first'
        elif s.view_mode!='MAIN':s.message='Close current screen first'
        elif not record_platform_calibration(scene):s.message='Platform geometry unavailable'
        else:s.cal_valid=False;s.cal_stage='INTRO';s.view_mode='CALIBRATION';s.message='Calibration study';sync_phantom(scene)
    elif action=='CAL_CANCEL':
        s.cal_valid=False;s.cal_stage='IDLE';s.cal_elapsed=0;s.view_mode='MAIN';s.message='Calibration study cancelled';sync_phantom(scene)
    elif action=='CAL_NEXT':
        if s.cal_stage=='INTRO':s.cal_stage='WAIT_EMPTY';s.message='Prepare empty scan'
        elif s.cal_stage=='WAIT_EMPTY':
            if s.loaded:s.message='Unload before calibration'
            elif s.cal_rod_placed:s.message='Remove study rod first'
            elif not s.cal_area_clear:s.message='Confirm study area clear'
            else:s.cal_stage='EMPTY_SCAN';s.cal_elapsed=0;s.cal_duration_snapshot=s.cal_duration;s.message='Empty scan in progress'
        elif s.cal_stage=='SUCCESS':s.cal_stage='REMOVE_ROD';s.message='Remove study rod'
        elif s.cal_stage=='REMOVE_ROD':
            if s.cal_rod_placed:s.message='Remove study rod first'
            else:s.cal_valid=True;s.cal_stage='IDLE';s.view_mode='MAIN';s.message='Study calibration complete';sync_phantom(scene);record_calibration_transport_pose(scene)
        elif s.cal_stage=='FAILED':
            if record_platform_calibration(scene):s.cal_stage='WAIT_EMPTY';s.message='Prepare empty scan'
            else:s.message='Platform geometry unavailable'
        elif s.cal_stage in {'EMPTY_SCAN','WAIT_ROD','ROD_SCAN'}:s.message='Calibration study in progress'
    elif action=='HEIGHT_FIELD':
        if main_measurement_ready(s) and s.state=='RESULT':
            s.manual_height_draft='0';s.manual_height_units=s.height_units;s.manual_height_status=''
            s.view_mode='MANUAL_HEIGHT';s.message='Enter a manual study value'
    elif action=='HEIGHT_REPEAT_MAIN':
        if main_measurement_ready(s) and s.state=='RESULT':do_action(scene,'HEIGHT');return
    elif action.startswith('HEIGHT_MANUAL_'):
        if s.view_mode=='MANUAL_HEIGHT':manual_height_action(scene,action)
    elif action=='FAN_SAMPLE':
        if not s.disconnected and s.height_source=='FAN':
            value,error,_=fan_height(scene);s.message=error if value is None else f'Fan estimate: {value:.1f} cm'
    elif action=='PHANTOM_SNAP':
        if s.height_source not in {'GEOMETRY','ARRAY','FAN'}:s.message='Choose a geometry height source'
        elif platform_surface_z(scene,0,.070) is None:s.message='Platform surface unavailable'
        else:
            cancel_height(scene,'Subject repositioned; remeasure')
            if s.loaded and not s.height_result_manual and (s.state=='RESULT' or s.view_mode=='HEIGHT'):
                clear_held(s);s.state='WEIGHED';s.view_mode='MAIN';s.measured_height_cm=0
            sync_phantom(scene)
            if s.measurement_mode=='SELF' and s.loaded and not s.height_result_manual:
                s.self_stage='WEIGHT';s.view_mode='SELF'
            s.message='Subject aligned to modeled glass; remeasure'
    elif action=='HEIGHT':
        if s.disconnected:s.message='Connect power first'
        elif s.height_measuring:s.message='Height measurement in progress'
        elif s.mother_stage!='NONE':s.message='Finish mother child first'
        elif not s.loaded or s.state in {'OVERLOAD','UNSTABLE'}:s.message='Stable weight required'
        elif s.gross_kg<s.height_gate_kg:s.message='Below study height load gate'
        elif not s.cal_valid:s.message='Complete calibration study'
        elif s.cal_rod_placed:s.message='Remove study rod first'
        else:
            # A new acquisition invalidates the current committed height before
            # sampling, even when it is started from a completed result.
            s.state='WEIGHED';s.measured_height_cm=0;s.height_result_manual=False
            if s.view_mode=='HEIGHT':s.view_mode='MAIN'
            value,error,signature=height_candidate(scene)
            if value is None:s.state='WEIGHED';s.measured_height_cm=0;s.message=error
            elif not 100<=quantize(value,.1)<=220:s.state='WEIGHED';s.measured_height_cm=0;s.message='Height outside 100–220 cm'
            else:
                s.geometry_snapshot_cm=value;s.array_snapshot_json=signature
                begin_height_audio(scene)
                if s.measurement_mode=='GUIDED' and voice_reference_reached(s):emit_voice(scene,'guidance','guidance_height')
                if s.timed_height:
                    s.height_elapsed=0;s.height_duration_snapshot=s.height_duration;s.height_measuring=True;s.view_mode='MEASURING';s.message='Height measurement in progress'
                else:finish_height(scene,value,signature)
    elif action=='HEIGHT_REPEAT':
        if not s.disconnected and s.view_mode=='HEIGHT':
            # Do not leave an old preview acceptable if a fresh measurement
            # fails or its prerequisites have changed.
            s.view_mode='MAIN';s.measured_height_cm=0
            do_action(scene,'HEIGHT');return
    elif action in {'HEIGHT_PLUS','HEIGHT_MINUS'}:
        if not s.disconnected and s.view_mode=='HEIGHT':
            step=.5 if s.height_units=='CM' else .3175
            s.preview_height_cm=max(100,min(220,s.preview_height_cm+(step if action=='HEIGHT_PLUS' else -step)))
    elif action=='HEIGHT_ACCEPT':
        if not s.disconnected and s.view_mode=='HEIGHT' and s.loaded and s.state=='WEIGHED':
            s.measured_height_cm=s.preview_height_cm;s.height_result_manual=False;s.last_net_kg=displayed_gross(s)-s.tare_kg;s.last_height_cm=s.measured_height_cm;s.has_last=True;s.state='RESULT';s.view_mode='MAIN';s.message='Height captured (simulated)'
            arm_network_clear(scene)
            if s.measurement_mode=='GUIDED':emit_voice(scene,'results','result')
    elif action=='HEIGHT_CANCEL':
        cancel_height(scene,'Height cancelled');s.view_mode='MAIN';s.measured_height_cm=0;s.message='Height cancelled'
    elif action=='RECALL':
        if s.disconnected:s.message='Connect power first'
        elif s.has_last:s.view_mode='RECALL';s.message='Previous measurement'
        else:s.message='No previous measurement'
    elif action=='RECALL_CLOSE':s.view_mode='MAIN';s.message='Recall closed'
    elif action=='OPEN_MESSAGE':
        if not s.disconnected and s.view_mode=='MAIN' and s.message:s.message_page=0;s.view_mode='MESSAGE'
    elif action=='CLOSE_MESSAGE':
        if s.view_mode=='MESSAGE':s.view_mode='MAIN'
    elif action=='MESSAGE_PREVIOUS':
        if s.view_mode=='MESSAGE':s.message_page=max(0,s.message_page-1)
    elif action=='MESSAGE_NEXT':
        if s.view_mode=='MESSAGE':s.message_page=min(len(layout_message(s.message)[1])-1,s.message_page+1)
    elif action=='MENU_OPEN':
        if not s.disconnected and s.view_mode=='MAIN':s.menu_page='ROOT';s.view_mode='SETTINGS'
    elif action=='MENU_HOME':
        if s.view_mode=='SETTINGS':s.view_mode='MAIN';s.message='Settings closed'
    elif action=='MENU_BACK':
        if s.view_mode=='SETTINGS':
            if s.menu_page=='ROOT':s.view_mode='MAIN';s.message='Settings closed'
            else:menu_back(s)
    elif action.startswith('NETDATA_'):
        if not s.disconnected and not s.display_standby and s.view_mode=='SETTINGS' and s.menu_page=='NET_CLEAR_DATA':
            if action.startswith('NETDATA_DIGIT_'):
                digit=action.rsplit('_',1)[1]
                if len(digit)==1 and digit.isdigit():
                    value='0' if s.net_clear_replace else s.net_clear_draft;s.net_clear_replace=False
                    if len(value)<4:s.net_clear_draft=digit if value=='0' else value+digit;s.net_clear_overflow=False;s.net_clear_status=''
                    else:s.net_clear_overflow=True;s.net_clear_status='Too many digits'
            elif action=='NETDATA_DELETE':s.net_clear_draft=s.net_clear_draft[:-1] or '0';s.net_clear_replace=False;s.net_clear_overflow=False;s.net_clear_status=''
            elif action=='NETDATA_CLEAR':s.net_clear_draft='0';s.net_clear_replace=True;s.net_clear_overflow=False;s.net_clear_status=''
            elif action=='NETDATA_ACCEPT':
                value=int(s.net_clear_draft or '0')
                if s.net_clear_overflow:s.net_clear_status='Too many digits'
                elif value==0:s.net_clear_draft='300';s.net_clear_replace=False;s.net_clear_status='Default suggested; confirm'
                elif not 10<=value<=3600:s.net_clear_status='Use 10–3600 seconds'
                else:
                    s.net_clear_seconds=value;s.net_clear_elapsed=0;s.net_clear_status='';s.menu_page='NET_IDENTIFICATION'
    elif action.startswith('PRETARE_'):
        if not s.disconnected and not s.display_standby and s.view_mode=='SETTINGS':
            if action=='PRETARE_OPEN' and s.menu_page=='PRETARE':
                if s.loaded:s.message='Unload before pre-tare'
                else:
                    s.pre_tare_edit_units=s.weight_units;s.pre_tare_draft=format_pre_tare(s.pre_tare_kg,s.weight_units);s.pre_tare_replace_next=True;s.pre_tare_edit_status='';s.menu_page='PRETARE_EDIT'
            elif s.menu_page=='PRETARE_EDIT':
                value=s.pre_tare_draft
                if action.startswith('PRETARE_DIGIT_'):
                    digit=action.rsplit('_',1)[1]
                    if len(digit)==1 and digit.isdigit():
                        if s.pre_tare_replace_next:value='0';s.pre_tare_replace_next=False
                        if len(value)<7 and ('.' not in value or len(value.split('.',1)[1])<2):s.pre_tare_draft=digit if value=='0' else value+digit;s.pre_tare_edit_status=''
                elif action=='PRETARE_DECIMAL':
                    if s.pre_tare_replace_next:value='0';s.pre_tare_replace_next=False
                    if '.' not in value and len(value)<7:s.pre_tare_draft=value+'.';s.pre_tare_edit_status=''
                elif action=='PRETARE_DELETE':s.pre_tare_draft=value[:-1] or '0';s.pre_tare_replace_next=False;s.pre_tare_edit_status=''
                elif action=='PRETARE_CLEAR':s.pre_tare_draft='0';s.pre_tare_replace_next=True;s.pre_tare_edit_status=''
                elif action=='PRETARE_ACCEPT':
                    try:entered=float(value);kg=entered if s.pre_tare_edit_units=='KG' else entered*.45359237
                    except (ValueError,OverflowError):kg=float('nan')
                    if s.loaded:s.pre_tare_edit_status='Unload before saving'
                    elif s.weight_units!=s.pre_tare_edit_units:s.pre_tare_edit_status='Units changed; reopen'
                    elif not math.isfinite(kg) or kg<0 or kg>360 or kg+s.additional_kg+s.scanned_kg+s.adult_kg>360:s.pre_tare_edit_status='Study tare out of range'
                    else:
                        s.pre_tare_input=kg;do_action(scene,'APPLY_PRE_TARE');s.menu_page='PRETARE';s.pre_tare_edit_status=''
    elif action in {'MENU_PAGE_PREVIOUS','MENU_PAGE_NEXT'}:
        if not s.disconnected and not s.display_standby and s.view_mode=='SETTINGS':
            if action=='MENU_PAGE_PREVIOUS' and s.menu_page=='DISPLAY_MORE':s.menu_page='DISPLAY'
            elif action=='MENU_PAGE_NEXT' and s.menu_page=='DISPLAY':s.menu_page='DISPLAY_MORE'
    elif action=='BODY_CYCLE':
        if body_size_available(s):
            order=('BMI','DUBOIS','HAYCOCK','MOSTELLER');s.indicator=order[(order.index(s.indicator)+1)%len(order)]
    elif action.startswith('MENU_ROW_'):
        if s.view_mode=='SETTINGS':menu_select(scene,int(action.rsplit('_',1)[1])-1)
    elif action in {'BRIGHTNESS_MINUS','BRIGHTNESS_PLUS','BRIGHTNESS_ACCEPT'}:
        if not s.disconnected and s.view_mode=='SETTINGS' and s.menu_page=='BRIGHTNESS':
            if action=='BRIGHTNESS_MINUS':s.brightness_draft=max(1,s.brightness_draft-1)
            elif action=='BRIGHTNESS_PLUS':s.brightness_draft=min(5,s.brightness_draft+1)
            else:s.display_brightness=s.brightness_draft;s.menu_page='DISPLAY'

    elif action in {'AUDIO_LEVEL_MINUS','AUDIO_LEVEL_PLUS','AUDIO_LEVEL_ACCEPT'}:
        if not s.disconnected and s.view_mode=='SETTINGS' and s.menu_page=='AUDIO_VOLUME':
            if action=='AUDIO_LEVEL_MINUS':s.volume_draft=max(0,s.volume_draft-1)
            elif action=='AUDIO_LEVEL_PLUS':s.volume_draft=min(5,s.volume_draft+1)
            else:s.audio_volume=s.volume_draft;s.menu_page='AUDIO'
    elif action=='LOGOUT_IDS':
        if s.disconnected:s.message='Connect power first'
        elif s.view_mode!='MAIN' or not s.mock_network:s.message='Mock connection required'
        else:
            s.synthetic_id='';s.synthetic_user_id='';s.message='Synthetic IDs cleared'
    elif action=='TRANSFER_RETRY':retry_transfer(scene)
    elif action=='TRANSFER_CANCEL':
        if s.transfer_state in {'PENDING','RETRY_WAIT'}:s.transfer_state='FAILED';s.transfer_error='cancelled';s.message='Mock transfer cancelled'
        else:s.message='No mock transfer in progress'
    elif action=='CONFIRM':
        if s.disconnected:s.message='Connect power first'
        elif s.view_mode!='MAIN':s.message='Close current screen first'
        elif s.gross_kg>360 or s.state=='OVERLOAD':s.message='Capacity exceeded'
        elif not s.mock_network:s.message='Standalone: no send'
        elif s.state!='RESULT' and not(s.state=='WEIGHED' and s.mother_stage=='DONE'):s.message='Complete measurement first'
        elif s.transfer_state in {'PENDING','RETRY_WAIT'}:s.message='Mock transfer already in progress'
        else:s.view_mode='OVERVIEW';s.message='Review synthetic IDs'
    elif action=='OVERVIEW_CLOSE':
        if s.view_mode=='OVERVIEW':s.view_mode='MAIN';s.message='Review closed'
    elif action=='OVERVIEW_SEND':
        # Recheck every eligibility condition at submission time.  The payload
        # is frozen only now; opening a review never starts a transfer.
        if s.disconnected:s.message='Connect power first'
        elif s.view_mode!='OVERVIEW':s.message='Open overview first'
        elif s.gross_kg>360 or s.state=='OVERLOAD':s.message='Capacity exceeded'
        elif not s.mock_network:s.message='Standalone: no send'
        elif s.state!='RESULT' and not(s.state=='WEIGHED' and s.mother_stage=='DONE'):s.message='Complete measurement first'
        elif not s.synthetic_id.strip():s.message='Synthetic ID required'
        else:
            start_transfer(scene)
            if s.transfer_state=='PENDING':s.view_mode='MAIN'
    refresh(scene)

# Study-only fingerprint: evaluated glass vertices and head object transforms
# are compared in the product frame. These thresholds are not metrology.
import hashlib
_platform_signature_cache={}
_platform_watch_guard=False
PLATFORM_TOLERANCE_M=1e-5

def platform_geometry_signature(scene,depsgraph=None):
    root=scene.objects.get('CONTROL • product root');glass=scene.objects.get('654 • Bearclaw glass top')
    if root is None or glass is None or glass.type!='MESH':return None
    try:
        depsgraph=depsgraph or bpy.context.evaluated_depsgraph_get()
        if platform_surface_z(scene,0,.070,depsgraph) is None:return None
        obj=glass.evaluated_get(depsgraph);root_world=root.evaluated_get(depsgraph).matrix_world
        if abs(root_world.determinant())<1e-12:return None
        matrix=root_world.inverted()@obj.matrix_world;mesh=obj.to_mesh()
        try:
            if mesh is None or len(mesh.vertices)==0 or len(mesh.polygons)==0:return None
            coords=[float(c) for vertex in mesh.vertices for c in (matrix@vertex.co)]
            if not all(math.isfinite(v) for v in coords):return None
            topology=hashlib.sha256(repr([tuple(poly.vertices) for poly in mesh.polygons]).encode('ascii')).hexdigest()
            sensors=[]
            for name in HEAD_REFERENCE_OBJECTS:
                source=scene.objects.get(name)
                if source is None:return None
                pose=root_world.inverted()@source.evaluated_get(depsgraph).matrix_world
                if abs(pose.determinant())<1e-12:return None
                sensors.extend(float(pose[row][col]) for row in range(4) for col in range(4))
            if not all(math.isfinite(v) for v in sensors):return None
            return {'vertices':coords,'topology':topology,'sensors':sensors}
        finally:obj.to_mesh_clear()
    except (ValueError,RuntimeError,ReferenceError,ZeroDivisionError):return None

def platform_signatures_differ(a,b):
    if a is None or b is None:return a is not b
    try:
        aa=a['vertices'];bb=b['vertices']
        if not isinstance(aa,list) or not isinstance(bb,list) or not aa or not bb:return True
        if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in aa+bb):return True
        sa=a['sensors'];sb=b['sensors']
        if not isinstance(sa,list) or not isinstance(sb,list) or len(sa)!=len(sb) or not sa:return True
        if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in sa+sb):return True
        return a['topology']!=b['topology'] or len(aa)!=len(bb) or any(abs(x-y)>PLATFORM_TOLERANCE_M for x,y in zip(aa,bb)) or any(abs(x-y)>PLATFORM_TOLERANCE_M for x,y in zip(sa,sb))
    except (KeyError,TypeError,ValueError):return True

def record_platform_calibration(scene):
    sig=platform_geometry_signature(scene)
    if sig is None:return False
    scene['seca_calibration_glass_signature']=json.dumps(sig,separators=(',',':'))
    _platform_signature_cache[scene.as_pointer()]=sig
    return True

def check_platform_change(scene,depsgraph=None):
    global _platform_watch_guard
    if _platform_watch_guard or not hasattr(scene,'seca_study'):return False
    _platform_watch_guard=True
    try:
        key=scene.as_pointer();current=platform_geometry_signature(scene,depsgraph)
        if key not in _platform_signature_cache:
            _platform_signature_cache[key]=current;return False
        previous=_platform_signature_cache[key]
        if not platform_signatures_differ(previous,current):return False
        _platform_signature_cache[key]=current;s=scene.seca_study
        if s.cal_valid or s.cal_stage not in {'IDLE','FAILED'}:
            invalidate_after_setup_change(scene);return True
        return False
    finally:_platform_watch_guard=False

def _watch_platform_depsgraph(scene,depsgraph):
    if _platform_watch_guard:return
    glass=scene.objects.get('654 • Bearclaw glass top')
    watched=[scene.objects.get(name) for name in HEAD_REFERENCE_OBJECTS+['CONTROL • head assembly (geometry edit only)']]
    if glass is None or any(obj is None for obj in watched):check_platform_change(scene,depsgraph);return
    for update in depsgraph.updates:
        original=getattr(update.id,'original',update.id)
        if original==glass or original==glass.data or original in watched:
            check_platform_change(scene,depsgraph);return
_watch_platform_depsgraph._seca_platform_watcher=True

def remove_platform_watchers():
    for handler in list(bpy.app.handlers.depsgraph_update_post):
        if getattr(handler,'_seca_platform_watcher',False):bpy.app.handlers.depsgraph_update_post.remove(handler)
    _platform_signature_cache.clear()

_transport_guard=False
_transport_pose_cache={}
TRANSPORT_RADIUS=.043
TRANSPORT_TRACK=.46

def transport_pose(scene,depsgraph=None):
    obj=scene.objects.get('CONTROL • transport pivot')
    if obj is None:return None
    if depsgraph is not None:obj=obj.evaluated_get(depsgraph)
    return tuple(obj.location)+tuple(obj.rotation_euler)

def transport_pose_differs(a,b):
    return a is None or b is None or len(a)!=6 or len(b)!=6 or any(abs(float(x)-float(y))>1e-6 for x,y in zip(a,b))

def remember_transport_pose(scene,depsgraph=None):
    pose=transport_pose(scene,depsgraph)
    if pose is not None:_transport_pose_cache[scene.as_pointer()]=pose
    return pose

def record_calibration_transport_pose(scene):
    pose=transport_pose(scene,bpy.context.evaluated_depsgraph_get())
    if pose is not None:scene['seca_calibration_transport_pose']=list(pose)

def transport_is_tilted(scene):
    pose=transport_pose(scene,bpy.context.evaluated_depsgraph_get())
    return abs(scene.seca_study.transport_angle)>1e-4 or (pose is not None and (abs(pose[3])>1e-4 or abs(pose[4])>1e-4))

def sync_generated_transport(scene,pose,depsgraph=None):
    # Only the known generator's bounded timeline has a recoverable mapping
    # from wheel angles back to the sidebar's cumulative travel controls.
    global _transport_guard
    control=scene.objects.get('CONTROL • transport pivot')
    if _transport_guard or not scene.get('transport_animation_scope') or control is None or not control.animation_data or not control.animation_data.action:return
    x,y,z,rx,ry,rz=pose
    if abs(z-.043)>1e-4 or abs(ry)>1e-4 or rx>1e-4 or -rx>math.radians(25)+1e-4 or abs(rz)>2*math.pi+1e-4:return
    wheels=[]
    for side in ('L','R'):
        obj=scene.objects.get('CONTROL • wheel '+side)
        if obj is None:return
        if depsgraph is not None:obj=obj.evaluated_get(depsgraph)
        wheels.append(obj.rotation_euler.x)
    angle=max(0.0,-rx);left=-(wheels[0]-angle)*TRANSPORT_RADIUS;right=-(wheels[1]-angle)*TRANSPORT_RADIUS;distance=(left+right)/2
    if abs(distance)>5.0001:return
    s=scene.seca_study;_transport_guard=True
    try:
        s.transport_x=x;s.transport_y=y-.267;s.transport_angle=angle;s.transport_yaw=rz
        s.wheel_l_distance=left;s.wheel_r_distance=right;s.transport_distance=distance
        s.previous_distance=distance;s.previous_yaw=rz
    finally:_transport_guard=False

def _seca_study_watch_transport_v29(scene,depsgraph=None):
    if not hasattr(scene,'seca_study'):return
    current=transport_pose(scene,depsgraph);previous=_transport_pose_cache.get(scene.as_pointer())
    if current is None:return
    _transport_pose_cache[scene.as_pointer()]=current
    sync_generated_transport(scene,current,depsgraph)
    if previous is None or not transport_pose_differs(previous,current):return
    s=scene.seca_study
    # Avoid repeated work during an already-invalidated animation, while still
    # invalidating a newly started calibration or current measurement.
    if s.cal_valid or s.cal_stage!='IDLE' or s.height_measuring or s.state in {'WEIGHED','RESULT','HELD'}:
        invalidate_after_setup_change(scene)
_seca_study_watch_transport_v29._seca_transport_watcher=True

def _seca_study_watch_transport_depsgraph_v29(scene,depsgraph):
    if _transport_guard:return
    pivot=scene.objects.get('CONTROL • transport pivot')
    if pivot is None:return
    for update in depsgraph.updates:
        original=getattr(update.id,'original',update.id)
        if original==pivot and update.is_updated_transform:
            _seca_study_watch_transport_v29(scene,depsgraph);return
_seca_study_watch_transport_depsgraph_v29._seca_transport_watcher=True

def remove_transport_watchers():
    for handlers in (bpy.app.handlers.frame_change_post,bpy.app.handlers.depsgraph_update_post):
        for handler in list(handlers):
            if getattr(handler,'_seca_transport_watcher',False):handlers.remove(handler)
    _transport_pose_cache.clear()

def integrate_transport(s):
    ds=s.transport_distance-s.previous_distance;turn=s.transport_yaw-s.previous_yaw;heading=s.previous_yaw
    if abs(turn)<1e-7:
        s.transport_x-=math.sin(heading)*ds;s.transport_y+=math.cos(heading)*ds
    else:
        s.transport_x+=(math.cos(heading+turn)-math.cos(heading))*ds/turn
        s.transport_y+=(math.sin(heading+turn)-math.sin(heading))*ds/turn
    s.wheel_l_distance+=ds-TRANSPORT_TRACK*turn/2
    s.wheel_r_distance+=ds+TRANSPORT_TRACK*turn/2
    s.previous_distance=s.transport_distance;s.previous_yaw=s.transport_yaw

def update_transport_pose(s,control):
    control.rotation_euler.x=-s.transport_angle;control.rotation_euler.z=s.transport_yaw
    control.location.x=s.transport_x;control.location.y=.267+s.transport_y
    for name,distance in (('CONTROL • wheel L',s.wheel_l_distance),('CONTROL • wheel R',s.wheel_r_distance)):
        obj=bpy.data.objects.get(name)
        if obj:obj.rotation_euler.x=-distance/TRANSPORT_RADIUS+s.transport_angle

def clearance_path_changed(self,context):
    scene=context.scene if context else None
    if not scene or not hasattr(scene,'seca_clearance'):return
    v=scene.seca_clearance
    if not v.report_json:return
    v.status='Not checked — path input changed';v.refinement_status='Not run';v.report_json='';scene.pop('seca_clearance_signature',None)
    for name in ('CLEARANCE • axle path','CLEARANCE • possible overlap marker','CLEARANCE • sampled part ghost'):
        obj=scene.objects.get(name)
        if obj:obj.hide_set(True);obj.hide_render=True

def drive_arc(scene):
    global _transport_guard
    s=scene.seca_study;control=bpy.data.objects.get('CONTROL • transport pivot')
    if not control:s.message='Transport control missing';refresh(scene);return
    if (scene.get('seca_level_active',False) or (hasattr(scene,'seca_level') and scene.seca_level.enabled)):
        s.message='Exit leveling before transport';refresh(scene);return
    if not s.drip_guard_removed or s.cal_rod_placed:
        s.message='Remove guard and study rod';refresh(scene);return
    if not s.disconnected or s.loaded or abs(s.transport_angle)<.0001:
        s.message='Unload, disconnect, tilt';refresh(scene);return
    distance=s.previous_distance+s.arc_distance;yaw=s.previous_yaw+s.arc_yaw
    if not(-5.000001<=distance<=5.000001 and -2*math.pi-1e-6<=yaw<=2*math.pi+1e-6):
        s.message='Transport control limit';refresh(scene);return
    distance=max(-5,min(5,distance));yaw=max(-2*math.pi,min(2*math.pi,yaw))
    _transport_guard=True
    try:
        before=transport_pose(scene)
        s.transport_distance=distance;s.transport_yaw=yaw;integrate_transport(s);update_transport_pose(s,control)
        after=remember_transport_pose(scene)
        if transport_pose_differs(before,after):
            invalidate_after_setup_change(scene);s.message='Arc applied; recalibrate study'
        else:s.message='Arc pose applied'
    finally:_transport_guard=False
    refresh(scene)

def apply_transport(scene):
    global _transport_guard
    if _transport_guard:return
    _transport_guard=True
    try:
        s=scene.seca_study;control=bpy.data.objects.get('CONTROL • transport pivot')
        if not control:return
        before=transport_pose(scene)
        if not s.disconnected and s.was_disconnected and transport_is_tilted(scene):
            s.disconnected=True;s.message='Lower before reconnecting';refresh(scene);return
        if s.disconnected:
            stop_audio()
            s.display_standby=False;s.idle_elapsed=0
            cancel_height(scene,'Power disconnected');
            if s.cal_stage!='IDLE':calibration_fail(scene,'Power disconnected');s.view_mode='MAIN';s.cal_stage='IDLE';sync_phantom(scene)
            clear_samples(scene);clear_held(s);clear_temporary_tares(s);s.state='READY';s.measured_height_cm=0;s.height_result_manual=False;s.view_mode='MAIN';advance_transfer(scene,0);s.message='Power disconnected'
        if not s.disconnected and s.was_disconnected and s.loaded:
            s.state='UNSTABLE';s.message='Load present; remeasure';clear_samples(scene)
        if not s.disconnected and s.was_disconnected and s.measurement_mode=='SELF':
            s.self_stage='SELECT';s.view_mode='SELF';s.message='Select measurement mode'
        if not s.disconnected and s.was_disconnected and s.fault_active=='NONE':
            if s.fault_scenario=='ZERO_MOTION' or (s.fault_scenario=='STARTUP_LOAD' and s.loaded):activate_fault(scene,s.fault_scenario)
        s.was_disconnected=s.disconnected
        if (scene.get('seca_level_active',False) or (hasattr(scene,'seca_level') and scene.seca_level.enabled)):
            if abs(s.transport_angle)>0.0001 or abs(s.transport_distance-s.previous_distance)>0.00001 or abs(s.transport_yaw-s.previous_yaw)>0.00001:
                s.transport_angle=0;s.transport_distance=s.previous_distance;s.transport_yaw=s.previous_yaw;s.message='Exit leveling before transport'
        # This is a deliberately kinematic teaching model, not a force solver.
        if (not s.disconnected or s.loaded or not s.drip_guard_removed or s.cal_rod_placed) and abs(s.transport_angle)>0.0001:
            s.transport_angle=0;s.message='Unload, remove guard and rod'
        if abs(s.transport_distance-s.previous_distance)>0.00001 or abs(s.transport_yaw-s.previous_yaw)>0.00001:
            if not s.disconnected or s.loaded or not s.drip_guard_removed or s.cal_rod_placed or abs(s.transport_angle)<0.0001:
                s.transport_distance=s.previous_distance;s.transport_yaw=s.previous_yaw;s.message='Unload, disconnect, tilt'
            else:integrate_transport(s)
        update_transport_pose(s,control)
        after=remember_transport_pose(scene)
        if transport_pose_differs(before,after):invalidate_after_setup_change(scene)
        refresh(scene)
    finally:_transport_guard=False

def update_drip_guard(self,context):
    if not context or not context.scene:return
    if not self.drip_guard_removed and abs(self.transport_angle)>0.0001:
        self.drip_guard_removed=True;self.message='Lower before installing guard';refresh(context.scene);return
    guard=bpy.data.objects.get('CONTROL • drip guard')
    if guard:guard.location.y=.10 if self.drip_guard_removed else 0.0
    if context.area:context.area.tag_redraw()

class SECA_PG_study(bpy.types.PropertyGroup):
    beeps_enabled: BoolProperty(name='Height beeps',default=True,update=audio_setting_changed)
    audio_volume: IntProperty(name='Study volume level',default=3,min=0,max=5,update=audio_setting_changed)
    audio_next_beep: FloatProperty(default=.5,min=0)
    audio_sequence: IntProperty(default=0,min=0)
    audio_events: StringProperty(default='[]')
    audio_status: StringProperty(default='No playback requested')
    voice_guidance_enabled: BoolProperty(name='Voice guidance',default=True,update=voice_settings_changed)
    voice_results_enabled: BoolProperty(name='Results announcements',default=True,update=voice_settings_changed)
    voice_language: EnumProperty(name='Voice language',items=[('EN','English','Only English is provided in this study')],default='EN')
    voice_pack_dir: StringProperty(name='Optional external voice pack',default='')
    voice_clothing_sent: BoolProperty(default=False)
    voice_guided_sent: BoolProperty(default=False)
    voice_events: StringProperty(default='[]')
    voice_sequence: IntProperty(default=0,min=0)
    voice_status: StringProperty(default='No announcement requested')
    standby_seconds: FloatProperty(name='Standby time (s; 0 = off)',description='Three minutes is documented default; other durations are study inputs',default=180,min=0,max=3600,update=standby_setting_changed)
    idle_elapsed: FloatProperty(default=0,min=0)
    display_standby: BoolProperty(default=False)
    fault_scenario: EnumProperty(name='Injected condition',items=[('NONE','None','No injected condition'),('STARTUP_LOAD','Startup load','Artificial startup load fault; threshold unverified'),('ZERO_MOTION','Zero-point motion','Artificial zero-point oscillation fault'),('CORNER','Corner overload','Artificial corner-load fault; threshold unverified'),('CELL','Load-cell fault','Artificial component fault')],default='NONE')
    fault_active: EnumProperty(items=[('NONE','None','')]+[(v,v.replace('_',' ').title(),'') for v in ('STARTUP_LOAD','ZERO_MOTION','CORNER','CELL')],default='NONE')
    fault_help: BoolProperty(default=False)
    fault_status: StringProperty(default='')
    gross_kg: FloatProperty(name='Gross load (kg)',default=70,min=0,max=500,precision=2,update=input_changed)
    dynamic_weight: BoolProperty(name='Timed weight model',default=True,update=input_changed)
    sensitivity: EnumProperty(name='Filter sensitivity',items=[('LOW','Low / faster',''),('MEDIUM','Medium',''),('HIGH','High / slower','')],default='LOW',update=input_changed)
    motion_kg: FloatProperty(name='Simulated motion (kg)',default=0,min=0,max=10,precision=2,update=input_changed)
    filtered_kg: FloatProperty(default=0)
    sample_time: FloatProperty(default=0,min=0)
    height_cm: FloatProperty(name='Synthetic height (cm)',default=170,min=50,max=240,precision=1,update=height_changed)
    height_gate_kg: FloatProperty(name='Assumed height load gate (kg)',description='Study-only manual height gate; not the documented voice trigger or a verified firmware threshold',default=.5,min=0,max=360,precision=2,update=source_changed)
    measurement_mode: EnumProperty(items=[('GUIDED','Guided',''),('SELF','Self-measurement','')],default='GUIDED')
    self_stage: EnumProperty(items=[(x,x.replace('_',' ').title(),'') for x in ('SELECT','READY','CLOTHING','ID','WEIGHT','HEIGHT_PREP','HEIGHT_RUNNING','HEIGHT_READ','RESULT','FINISHED')],default='READY')
    self_weight_only: BoolProperty(name='Weight only (self study)',default=False)
    self_weight_only_snapshot: BoolProperty(default=False)
    self_network_snapshot: BoolProperty(default=False)
    self_id: StringProperty(default='')
    height_source: EnumProperty(name='Height source',items=[('MANUAL','Numeric input',''),('GEOMETRY','Single-ray phantom',''),('ARRAY','Six-ray phantom study',''),('FAN','Adjustable echo fan study','')],default='MANUAL',update=source_changed)
    fan_half_angle_deg: FloatProperty(name='Fan half-angle (degrees)',default=4,min=0,max=20,update=fan_parameter_changed)
    fan_temperature_c: FloatProperty(name='Air temperature (C)',default=20,min=-10,max=40,update=fan_parameter_changed)
    fan_assumed_speed_mps: FloatProperty(name='Assumed sound speed (m/s)',default=343.42,min=300,max=380,update=fan_parameter_changed)
    fan_max_distance_m: FloatProperty(name='Maximum ray distance (m)',default=2.5,min=.1,max=5,update=fan_parameter_changed)
    fan_attenuation_per_m: FloatProperty(name='Attenuation estimate (per m)',default=.2,min=0,max=5,update=fan_parameter_changed)
    fan_threshold: FloatProperty(name='Echo threshold (study units)',default=.02,min=0,max=20,update=fan_parameter_changed)
    fan_summary: StringProperty(default='No fan sample')
    fan_trace_json: StringProperty(default='[]')
    cal_valid: BoolProperty(default=False)
    cal_stage: EnumProperty(items=[('IDLE','Idle',''),('INTRO','Introduction',''),('WAIT_EMPTY','Prepare empty scan',''),('EMPTY_SCAN','Empty scan',''),('WAIT_ROD','Place rod',''),('ROD_SCAN','Rod scan',''),('SUCCESS','Success',''),('REMOVE_ROD','Remove rod',''),('FAILED','Failed','')],default='IDLE')
    cal_area_clear: BoolProperty(name='Confirm study area clear',default=False,update=calibration_conditions_changed)
    cal_rod_placed: BoolProperty(name='Place study rod',default=False,update=lambda self,ctx:calibration_rod_changed(self,ctx,False))
    cal_rod_x: FloatProperty(name='Rod X (m)',default=0,min=-.25,max=.25,update=lambda self,ctx:calibration_rod_changed(self,ctx,True))
    cal_rod_y: FloatProperty(name='Rod Y (m)',default=-.075,min=-.2,max=.2,update=lambda self,ctx:calibration_rod_changed(self,ctx,True))
    cal_duration: FloatProperty(name='Stage duration (s)',default=1.5,min=.1,max=30)
    cal_duration_snapshot: FloatProperty(default=1.5,min=.1,max=30)
    cal_elapsed: FloatProperty(default=0,min=0)
    timed_height: BoolProperty(name='Timed height study',default=True)
    height_duration: FloatProperty(name='Study duration (s)',default=2,min=.1,max=30)
    height_duration_snapshot: FloatProperty(default=2,min=.1,max=30)
    height_measuring: BoolProperty(default=False)
    height_elapsed: FloatProperty(default=0,min=0)
    array_min_pairs: IntProperty(name='Minimum valid pairs',default=3,min=1,max=3,update=source_changed)
    array_valid_pairs: IntProperty(default=0,min=0,max=3)
    array_spread_cm: FloatProperty(default=0,min=0)
    array_detail_json: StringProperty(default='')
    array_snapshot_json: StringProperty(default='')
    geometry_snapshot_cm: FloatProperty(default=0)
    height_result_manual: BoolProperty(default=False)
    manual_height_draft: StringProperty(default='0')
    manual_height_status: StringProperty(default='')
    manual_height_units: EnumProperty(items=[('CM','cm',''),('IMPERIAL','inches (study)','')],default='CM')
    measured_height_cm: FloatProperty(default=0)
    preview_height_cm: FloatProperty(default=170,min=100,max=220)
    view_mode: EnumProperty(items=[('MAIN','Main',''),('MANUAL_HEIGHT','Manual height',''),('HEIGHT','Height review',''),('MEASURING','Measuring',''),('CALIBRATION','Calibration study',''),('RECALL','Recall',''),('TARE_MENU','Tare assistant',''),('TARE_EDIT','Clothing tare',''),('MOTHER','Mother child',''),('MESSAGE','Study message',''),('OVERVIEW','Overview',''),('SETTINGS','Settings',''),('SELF','Self study',''),('FAULT','Fault study','')],default='MAIN')
    menu_page: EnumProperty(items=[(v,v.title().replace('_',' '),'') for v in ('ROOT','DISPLAY','DISPLAY_MORE','NAME_FORMAT','DATE_FORMAT','BODY_OPTIONS','WEIGHT','PRETARE','PRETARE_EDIT','UNITS','AUTOHOLD','SENSITIVITY','CLEAR_VALUES','TIMEOUT','STANDBY','BRIGHTNESS','AUDIO','AUDIO_BEEPS','AUDIO_VOLUME','AUDIO_LANGUAGE','NETWORK','NET_IDENTIFICATION','NET_CLEAR_DATA')],default='ROOT')
    show_demo_identity: BoolProperty(name='Show fictional identity example',description='Displays a fixed fictional name and date only; never a verified identity',default=False,update=lambda self,ctx:refresh(ctx.scene))
    name_format: EnumProperty(items=[(v,v.replace('_',' ').title(),'') for v in ('GIVEN_FAMILY','GIVEN_COMMA_FAMILY','FAMILY_GIVEN','FAMILY_COMMA_GIVEN')],default='GIVEN_FAMILY')
    date_format: EnumProperty(items=[(v,v.replace('_',' '),'') for v in ('YMD_DOT','DMY_DOT','MDY_DOT','YMD_SLASH','DMY_SLASH','MDY_SLASH')],default='YMD_SLASH')
    display_brightness: IntProperty(name='Display brightness stage',description='Relative study levels; physical luminance is unmeasured',default=4,min=1,max=5,update=display_brightness_changed)
    brightness_draft: IntProperty(default=4,min=1,max=5)
    volume_draft: IntProperty(default=3,min=0,max=5)
    menu_timeout_draft: IntProperty(default=30,min=1,max=3600)
    tare_kg: FloatProperty(name='Tare (kg)',default=0,min=0,max=360)
    pre_tare_kg: FloatProperty(default=0,min=0,max=360)
    pre_tare_input: FloatProperty(name='Pre-tare setting (kg)',default=0,min=0,max=360,precision=2)
    pre_tare_draft: StringProperty(default='0')
    pre_tare_edit_units: EnumProperty(items=[('KG','kg',''),('LB','lb','')],default='KG')
    pre_tare_replace_next: BoolProperty(default=True)
    pre_tare_edit_status: StringProperty(default='')
    preset_suppressed: BoolProperty(default=False)
    clothing_active: BoolProperty(default=False)
    clothing_kg: FloatProperty(default=0,min=0,max=360)
    clothing_draft_kg: FloatProperty(default=0,min=0,max=360)
    additional_kg: FloatProperty(default=0,min=0,max=360)
    scanned_kg: FloatProperty(default=0,min=0,max=360)
    scan_input_kg: FloatProperty(name='Synthetic scan (kg)',default=0,min=0,max=360,precision=2)
    adult_kg: FloatProperty(default=0,min=0,max=360)
    mother_stage: EnumProperty(items=[('NONE','Inactive',''),('INTRO','Introduction',''),('WAIT_ADULT','Waiting for adult',''),('ADULT_READY','Adult ready',''),('WAIT_CHILD','Waiting for child',''),('CHILD_READY','Child ready',''),('DONE','Accepted','')],default='NONE')
    last_kg: FloatProperty(default=0)
    last_net_kg: FloatProperty(default=0)
    last_height_cm: FloatProperty(default=0)
    has_last: BoolProperty(default=False)
    weight_units: EnumProperty(name='Weight units',items=[('KG','kg',''),('LB','lb','')],default='KG',update=lambda self,ctx:refresh(ctx.scene))
    height_units: EnumProperty(name='Height units',items=[('CM','cm',''),('IMPERIAL','ft/in','')],default='CM',update=height_units_changed)
    indicator: EnumProperty(name='Body size',items=[('OFF','Off',''),('BMI','BMI',''),('MOSTELLER','BSA Mosteller',''),('DUBOIS','BSA Du Bois',''),('HAYCOCK','BSA Haycock','')],default='BMI',update=lambda self,ctx:refresh(ctx.scene))
    loaded: BoolProperty(default=False)
    state: EnumProperty(items=[('READY','Ready',''),('UNSTABLE','Unstable',''),('WEIGHED','Weighed',''),('RESULT','Result',''),('HELD','Held',''),('OVERLOAD','Overload',''),('FAULT','Fault','')],default='READY')
    setup_remeasure_required: BoolProperty(default=False)
    autohold: BoolProperty(name='Auto-HOLD',default=False,update=retention_changed)
    clear_policy: EnumProperty(name='Clear values',items=[('RELOAD','On reload',''),('UNLOAD','On unload',''),('TIMEOUT','After timeout','')],default='RELOAD',update=retention_changed)
    clear_timeout: FloatProperty(name='Clear after (seconds)',default=30,min=1,max=3600,update=retention_changed)
    manual_hold: BoolProperty(default=False)
    held_valid: BoolProperty(default=False)
    held_net_kg: FloatProperty(default=0)
    held_height_cm: FloatProperty(default=0)
    held_tare_kg: FloatProperty(default=0)
    held_elapsed: FloatProperty(default=0,min=0)
    message: StringProperty(default='Scale ready')
    message_page: IntProperty(default=0,min=0)
    net_clear_seconds: IntProperty(name='Mock clear data (seconds)',default=300,min=10,max=3600)
    net_clear_elapsed: FloatProperty(default=0,min=0,max=3600)
    net_clear_armed: BoolProperty(default=False)
    net_data_expired: BoolProperty(default=False)
    net_clear_busy: BoolProperty(default=False)
    net_clear_draft: StringProperty(default='300')
    net_clear_replace: BoolProperty(default=True)
    net_clear_overflow: BoolProperty(default=False)
    net_clear_status: StringProperty(default='')
    mock_network: BoolProperty(name='Mock network',default=False,update=retention_changed)
    mock_transport: EnumProperty(name='Study connection',items=[('LAN','LAN','Local simulated wired connection'),('WIFI','Wi-Fi','Local simulated wireless connection')],default='LAN',update=retention_changed)
    mock_lan_state: EnumProperty(name='LAN status',items=[('CONNECTED','Connected',''),('UNPLUGGED','Unavailable',''),('DISABLED','Disabled','')],default='CONNECTED',update=retention_changed)
    mock_wifi_signal: EnumProperty(name='Wi-Fi signal',items=[('DISABLED','Unavailable',''),('NO_SIGNAL','No signal',''),('VERY_WEAK','Very weak',''),('WEAK','Weak',''),('GOOD','Good',''),('OPTIMAL','Optimal','')],default='GOOD',update=retention_changed)
    mock_wifi_associated: BoolProperty(name='Associated (study)',default=True,update=retention_changed)
    scanner_attached: BoolProperty(name='Mock scanner attached',default=False)
    scan_fixture_target: EnumProperty(name='Scan as',items=[('PATIENT','Patient ID',''),('USER','User ID','')],default='PATIENT')
    scan_fixture: StringProperty(name='Fictional scan',default='TEST-PATIENT')
    synthetic_id: StringProperty(name='Synthetic patient ID',default='TEST-001',update=patient_id_changed)
    synthetic_user_id: StringProperty(name='Synthetic user ID',default='DEMO-USER',update=lambda self,ctx:refresh(ctx.scene))
    transfer_state: EnumProperty(items=[('IDLE','Idle',''),('PENDING','Pending',''),('RETRY_WAIT','Waiting to retry',''),('ACKNOWLEDGED','Acknowledged',''),('FAILED','Failed','')],default='IDLE')
    transfer_payload: StringProperty(default='')
    receiver_records: StringProperty(default='{}')
    transfer_serial: IntProperty(default=0,min=0)
    transfer_attempts: IntProperty(default=0,min=0)
    transfer_remaining: IntProperty(default=0,min=0)
    transfer_error: StringProperty(default='')
    transfer_elapsed: FloatProperty(default=0,min=0)
    transfer_failure_mode: EnumProperty(name='Simulated failure',items=[('NONE','None',''),('REJECT','Receiver unavailable',''),('ACK_LOST','Acknowledgement lost','')],default='NONE')
    transfer_failures: IntProperty(name='Failures before success',default=0,min=0,max=10)
    transfer_max_attempts: IntProperty(name='Maximum attempts',default=3,min=1,max=10)
    transfer_latency: FloatProperty(name='Receiver delay (s)',default=1,min=.05,max=30)
    transfer_mode_snapshot: StringProperty(default='NONE')
    transfer_max_snapshot: IntProperty(default=3,min=1)
    transfer_latency_snapshot: FloatProperty(default=1,min=.05)
    drip_guard_removed: BoolProperty(name='Remove drip guard',default=False,update=update_drip_guard)
    disconnected: BoolProperty(name='Cables disconnected',default=False,update=lambda self,ctx:apply_transport(ctx.scene))
    was_disconnected: BoolProperty(default=False)
    transport_angle: FloatProperty(name='Tilt (proposed)',subtype='ANGLE',default=0,min=0,max=math.radians(25),update=lambda self,ctx:apply_transport(ctx.scene))
    transport_distance: FloatProperty(name='Travel (m)',default=0,min=-5,max=5,update=lambda self,ctx:apply_transport(ctx.scene))
    previous_distance: FloatProperty(default=0)
    transport_yaw: FloatProperty(name='Heading',subtype='ANGLE',default=0,min=-2*math.pi,max=2*math.pi,update=lambda self,ctx:apply_transport(ctx.scene))
    previous_yaw: FloatProperty(default=0)
    transport_x: FloatProperty(default=0)
    transport_y: FloatProperty(default=0)
    wheel_l_distance: FloatProperty(default=0)
    wheel_r_distance: FloatProperty(default=0)
    arc_distance: FloatProperty(name='Arc travel (m)',default=.5,min=-5,max=5,update=clearance_path_changed)
    arc_yaw: FloatProperty(name='Arc turn',subtype='ANGLE',default=0,min=-2*math.pi,max=2*math.pi,update=clearance_path_changed)

class SECA_OT_action(bpy.types.Operator):
    bl_idname='seca_study.action';bl_label='Simulate action';bl_options={'REGISTER','UNDO'}
    action: StringProperty()
    def execute(self,context):do_action(context.scene,self.action);return {'FINISHED'}

# Picking and feedback derive from the geometry of the displayed button tiles.
# These tiles are a provisional study layout, not verified seca firmware.
TOUCH_REGIONS={
 'FAULT':[('FAULT_RESTART','FAULT • restart region'),('FAULT_HELP','FAULT • help region')],
 'SELF':[('SELF_BACK','SELF • secondary region'),('SELF_NEXT','SELF • primary region')],
 'CALIBRATION':[('CAL_CANCEL','CAL • cancel region'),('CAL_NEXT','CAL • next region')],
 'MAIN':[('MENU_OPEN','SIM • settings region'),('LOGOUT_IDS','SIM • identity logout region'),('TARE_MENU','SIM • tare region'),('RECALL','SIM • recall region'),('CONFIRM','SIM • confirm tile'),('OPEN_MESSAGE','SIM • message region'),('CLEAR_TARE','SIM • tare clear region'),('REPEAT','SIM • weight repeat region'),('HEIGHT_REPEAT_MAIN','SIM • height repeat region'),('HEIGHT','SIM • height start region'),('BODY_CYCLE','SIM • body size region'),('HEIGHT_FIELD','SIM • height region')],
 'MANUAL_HEIGHT':[('HEIGHT_MANUAL_CANCEL','MANUALH • back region'),('HEIGHT_MANUAL_APPLY','MANUALH • accept region'),('HEIGHT_MANUAL_DOT','MANUALH • decimal region'),('HEIGHT_MANUAL_DELETE','MANUALH • delete region')]+[(f'HEIGHT_MANUAL_DIGIT_{i}',f'MANUALH • digit {i} region') for i in range(10)],
 'HEIGHT':[('HEIGHT_CANCEL','REVIEW • back region'),('HEIGHT_MINUS','REVIEW • minus region'),('HEIGHT_PLUS','REVIEW • plus region'),('HEIGHT_REPEAT','REVIEW • cancel region'),('HEIGHT_ACCEPT','REVIEW • accept region')],
 'TARE_MENU':[('MOTHER_START','TAREMENU • mother button'),('CLOTHING_START','TAREMENU • clothing button'),('TARE_ADDITIONAL','TAREMENU • additional button'),('TARE_CANCEL','TAREMENU • back region')],
 'MOTHER':[('MOTHER_CANCEL','MOTHER • back region'),('MOTHER_REPEAT','MOTHER • repeat region'),('MOTHER_ADVANCE','MOTHER • action region')],
 'TARE_EDIT':[('CLOTHING_MINUS','TAREEDIT • minus region'),('CLOTHING_PLUS','TAREEDIT • plus region'),('TARE_CANCEL','TAREEDIT • cancel region'),('CLOTHING_ACCEPT','TAREEDIT • accept region')],
 'RECALL':[('RECALL_CLOSE','RECALL • close region')],
 'SETTINGS':[('NETDATA_CLEAR','CLEARDATA • clear region'),('NETDATA_DELETE','CLEARDATA • delete region'),('NETDATA_ACCEPT','CLEARDATA • accept region')]+[(f'NETDATA_DIGIT_{i}',f'CLEARDATA • digit {i} region') for i in range(10)]+[('MENU_BACK','SECMENU • back region'),('MENU_HOME','SECMENU • home region'),('MENU_PAGE_PREVIOUS','PAGING • previous region'),('MENU_PAGE_NEXT','PAGING • next region'),('PRETARE_OPEN','PRETARE • edit region'),('PRETARE_CLEAR','PRETAREKEY • clear region'),('PRETARE_DECIMAL','PRETAREKEY • decimal region'),('PRETARE_DELETE','PRETAREKEY • delete region'),('PRETARE_ACCEPT','PRETAREKEY • accept region')]+[(f'PRETARE_DIGIT_{i}',f'PRETAREKEY • digit {i} region') for i in range(10)]+[('BRIGHTNESS_MINUS','BRIGHT • minus region'),('BRIGHTNESS_PLUS','BRIGHT • plus region'),('BRIGHTNESS_ACCEPT','BRIGHT • accept region'),('AUDIO_LEVEL_MINUS','BRIGHT • minus region'),('AUDIO_LEVEL_PLUS','BRIGHT • plus region'),('AUDIO_LEVEL_ACCEPT','BRIGHT • accept region')]+[(f'MENU_ROW_{i}',f'SECMENU • row {i}') for i in range(1,8)],
 'OVERVIEW':[('OVERVIEW_CLOSE','OVERVIEW • close region'),('OVERVIEW_SEND','OVERVIEW • send region')],
 'MESSAGE':[('MESSAGE_PREVIOUS','MSG • previous region'),('CLOSE_MESSAGE','MSG • close region'),('MESSAGE_NEXT','MSG • next region')],
}

def region_bounds(name):
    screen=bpy.data.objects.get('ID display active image');obj=bpy.data.objects.get(name)
    if not screen or not obj:return None
    relative=screen.matrix_world.inverted()@obj.matrix_world
    pts=[relative@Vector(corner) for corner in obj.bound_box]
    return min(p.x for p in pts),max(p.x for p in pts),min(p.z for p in pts),max(p.z for p in pts)

def region_at(view,x,z):
    screen=bpy.data.objects.get('ID display active image')
    if not screen:return None
    point=screen.matrix_world@Vector((x,-.002,z))
    for action,name in TOUCH_REGIONS.get(view,[]):
        obj=bpy.data.objects.get(name)
        if not obj:continue
        if view=='SETTINGS' and action.startswith('MENU_PAGE_') and bpy.context.scene.seca_study.menu_page not in {'DISPLAY','DISPLAY_MORE'}:continue
        if view=='SETTINGS' and action.startswith('NETDATA_') and bpy.context.scene.seca_study.menu_page!='NET_CLEAR_DATA':continue
        if view=='SETTINGS' and action.startswith('PRETARE_') and ((action=='PRETARE_OPEN' and bpy.context.scene.seca_study.menu_page!='PRETARE') or (action!='PRETARE_OPEN' and bpy.context.scene.seca_study.menu_page!='PRETARE_EDIT')):continue
        if action=='BODY_CYCLE' and (obj.hide_get() or obj.hide_render):continue
        if view=='MOTHER' and (obj.hide_get() or obj.hide_render):continue
        if view=='SETTINGS' and ((action.startswith('BRIGHTNESS_') and bpy.context.scene.seca_study.menu_page!='BRIGHTNESS') or (action.startswith('AUDIO_LEVEL_') and bpy.context.scene.seca_study.menu_page!='AUDIO_VOLUME') or (action.startswith('MENU_ROW_') and bpy.context.scene.seca_study.menu_page in {'BRIGHTNESS','AUDIO_VOLUME','PRETARE','PRETARE_EDIT','NET_CLEAR_DATA'})):continue
        if name in {'SIM • weight repeat region','SIM • height repeat region','SIM • height start region','SIM • tare clear region'} and (obj.hide_get() or obj.hide_render):continue
        p=obj.matrix_world.inverted()@point
        xmin=min(c[0] for c in obj.bound_box);xmax=max(c[0] for c in obj.bound_box)
        zmin=min(c[2] for c in obj.bound_box);zmax=max(c[2] for c in obj.bound_box)
        if xmin<=p.x<xmax and zmin<=p.z<=zmax:return action
    return None

def action_at_ray(scene,origin,direction):
    screen=bpy.data.objects.get('ID display active image')
    if not screen or scene.seca_study.disconnected:return None
    inv=screen.matrix_world.inverted();local_origin=inv@origin;local_dir=inv.to_3x3()@direction
    if local_dir.y<=1e-7:return None
    t=(-.002-local_origin.y)/local_dir.y
    if t<0:return None
    p=local_origin+t*local_dir
    if scene.seca_study.display_standby:
        xs=[c[0] for c in screen.bound_box];zs=[c[2] for c in screen.bound_box]
        action='WAKE' if min(xs)<=p.x<=max(xs) and min(zs)<=p.z<=max(zs) else None
    else:action=region_at(scene.seca_study.view_mode,p.x,p.z)
    if not action:return None
    hit,point,normal,index,obj,matrix=scene.ray_cast(bpy.context.evaluated_depsgraph_get(),origin,direction)
    if not hit:return None
    while obj and obj!=screen:obj=obj.parent
    return action if obj==screen else None

def touch_enabled(scene,action):
    s=scene.seca_study
    if action in {'HEIGHT','HEIGHT_REPEAT','HEIGHT_ACCEPT','HEIGHT_FIELD','HEIGHT_REPEAT_MAIN','CONFIRM','OVERVIEW_SEND','HOLD','MOTHER_ADVANCE','MOTHER_NEXT','MOTHER_ACCEPT','SELF_NEXT'} and sampling_window_missing(scene):return False
    if s.disconnected:return False
    if s.display_standby:return action=='WAKE'
    if action=='WAKE':return False
    if action=='REPEAT':return main_measurement_ready(s)
    if action=='HEIGHT':return main_measurement_ready(s) and s.state=='WEIGHED'
    if action in {'HEIGHT_FIELD','HEIGHT_REPEAT_MAIN'}:return main_measurement_ready(s) and s.state=='RESULT'
    if action.startswith('HEIGHT_MANUAL_'):return s.view_mode=='MANUAL_HEIGHT' and s.loaded and s.state=='RESULT' and s.height_units==s.manual_height_units
    if action=='SELF_NEXT':return self_next_enabled(s)
    if action=='SELF_BACK':return s.self_stage in {'SELECT','ID','WEIGHT','HEIGHT_READ'}
    if action=='OPEN_MESSAGE':
        o=bpy.data.objects.get('SIM • message')
        return bool(s.message and o and not o.hide_get())
    if action=='LOGOUT_IDS':return s.mock_network and s.view_mode=='MAIN'
    if action.startswith('NETDATA_'):return s.view_mode=='SETTINGS' and s.menu_page=='NET_CLEAR_DATA'
    if action.startswith('PRETARE_'):return s.view_mode=='SETTINGS' and not s.loaded and ((action=='PRETARE_OPEN' and s.menu_page=='PRETARE') or (action!='PRETARE_OPEN' and s.menu_page=='PRETARE_EDIT'))
    if action=='CLEAR_TARE':return s.view_mode=='MAIN' and (s.held_tare_kg if s.state=='HELD' else s.tare_kg)>0
    if action=='MOTHER_ADVANCE':return s.view_mode=='MOTHER' and (s.mother_stage=='INTRO' and not s.loaded or s.mother_stage in {'ADULT_READY','CHILD_READY'} and s.loaded and s.state=='WEIGHED')
    if action=='MOTHER_REPEAT':return s.view_mode=='MOTHER' and s.mother_stage in {'ADULT_READY','CHILD_READY'} and s.loaded and s.state=='WEIGHED'
    if action=='MOTHER_CANCEL':return s.view_mode=='MOTHER'
    if action=='BODY_CYCLE':return body_size_available(s)
    if action=='MENU_PAGE_PREVIOUS':return s.view_mode=='SETTINGS' and s.menu_page=='DISPLAY_MORE'
    if action=='MENU_PAGE_NEXT':return s.view_mode=='SETTINGS' and s.menu_page=='DISPLAY'
    if action.startswith('BRIGHTNESS_'):
        return s.view_mode=='SETTINGS' and s.menu_page=='BRIGHTNESS' and (action!='BRIGHTNESS_MINUS' or s.brightness_draft>1) and (action!='BRIGHTNESS_PLUS' or s.brightness_draft<5)
    if action.startswith('AUDIO_LEVEL_'):
        return s.view_mode=='SETTINGS' and s.menu_page=='AUDIO_VOLUME' and (action!='AUDIO_LEVEL_MINUS' or s.volume_draft>0) and (action!='AUDIO_LEVEL_PLUS' or s.volume_draft<5)
    if action.startswith('MENU_ROW_'):
        idx=int(action.rsplit('_',1)[1])-1;items=menu_spec(s)[1]
        return s.view_mode=='SETTINGS' and 0<=idx<len(items) and items[idx][3]
    if action=='CAL_NEXT' and s.cal_stage in {'EMPTY_SCAN','WAIT_ROD','ROD_SCAN'}:return False
    if action=='MESSAGE_PREVIOUS':return s.message_page>0
    if action=='MESSAGE_NEXT':return s.message_page+1<len(layout_message(s.message)[1])
    return True

def touch_feedback(scene,view,action):
    o=bpy.data.objects.get('TOUCH • pressed feedback')
    if not o:return
    target=next((name for act,name in TOUCH_REGIONS.get(view,[]) if act==action),None)
    region=region_bounds(target) if target else None
    if not region:
        o.hide_set(True);o.hide_render=True;return
    tile=bpy.data.objects[target];screen=bpy.data.objects['ID display active image']
    xmin=min(c[0] for c in tile.bound_box);xmax=max(c[0] for c in tile.bound_box)
    zmin=min(c[2] for c in tile.bound_box);zmax=max(c[2] for c in tile.bound_box)
    center=Vector(((xmin+xmax)/2,0,(zmin+zmax)/2))
    center_screen=screen.matrix_world.inverted()@tile.matrix_world@center
    target_world=screen.matrix_world@Vector((center_screen.x,-.00225,center_screen.z))
    local_target=tile.matrix_world.inverted()@target_world
    o.parent=tile;o.matrix_parent_inverse.identity();o.rotation_euler=(0,0,0)
    o.location=(center.x,local_target.y,center.z);o.scale.x=xmax-xmin;o.scale.z=zmax-zmin
    o['touch_view']=view;o.hide_set(False);o.hide_render=False

class TouchGesture:
    def __init__(self):self.tracking=False;self.action=None;self.view=None
    def begin(self,scene,action):
        self.cancel(scene)
        if not action:return False
        if not scene.seca_study.display_standby:scene.seca_study.idle_elapsed=0
        self.tracking=True
        if touch_enabled(scene,action):
            self.action=action;self.view=scene.seca_study.view_mode;touch_feedback(scene,self.view,action)
        return True
    def move(self,scene,action):
        if self.tracking and self.action and (action!=self.action or scene.seca_study.view_mode!=self.view or not touch_enabled(scene,self.action)):
            self.action=None;touch_feedback(scene,None,None)
    def release(self,scene,action):
        if not self.tracking:return False
        valid=self.action and self.action==action and self.view==scene.seca_study.view_mode and touch_enabled(scene,self.action)
        dispatch=self.action if valid else None
        self.cancel(scene)
        if dispatch:do_action(scene,dispatch)
        return True
    def cancel(self,scene):
        self.tracking=False;self.action=None;self.view=None;touch_feedback(scene,None,None)

class SECA_OT_fixture_scan(bpy.types.Operator):
    """Insert a fictional value; no hardware scanner is accessed."""
    bl_idname='seca_study.fixture_scan';bl_label='Insert fictional scan'
    def execute(self,context):insert_fixture_scan(context.scene);return {'FINISHED'}

class SECA_OT_touch(bpy.types.Operator):
    """Press and release on a control; drag away cancels; Esc exits study touch."""
    bl_idname='seca_study.touch';bl_label='Enable 3D screen touch';bl_options={'REGISTER'}
    def invoke(self,context,event):
        if not context.area or context.area.type!='VIEW_3D':self.report({'WARNING'},'Use from the 3D View sidebar');return {'CANCELLED'}
        self._gesture=TouchGesture();context.window_manager.modal_handler_add(self);self.report({'INFO'},'Press and release screen; Esc ends touch mode');return {'RUNNING_MODAL'}
    def hit(self,context,event):
        area=context.area;screen=bpy.data.objects.get('ID display active image')
        if not area or area.type!='VIEW_3D' or not screen:return None
        region=next((r for r in area.regions if r.type=='WINDOW'),None)
        rv=area.spaces.active.region_3d
        if not region or not rv:return None
        xy=(event.mouse_x-region.x,event.mouse_y-region.y)
        if not(0<=xy[0]<region.width and 0<=xy[1]<region.height):return None
        direction=view3d_utils.region_2d_to_vector_3d(region,rv,xy)
        if rv.is_perspective:
            origin=view3d_utils.region_2d_to_origin_3d(region,rv,xy)
        else:
            # For an orthographic viewport, begin at the view plane rather
            # than an arbitrary point 10 m behind it.  A far origin can place
            # the studio floor in front of a nearby, visibly unobscured screen.
            reference=view3d_utils.region_2d_to_location_3d(region,rv,xy,screen.matrix_world.translation)
            camera=area.spaces.active.camera or context.scene.camera
            if rv.view_perspective=='CAMERA' and camera:
                depth=(reference-camera.matrix_world.translation).dot(direction)
            else:
                depth=rv.view_distance+(reference-rv.view_location).dot(direction)
            if depth<=1e-6:return None
            origin=reference-direction*depth
        return action_at_ray(context.scene,origin,direction)
    def modal(self,context,event):
        g=self._gesture
        if event.type in {'ESC','RIGHTMOUSE','WINDOW_DEACTIVATE'}:
            g.cancel(context.scene)
            if context.area:context.area.tag_redraw()
            return {'PASS_THROUGH'} if event.type=='WINDOW_DEACTIVATE' else {'FINISHED'}
        if event.type=='LEFTMOUSE' and event.value=='PRESS':
            if not g.begin(context.scene,self.hit(context,event)):return {'PASS_THROUGH'}
        elif event.type=='MOUSEMOVE' and g.tracking:g.move(context.scene,self.hit(context,event))
        elif event.type=='LEFTMOUSE' and event.value=='RELEASE':
            if not g.release(context.scene,self.hit(context,event)):return {'PASS_THROUGH'}
        else:return {'PASS_THROUGH'}
        if context.area:context.area.tag_redraw()
        return {'RUNNING_MODAL'}


class SECA_PT_panel(bpy.types.Panel):
    bl_label='seca study — simulated';bl_idname='SECA_PT_study';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='seca study'
    def draw(self,context):
        l=self.layout;s=context.scene.seca_study
        l.label(text='Synthetic values; not medical use',icon='INFO')
        box=l.box();box.label(text='Synthesized audio study — not seca recordings')
        box.prop(s,'beeps_enabled');box.prop(s,'audio_volume');box.label(text=s.audio_status);box.prop(s,'voice_guidance_enabled');box.prop(s,'voice_results_enabled');box.prop(s,'voice_language');box.prop(s,'voice_pack_dir');box.label(text='Voice study: '+s.voice_status)
        box=l.box();box.label(text='Display standby study')
        box.prop(s,'standby_seconds');box.label(text='Display: '+('standby' if s.display_standby else 'active'))
        if s.display_standby:box.operator('seca_study.action',text='Wake display').action='WAKE'
        box=l.box();box.label(text='Injected fault study — no sensor diagnosis')
        box.prop(s,'fault_scenario');row=box.row(align=True);row.operator('seca_study.action',text='Inject corner / cell').action='FAULT_INJECT';row.operator('seca_study.action',text='Simulate restart').action='FAULT_RESTART'
        if s.fault_active!='NONE':box.label(text='Latched: '+s.fault_active);box.operator('seca_study.action',text='Step off').action='STEP_OFF'
        box=l.box();box.label(text='Measurement mode study: '+s.measurement_mode)
        box.operator('seca_study.action',text='Restart to select mode').action='MODE_RESTART'
        if s.self_stage=='SELECT' and s.view_mode=='SELF':
            row=box.row(align=True);row.operator('seca_study.action',text='Guided').action='SELF_BACK';row.operator('seca_study.action',text='Self-measurement').action='SELF_NEXT'
        elif s.measurement_mode=='SELF':
            box.prop(s,'self_weight_only');box.label(text='Stage: '+s.self_stage)
            if s.self_stage=='ID':box.prop(s,'synthetic_id')
            row=box.row(align=True);row.operator('seca_study.action',text='Back / alternate').action='SELF_BACK';row.operator('seca_study.action',text='Continue').action='SELF_NEXT'
        l.prop(s,'gross_kg');l.prop(s,'height_source');l.prop(s,'height_cm');l.prop(s,'dynamic_weight')
        datum=platform_surface_z(context.scene,0,.070)
        l.label(text='Modeled glass datum: '+(f'{datum*1000:.1f} mm' if datum is not None else 'unavailable'))
        l.label(text='Published 70 mm; floor datum unverified')
        box=l.box();box.label(text='654 load references — simulated gross input')
        status=load_reference_status(s)
        labels={'NO_LOAD':'No powered, loaded input','OVER_CAPACITY':'Above 360 kg capacity','BELOW_MINIMUM':'Below 1 kg minimum capacity','IN_RANGE':'Within 1–360 kg gross range'}
        box.label(text=labels[status]);box.label(text='0.5 kg voice reference: '+('reached' if voice_reference_reached(s) else 'not reached'))
        box.label(text='Voice trigger and timing are study estimates')
        box.prop(s,'height_gate_kg');box.label(text='Height gate is a separate study assumption')
        if s.height_source in {'GEOMETRY','ARRAY','FAN'}:l.operator('seca_study.action',text='Align phantom to modeled glass').action='PHANTOM_SNAP'
        if s.height_source=='GEOMETRY':l.label(text='Single ray approximation, not ultrasound')
        if s.height_source=='ARRAY':
            l.label(text='Six narrow rays; not acoustic simulation');l.prop(s,'array_min_pairs');l.label(text=f'Valid pairs: {s.array_valid_pairs}/3; spread {s.array_spread_cm:.2f} cm')
        if s.height_source=='FAN':
            box=l.box();box.label(text='Uncalibrated geometric echo fan')
            for prop in ('fan_half_angle_deg','fan_temperature_c','fan_assumed_speed_mps','fan_max_distance_m','fan_attenuation_per_m','fan_threshold','array_min_pairs'):box.prop(s,prop)
            box.label(text=s.fan_summary);box.label(text='Reflectivity is an object study property')
            box.operator('seca_study.action',text='Sample echo fan').action='FAN_SAMPLE'
        box=l.box();box.label(text='Calibration study — not device calibration')
        box.label(text='Simulated validity: '+('complete' if s.cal_valid else 'not complete'))
        box.prop(s,'cal_area_clear');box.prop(s,'cal_duration');box.prop(s,'cal_rod_placed')
        if s.cal_rod_placed:box.prop(s,'cal_rod_x');box.prop(s,'cal_rod_y')
        if s.cal_stage=='IDLE':box.operator('seca_study.action',text='Start calibration study').action='CAL_START'
        else:
            box.label(text='Stage: '+s.cal_stage);row=box.row(align=True);row.operator('seca_study.action',text='Continue').action='CAL_NEXT';row.operator('seca_study.action',text='Cancel').action='CAL_CANCEL'
        l.prop(s,'timed_height')
        if s.timed_height:l.prop(s,'height_duration')
        if s.height_measuring:l.operator('seca_study.action',text='Cancel height study').action='HEIGHT_CANCEL'
        if s.dynamic_weight:l.prop(s,'sensitivity');l.prop(s,'motion_kg')
        row=l.row(align=True);row.prop(s,'weight_units');row.prop(s,'height_units');l.prop(s,'indicator')
        row=l.row(align=True)
        for action,title in [('STEP_ON','Step on'),('HEIGHT','Measure height'),('STEP_OFF','Step off')]:row.operator('seca_study.action',text=title).action=action
        if s.view_mode=='HEIGHT':
            row=l.row(align=True)
            step='0.5 cm' if s.height_units=='CM' else '1/8 in'
            for action,title in [('HEIGHT_MINUS','− '+step),('HEIGHT_PLUS','+ '+step),('HEIGHT_REPEAT','Repeat height'),('HEIGHT_ACCEPT','Accept height'),('HEIGHT_CANCEL','Back')]:row.operator('seca_study.action',text=title).action=action
        if s.view_mode=='SETTINGS':
            row=l.row(align=True);row.operator('seca_study.action',text='Settings back').action='MENU_BACK';row.operator('seca_study.action',text='Settings home').action='MENU_HOME'
        if s.view_mode=='RECALL':l.operator('seca_study.action',text='Close recall').action='RECALL_CLOSE'
        if s.view_mode=='MESSAGE':
            row=l.row(align=True);row.operator('seca_study.action',text='Previous').action='MESSAGE_PREVIOUS';row.operator('seca_study.action',text='Close message').action='CLOSE_MESSAGE';row.operator('seca_study.action',text='Next').action='MESSAGE_NEXT'
        elif s.message and s.view_mode=='MAIN' and not s.disconnected:l.operator('seca_study.action',text='Read study message').action='OPEN_MESSAGE'
        box=l.box();box.label(text='Result retention (simulated)')
        row=box.row();row.enabled=not s.mock_network;row.prop(s,'autohold')
        row=box.row();row.enabled=not s.mock_network;row.prop(s,'clear_policy')
        if s.clear_policy=='TIMEOUT' and not s.mock_network:box.prop(s,'clear_timeout')
        if s.mock_network:
            box.label(text='Mock network: Auto-HOLD forced');box.label(text=f'Clear data: {s.net_clear_seconds} s')
            box.label(text=f'Mock clear timer: {s.net_clear_elapsed:.1f} s' if s.net_clear_armed else 'Mock clear timer: idle')
        row=box.row(align=True)
        for action,title in [('HOLD','Hold'),('RELEASE_HOLD','Release'),('CLEAR_RESULT','Clear'),('REPEAT','Repeat')]:row.operator('seca_study.action',text=title).action=action
        if s.view_mode=='TARE_MENU':
            for action,title in [('MOTHER_START','Mother / child'),('CLOTHING_START','Clothing / accessories'),('TARE_ADDITIONAL','Tare additional weight'),('TARE_CANCEL','Back')]:l.operator('seca_study.action',text=title).action=action
        if s.view_mode=='TARE_EDIT':
            row=l.row(align=True)
            for action,title in [('CLOTHING_MINUS','−'),('CLOTHING_PLUS','+'),('CLOTHING_ACCEPT','Accept'),('TARE_CANCEL','Cancel')]:row.operator('seca_study.action',text=title).action=action
        if s.mother_stage=='CHILD_READY':l.operator('seca_study.action',text='Accept child weight').action='MOTHER_ACCEPT'
        row=l.row(align=True)
        for action,title in [('TARE_MENU','Tare assistant'),('CLEAR_TARE','Clear tare'),('RECALL','Recall'),('RESET','Reset')]:row.operator('seca_study.action',text=title).action=action
        box=l.box();box.label(text='Synthetic pre-tare and scan');box.prop(s,'pre_tare_input')
        row=box.row(align=True);row.operator('seca_study.action',text='Save pre-tare').action='APPLY_PRE_TARE';row.operator('seca_study.action',text='Delete pre-tare').action='DELETE_PRE_TARE'
        box.prop(s,'scan_input_kg');row=box.row(align=True);row.operator('seca_study.action',text='Add synthetic scan').action='SCAN_TARE';row.operator('seca_study.action',text='Clear scans').action='CLEAR_SCANS'
        box=l.box();box.label(text='Local connection study — no network');box.prop(s,'mock_network')
        if s.mock_network:
            box.prop(s,'mock_transport')
            if s.mock_transport=='LAN':box.prop(s,'mock_lan_state')
            else:box.prop(s,'mock_wifi_signal');box.prop(s,'mock_wifi_associated')
            box.label(text=mock_link_description(s))
        box.prop(s,'scanner_attached')
        if s.scanner_attached:
            box.prop(s,'scan_fixture_target');box.prop(s,'scan_fixture');box.operator('seca_study.fixture_scan')
        box.prop(s,'synthetic_id');box.prop(s,'synthetic_user_id');box.prop(s,'show_demo_identity')
        if s.view_mode=='SETTINGS' and s.menu_page=='DATE_FORMAT':box.label(text='* sixth format: older manual; target unverified')
        if s.mock_network and s.view_mode=='MAIN':box.operator('seca_study.action',text='Clear synthetic IDs').action='LOGOUT_IDS'
        if s.view_mode=='OVERVIEW':
            box.operator('seca_study.action',text='Send mock result').action='OVERVIEW_SEND'
            box.operator('seca_study.action',text='Close overview').action='OVERVIEW_CLOSE'
        box.prop(s,'transfer_latency');box.prop(s,'transfer_failure_mode')
        if s.transfer_failure_mode!='NONE':box.prop(s,'transfer_failures');box.prop(s,'transfer_max_attempts')
        box.operator('seca_study.action',text='Mock confirm').action='CONFIRM'
        box.label(text=f'{s.transfer_state}: attempt {s.transfer_attempts}')
        if s.transfer_error:box.label(text=s.transfer_error)
        if s.transfer_state=='FAILED':box.operator('seca_study.action',text='Retry same result').action='TRANSFER_RETRY'
        if s.transfer_state in {'PENDING','RETRY_WAIT'}:box.operator('seca_study.action',text='Cancel transfer').action='TRANSFER_CANCEL'
        l.label(text=s.message);l.operator('seca_study.touch',icon='RESTRICT_SELECT_OFF')
        covers=context.scene.objects.get('CONTROL • column covers (study)')
        if covers:
            box=l.box();box.label(text='Column covers — exploded study');box.prop(covers,'["open"]',text='Open',slider=True);box.label(text='Cable routes and removal motion estimated')
        mount=context.scene.objects.get('CONTROL • display height (estimated)')
        if mount:
            box=l.box();box.label(text='Display mount — approximate');box.prop(mount,'location',index=2,text='Vertical offset (m)');box.label(text='Limits and height unverified')
        box=l.box();box.label(text='Rear connection guard');box.prop(s,'drip_guard_removed');box.label(text='Geometry approximate; no fluid simulation')
        box=l.box();box.label(text='Kinematic transport study');box.prop(s,'disconnected');box.prop(s,'transport_angle');box.prop(s,'transport_distance')
        box.prop(s,'transport_yaw');box.label(text=f'Axle x {s.transport_x:.2f} m, y {s.transport_y:.2f} m')
        box.prop(s,'arc_distance');box.prop(s,'arc_yaw');box.operator('seca_study.action',text='Apply arc pose').action='TRANSPORT_ARC'
        box.label(text='Angles and forces not calibrated')

classes=(SECA_PG_study,SECA_OT_action,SECA_OT_fixture_scan,SECA_OT_touch,SECA_PT_panel)
_last_tick=None
def _timer():
    global _last_tick
    now=time.monotonic();dt=.05 if _last_tick is None else min(.25,max(0,now-_last_tick));_last_tick=now
    scene=bpy.context.scene
    if scene and hasattr(scene,'seca_study'):
        s=scene.seca_study
        redraw=False
        if s.dynamic_weight and s.loaded and s.state in {'UNSTABLE','WEIGHED','RESULT'} and not s.disconnected:
            if advance_sampling(scene,dt):redraw=True
        if check_platform_change(scene):redraw=True
        if advance_calibration(scene,dt):redraw=True
        if advance_height(scene,dt):redraw=True
        if advance_retention(scene,dt):redraw=True
        if advance_network_clear(scene,dt):redraw=True
        if advance_transfer(scene,dt):redraw=True
        if advance_standby(scene,dt):redraw=True
        if invalidate_changed_geometry(scene):refresh(scene);redraw=True
        if redraw:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type=='VIEW_3D':area.tag_redraw()
    return .05

def register():
    _sample_windows.clear()
    previous_stop=bpy.app.driver_namespace.pop('seca_audio_stop',None)
    if previous_stop:previous_stop()
    bpy.app.driver_namespace['seca_audio_stop']=stop_audio
    old=bpy.app.driver_namespace.pop('seca_study_timer',None)
    if old and bpy.app.timers.is_registered(old):bpy.app.timers.unregister(old)
    if hasattr(bpy.types.Scene,'seca_study'):del bpy.types.Scene.seca_study
    for cls in reversed(classes):
        # Blender registers operator RNA under CATEGORY_OT_name, panel RNA
        # under bl_idname, and property groups under their Python class name.
        if issubclass(cls,bpy.types.Operator):
            category,name=cls.bl_idname.split('.',1);identifier=category.upper()+'_OT_'+name
        elif issubclass(cls,bpy.types.Panel):identifier=cls.bl_idname
        else:identifier=cls.__name__
        existing=cls.__bases__[0].bl_rna_get_subclass_py(identifier,None)
        if existing:bpy.utils.unregister_class(existing)
    for cls in classes:bpy.utils.register_class(cls)
    bpy.types.Scene.seca_study=PointerProperty(type=SECA_PG_study)
    bpy.app.driver_namespace['seca_setup_changed']=invalidate_after_setup_change
    if bpy.context.scene.get('seca_setup_dirty',False):invalidate_after_setup_change(bpy.context.scene)
    touch_feedback(bpy.context.scene,None,None)
    sync_calibration_rod(bpy.context.scene,False)
    sync_phantom(bpy.context.scene)
    update_drip_guard(bpy.context.scene.seca_study,bpy.context)
    scene=bpy.context.scene;apply_display_brightness(scene);remove_platform_watchers();depsgraph=bpy.context.evaluated_depsgraph_get()
    current=platform_geometry_signature(scene,depsgraph);_platform_signature_cache[scene.as_pointer()]=current
    if scene.seca_study.cal_valid or scene.seca_study.cal_stage not in {'IDLE','FAILED'}:
        try:recorded_glass=json.loads(scene.get('seca_calibration_glass_signature','null'))
        except (ValueError,TypeError):recorded_glass=None
        if current is None or recorded_glass is None or platform_signatures_differ(recorded_glass,current):invalidate_after_setup_change(scene)
    bpy.app.handlers.depsgraph_update_post.append(_watch_platform_depsgraph)
    remove_transport_watchers();pose=remember_transport_pose(scene,depsgraph)
    if pose is not None:sync_generated_transport(scene,pose,depsgraph)
    if scene.seca_study.cal_valid and pose is not None:
        recorded=scene.get('seca_calibration_transport_pose')
        if recorded is None:scene['seca_calibration_transport_pose']=list(pose)
        elif transport_pose_differs(recorded,pose):invalidate_after_setup_change(scene)
    bpy.app.handlers.frame_change_post.append(_seca_study_watch_transport_v29)
    bpy.app.handlers.depsgraph_update_post.append(_seca_study_watch_transport_depsgraph_v29)
    require_live_sampling(scene)
    refresh(scene)
    if not bpy.app.background:
        bpy.app.driver_namespace['seca_study_timer']=_timer;bpy.app.timers.register(_timer,first_interval=.05)
def unregister():
    stop_audio();bpy.app.driver_namespace.pop('seca_audio_stop',None)
    remove_transport_watchers();remove_platform_watchers()
    bpy.app.driver_namespace.pop('seca_setup_changed',None)
    old=bpy.app.driver_namespace.pop('seca_study_timer',None)
    if old and bpy.app.timers.is_registered(old):bpy.app.timers.unregister(old)
    if hasattr(bpy.types.Scene,'seca_study'):del bpy.types.Scene.seca_study
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
if __name__=='__main__':register()
