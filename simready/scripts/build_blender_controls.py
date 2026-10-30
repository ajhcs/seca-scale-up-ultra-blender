import bpy,hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
prior=ROOT/'source/build-inputs/seca-simready-editable.blend'
original=ROOT/'source/seca-scale-up-ultra-original.blend'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=sha(original);prior_before=sha(prior)
bpy.ops.wm.open_mainfile(filepath=str(prior),load_ui=False,use_scripts=False)
specs=[('CONTROL • wheel L','X',None),('CONTROL • wheel R','X',None),
       ('CONTROL • display swivel','Z',(-.6,.6)),('CONTROL • display tilt and rotation','X',(-.4,.4))]
for name,axis,limits in specs:
    obj=bpy.context.scene.objects[name];c=obj.constraints.new('LIMIT_ROTATION');c.name='Provisional SimReady study limits';c.owner_space='LOCAL'
    for a in 'xyz':
        enabled=a.upper()!=axis or limits is not None
        setattr(c,'use_limit_'+a,enabled)
        setattr(c,'min_'+a,(limits[0] if a.upper()==axis and limits else 0))
        setattr(c,'max_'+a,(limits[1] if a.upper()==axis and limits else 0))
    obj['simready_study_note']='Modeled control and limits; not measured or verified manufacturer mechanics.'
notes=bpy.data.texts.get('SIMREADY_ARTICULATION_NOTES.txt') or bpy.data.texts.new('SIMREADY_ARTICULATION_NOTES.txt')
notes.clear();notes.write('Provisional controls: wheels rotate about local X; display swivel about local Z is limited to +/- 0.6 rad and tilt about local X to +/- 0.4 rad. These are study ranges from the reconstruction, not measured device limits. The display cable is static. No physics is validated by these Blender controls.\n')
target=ROOT/'source/seca-articulation-editable.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(target),check_existing=False)
result={'source_sha256_before':before,'source_sha256_after':sha(original),'prior_sha256_before':prior_before,'prior_sha256_after':sha(prior),
        'output_sha256':sha(target),'controls':[{'name':n,'axis':a,'study_limits_rad':r} for n,a,r in specs],
        'scope':'Editable source-derived controls, with provisional rotation limits and no script autorun; USD physics is authored separately.'}
assert result['source_sha256_before']==result['source_sha256_after'] and result['prior_sha256_before']==result['prior_sha256_after']
(ROOT/'validation/blender-controls.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
