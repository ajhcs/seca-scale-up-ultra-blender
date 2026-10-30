import csv,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/'source/build-inputs/prior-backlog.json').read_text())
updates={
'SR-01':('partial','Robotics-Prop 4.0.0 is the static profile for the five-body study; a target dynamics runtime and functional interaction contract are not established.'),
'SR-02':('blocked','The 582.7 vs 650 mm discrepancy is quantified and three hypothetical registrations are recorded; physical front/rear datum evidence is missing.'),
'SR-03':('partial','42 collision meshes pass closed-topology checks. Of 272 visual meshes, 22 have indexed boundary edges and 220 triangles are exactly zero-area; 3,004 have cross-product magnitude below 2e-14 m². Intended artwork and seam repair remain to be assessed.'),
'SR-04':('partial','Forty-nine modeled display poses show no crossings in selected Blender surfaces and no tested head-proxy/base-proxy overlaps outside the excluded mount pair; no continuous sweep, containment, full geometry or physical clearance is established.'),
'SR-06':('done','Meters, Z-up, floor-centered origin and all 272 source-selected component bounds and material bindings are checked in the assembled stage; relocation is separately verified from the delivery archive.'),
'SR-10':('partial','Five body masses sum to the published 29 kg and have finite positive inertia satisfying triangle inequalities; the distribution, inertia, center of mass and response are estimated.'),
'SR-11':('partial','42 closed convex collision proxies represent separate links; the unpowered reconstructed Bullet drop settled on a floor while its display reached the tilt stop, with mounting arm omitted from the Bullet test.'),
'SR-13':('partial','Two wheel revolutes and two display revolutes, estimated pivots and study limits are authored; reconstructed fixed-base Bullet probes exercise both directions, but the physical mechanism, stops, resistance and USD/PhysX motion remain unverified.'),
'SR-14':('partial','Connected-body pairs and one display/mount collider pair are filtered in USD, while mast/rail remain enabled; sampled proxy checks and a broader-exclusion Bullet test do not establish runtime contact behavior.'),
'SR-15':('partial','The USD retains the saved display artwork and the display geometry moves with its study link; dynamic screen states, touch alignment and compact baked representation are not implemented.'),
'SR-16':('partial','A separate deterministic offline fictional subset exercises tare, hold, units, synthetic scans and mock failure/retry, including independent instances; no USD or Blender adapter or behavioral parity is claimed.'),
'SR-18':('partial','Equipment, part and estimated material labels are authored across links; target-runtime instance and material masks and taxonomy application remain untested.'),
'SR-19':('partial','Five relative visual layers and a separate optional illustrative display-drive overlay are composed under an unpowered main stage; target-runtime-specific behavior is unverified.'),
'SR-20':('not done','The render inventory measures 272 meshes, 81,964 points and 145,872 triangles; draw-call optimization, LOD, texture bake and target-scene performance remain open.'),
'SR-21':('partial','Profile metadata, source revision and a new USD-imported thumbnail are authored; material and dimensional provenance are still incomplete.'),
'SR-23':('done','NVIDIA validator 2026.8.0 reports Robotics-Prop 4.0.0 static PASS; FET_004_STANDARD and FET_004_PHYSX static checks pass, while the report lists unmet optional features including FET_100_ISAAC.'),
'SR-24':('blocked','Isaac/RTX/PhysX execution and the NVIDIA benchmark require a supported runtime and graphics environment; local Bullet reconstruction does not replace them.'),
'SR-25':('partial','Two-way four-joint Bullet tests, a five-body drop, 49 visual and 49 proxy display samples, an ideal one-axis drive calculation and portable fictional workflow scenarios are recorded; actual transport, PhysX, hold-under-gravity and validated device behavior remain open.'),
'SR-26':('partial','Local layers, original and editable sources, prior inputs, licenses, static reports, assumptions, failure history and hashes are included; no official submission, target-runtime benchmark or manufacturer-verified BOM exists.'),
'SR-28':('partial','Original and editable Blender sources, articulated USD, local preview and supporting reports are provided; physical correctness, target runtime and interactive USD behavior remain unverified.'),
}
for r in rows:
 if r['id'] in updates:r['status'],r['result']=updates[r['id']]
(ROOT/'BACKLOG-STATUS.json').write_text(json.dumps(rows,indent=2)+'\n')
with (ROOT/'BACKLOG-STATUS.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
parts=['# SimReady derivative backlog status','', 'The statuses apply to this local articulated study. A partial item is not accepted as complete; the numbered rows retain the original WHAT and one-sentence HOW.', '']
for r in rows:
 parts.extend([f"## {r['id']} — {r['phase']} — {r['status']}",'',f"**WHAT:** {r['what']}", '',f"**HOW:** {r['how']}",'',f"**Current evidence and remaining work:** {r['result']}",''])
(ROOT/'BACKLOG-STATUS.md').write_text('\n'.join(parts).rstrip()+'\n')
print('Updated',len(rows),'items')
