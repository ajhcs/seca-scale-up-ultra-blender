"""Deterministic, fictional seca study scenario; run only on a disposable scene copy.

Run seca_simulator.py first. Running this script mutates the current scene and
stores a trace in a Blender text block; it never saves the blend or sends data.
"""
import bpy,json,math,traceback

TICK=.05
SETTABLE={'mock_network','synthetic_id','synthetic_user_id','dynamic_weight','timed_height','height_duration','gross_kg','height_cm','cal_area_clear','cal_rod_placed','cal_duration','fault_scenario','drip_guard_removed','disconnected','transport_angle','arc_distance','arc_yaw','net_clear_seconds'}
ACTIONS={'CAL_START','CAL_NEXT','MODE_RESTART','SELF_NEXT','SELF_BACK','STEP_ON','STEP_OFF','FAULT_INJECT','FAULT_RESTART','TRANSPORT_ARC','HEIGHT','HEIGHT_ACCEPT'}
SNAP_FIELDS=('measurement_mode','self_stage','self_id','state','view_mode','loaded','disconnected','cal_stage','cal_valid','setup_remeasure_required','height_measuring','display_standby','gross_kg','filtered_kg','measured_height_cm','fault_active','transfer_state','transfer_attempts','message','transport_angle','transport_x','transport_y','transport_yaw','wheel_l_distance','wheel_r_distance','net_clear_seconds','net_clear_elapsed','net_clear_armed','net_data_expired','synthetic_id','has_last')
SCREEN_PREFIXES=('SIM • ','SELF • ','SELFART • ','CAL • ','FAULT • ','REVIEW • ','OVERVIEW • ','MEASURE • ','MSG • ')

def snapshot(scene):
 s=scene.seca_study;bpy.context.view_layer.update()
 def matrix(name):
  o=scene.objects.get(name)
  if not o:raise ValueError('Missing geometry '+name)
  return [[round(float(x),7) for x in row] for row in o.matrix_world]
 text={o.name:o.data.body for o in scene.objects if o.type=='FONT' and o.name.startswith(SCREEN_PREFIXES) and not o.hide_render and not o.hide_get() and o.data.body}
 return {'state':{k:getattr(s,k) for k in SNAP_FIELDS},'visible_text':dict(sorted(text.items())),
         'product_matrix':matrix('CONTROL • product root'),'display_matrix':matrix('ID display active image'),
         'mock_payload':json.loads(s.transfer_payload) if s.transfer_payload else None,
         'mock_receipts':json.loads(s.receiver_records or '{}')}

def validate(events):
 if not isinstance(events,list) or not events:raise ValueError('Scenario requires a nonempty event list')
 for i,e in enumerate(events):
  if not isinstance(e,dict) or e.get('type') not in {'set','action','advance'}:raise ValueError(f'Invalid event {i}')
  if e['type']=='set' and e.get('name') not in SETTABLE:raise ValueError(f'Forbidden property in event {i}')
  if e['type']=='action' and e.get('name') not in ACTIONS:raise ValueError(f'Forbidden action in event {i}')
  if e['type']=='advance' and (not isinstance(e.get('seconds'),(int,float)) or not math.isfinite(e['seconds']) or not 0<=e['seconds']<=60):raise ValueError(f'Invalid clock increment in event {i}')
  if not isinstance(e.get('expect',{}),dict) or any(k not in SNAP_FIELDS for k in e.get('expect',{})):raise ValueError(f'Invalid expectation in event {i}')

def run(scene,sim,events,on_event=None):
 if not hasattr(scene,'seca_study'):raise RuntimeError('Run seca_simulator.py before the scenario')
 s=scene.seca_study
 if s.loaded or s.disconnected or s.state!='READY' or s.cal_stage!='IDLE' or s.fault_active!='NONE' or s.transfer_state!='IDLE' or s.transport_angle or abs(s.transport_x)>1e-6 or abs(s.transport_y)>1e-6:raise RuntimeError('Scenario requires the untouched, upright, powered baseline scene')
 validate(events)
 timer=bpy.app.driver_namespace.get('seca_study_timer');was_running=bool(timer and bpy.app.timers.is_registered(timer))
 if was_running:bpy.app.timers.unregister(timer)
 trace={'scenario':'fictional complete workflow v1','time_basis':'deterministic simulator clock, not measured device timing','scope':'Local synthetic events only; no hardware, scanner, clinical data or external transmission','tick_s':TICK,'status':'RUNNING','events':[],'timed_transitions':[]};clock=0.0
 try:
  for i,event in enumerate(events):
   typ=event['type']
   if typ=='set':setattr(s,event['name'],event['value'])
   elif typ=='action':sim['do_action'](scene,event['name'])
   else:
    remaining=float(event['seconds'])
    keys=('state','self_stage','cal_stage','view_mode','fault_active','transfer_state','display_standby','height_measuring','loaded','net_data_expired')
    signature=tuple(getattr(s,k) for k in keys)
    while remaining>1e-9:
     dt=min(TICK,remaining);remaining-=dt;clock+=dt
     for fn in ('advance_sampling','advance_calibration','advance_height','advance_retention','advance_network_clear','advance_transfer','advance_standby'):sim[fn](scene,dt)
     if sim['invalidate_changed_geometry'](scene):sim['refresh'](scene)
     new_signature=tuple(getattr(s,k) for k in keys)
     if new_signature!=signature:
      trace['timed_transitions'].append({'event_index':i,'time_s':round(clock,6),'snapshot':snapshot(scene)});signature=new_signature
   snap=snapshot(scene);mismatches={}
   for key,expected in event.get('expect',{}).items():
    actual=snap['state'][key]
    if isinstance(expected,(float,int)) and not isinstance(expected,bool):ok=abs(actual-expected)<1e-4
    else:ok=actual==expected
    if not ok:mismatches[key]={'expected':expected,'actual':actual}
   trace['events'].append({'index':i,'time_s':round(clock,6),'event':event,'snapshot':snap,'mismatches':mismatches})
   if mismatches:raise AssertionError(f'Event {i} ({event.get("label",typ)}) failed: {mismatches}')
   if on_event:on_event(i,event,snap)
  trace['status']='PASS'
 except Exception as exc:
  trace['status']='FAIL';trace['error']=str(exc);trace['traceback']=traceback.format_exc()
 finally:
  if was_running:
   sim['_last_tick']=None;bpy.app.timers.register(timer,first_interval=.05)
  text=bpy.data.texts.get('seca_scenario_trace.json') or bpy.data.texts.new('seca_scenario_trace.json');text.clear();text.write(json.dumps(trace,indent=2,sort_keys=True,allow_nan=False))
 if trace['status']!='PASS':raise RuntimeError(trace['error'])
 return trace

def main():
 # Simulator registration puts the live functions in the Blender driver namespace.
 sim=bpy.app.driver_namespace.get('seca_scenario_sim')
 if not sim:raise RuntimeError('Run scenario_launcher.py, which registers the simulator and starts the replay')
 events=json.loads(bpy.data.texts['seca_scenario.json'].as_string())['events']
 return run(bpy.context.scene,sim,events)
if __name__=='__main__':main()
