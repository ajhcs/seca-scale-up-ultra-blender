"""Reopen the delivered Blender source without executing embedded scripts."""
import bpy,hashlib,json,math,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
prior=ROOT/'source/build-inputs/seca-simready-editable.blend';current=ROOT/'source/seca-articulation-editable.blend';original=ROOT/'source/seca-scale-up-ultra-original.blend'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
 bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
 return {'objects':len(bpy.data.objects),'meshes':len(bpy.data.meshes),'materials':len(bpy.data.materials),
         'texts':{t.name:hashlib.sha256(t.as_string().encode()).hexdigest() for t in bpy.data.texts}}
a=read(prior);b=read(current)
specs=[('CONTROL • wheel L','x',None),('CONTROL • wheel R','x',None),('CONTROL • display swivel','z',.6),('CONTROL • display tilt and rotation','x',.4)]
controls=[]
for name,axis,limit in specs:
 ob=bpy.data.objects[name];c=ob.constraints.get('Provisional SimReady study limits')
 valid=bool(c and c.type=='LIMIT_ROTATION' and c.owner_space=='LOCAL')
 if valid:
  for dim in 'xyz':
   actual=getattr(c,'use_limit_'+dim);expected=(dim!=axis or limit is not None);valid &= actual==expected
   if expected:
    desired=limit if dim==axis and limit else 0
    valid &= abs(getattr(c,'min_'+dim)+desired)<1e-6 and abs(getattr(c,'max_'+dim)-desired)<1e-6
 controls.append({'name':name,'axis':axis,'valid':bool(valid),'limit_rad':limit})
checks={'original_matches_recorded_hash':sha(original)=='57e64f249073c472abacbc942eb990a76657a26333f56e80ec922815e7c5525d',
 'prior_text_blocks_unchanged':all(b['texts'].get(k)==v for k,v in a['texts'].items()),
 'same_object_mesh_material_counts':all(a[k]==b[k] for k in ('objects','meshes','materials')),
 'articulation_note_added':'SIMREADY_ARTICULATION_NOTES.txt' in b['texts'],
 'four_study_controls':all(c['valid'] for c in controls)}
result={'checks':checks,'prior':a,'current':b,'controls':controls,'original_sha256':sha(original),'prior_sha256':sha(prior),'current_sha256':sha(current),
 'scope':'Blender data and constraints reopened with use_scripts=False; embedded behavior was not executed or validated.'}
(ROOT/'validation/blender-reopen.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'checks':checks,'prior_counts':{k:a[k] for k in ('objects','meshes','materials')},'current_counts':{k:b[k] for k in ('objects','meshes','materials')},'controls':controls},indent=2));assert all(checks.values())
