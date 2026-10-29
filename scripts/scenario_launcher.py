"""Run on a disposable, freshly opened v50 scene; this changes the scene."""
import bpy
sim={'__name__':'__main__'};exec(bpy.data.texts['seca_simulator.py'].as_string(),sim)
bpy.app.driver_namespace['seca_scenario_sim']=sim
exec(bpy.data.texts['scenario_replay.py'].as_string(),{'__name__':'__main__'})
