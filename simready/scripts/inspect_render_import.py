import bpy,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=str(ROOT/'asset/seca_scale_up_ultra_articulated/usd/seca_scale_up_ultra_articulated.usda')
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.wm.usd_import(filepath=p,import_guide=False,import_proxy=False)
a=[]
for obj in bpy.context.scene.objects:
 if any(x in obj.name.lower() for x in ['wheel','collider']):
  a.append({'name':obj.name,'type':obj.type,'parent':obj.parent.name if obj.parent else None,'children':[x.name for x in obj.children]})
(ROOT/'validation/render-import-objects.json').write_text(json.dumps(a,indent=2)+'\n');print(json.dumps(a,indent=2))
