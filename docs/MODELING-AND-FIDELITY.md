# Modeling, use and fidelity

## Target and source material

The target is the US seca Scale-up Ultra configuration ONSHMIUTNN: 654 platform scale, 455 handrail, standard 257 ultrasonic measuring column, ID display and AC adapter. The [product page](https://us.secashop.com/products/measuring-stations-and-column-scales/seca-scale-up-ultra/ONSHMIUTNN) supplies the order configuration and nominal product dimensions. The [manufacturer product page](https://www.seca.com/en_us/products/all-products/product-details/seca654.html) covers several variants and links assembly material and Revit families. The [654/655 English manual](https://www.seca.com/fileadmin/documents/manual/seca_man_654_655_EN.pdf) describes operation and the [257/256 assembly instructions](https://www.seca.com/fileadmin/documents/manual/seca_man_257_256_de_en_fr_es.pdf) show the assembly and cable routing.

The reference packet contains product images, drawings, specifications, operation manuals and Revit families; the actual manufacturer assets are not redistributed here. The matching complete-family file identifies Revit LT 2016; a local third-party offline conversion attempt failed to decode its version, so no manufacturer geometry was used as a measured mesh. The source images have limited resolution, and the product and manuals can show different hardware or firmware revisions. The target unit's precise revision is not confirmed.

## Construction

The project was built as an editable reconstruction, using published outer and platform dimensions as initial constraints and photographs and assembly drawings for silhouette, appearance and broad part placement. Meshes, curves and separate materials represent the platform, glass, illuminated markings, column, head, rail, display, wheels, feet, guard and schematic connections. Some shapes were compared from approximate cameras; this is visual fitting, not calibrated photogrammetry or manufacturer dimensional verification. Two packed manufacturer reference images in the preserved v86 working file were removed from the public copy; the product geometry and study scripts remain.

The independent material nodes approximate white finishes, metal, dark housings, transparent surfaces and illuminated display elements. Their real compositions, measured roughness, optical properties, layer stack and color under calibrated light are unknown. The cover and channel study visualizes schematic cable routing and staged separation; it does not recover the true hidden connectors, complete cable lengths or a verified service procedure.

## What the controls do

Run the embedded simulator from Blender's Text Editor before using the **seca study** sidebar. The display contains editable Blender screen geometry and implements fictional measurements, simulated tare and hold, a mock scan, synthetic patient identifiers and local mock transfer. It uses illustrations from newer and older manuals as references; its layouts, type, firmware revision, exact transitions and timing have not been validated against a physical unit. Run only scripts you trust and inspect them before executing; model loading itself does not need auto-run.

The optional height study uses geometric rays or an adjustable geometric echo-fan heuristic. The fan is not a wave-acoustic simulation and does not reproduce seca's ultrasonic processing. Synthetic weight filtering, thresholds and timing are study choices. Its BMI/BSA calculations and displays are not validated for medical use. The embedded voice clips are synthesized from Flite, not manufacturer recordings; the mock network sends no real device or patient data.

For additional studies, run `clearance_study.py` after the simulator to inspect a sampled hypothetical transport path; run `display_fit_study.py` for selected current-pose display surface crossings; run `level_study.py` or `load_study.py` for approximate leveling and load distribution. These tools do not establish continuous motion clearance, contact mechanics, accessibility, force transfer, component stiffness or physical safety. The model's editable control ranges are estimates and should not be interpreted as physical stops.

## Known fidelity gaps

- Selected source geometry in the v77 saved room-handoff pose evaluated to **801 × 582.7 × 2387 mm**; seca publishes **801 × 650 × 2387 mm** for the handrail and standard column. The 67.3 mm depth difference is unresolved, and neither physical end datum is known.
- The model's Z=0 is its modeled floor; matching the published 70 mm platform height to that datum has not been demonstrated. The 801 mm model width was deliberately fitted using an assumed flange radius, so it is not independent validation.
- The display shell, mount, pivot, stops and cable path are estimated. Large unconstrained modeled rotations can intersect the rail. The selected-surface check does not test full containment, near misses or a continuous sweep.
- Wheel radius, axle position, weight distribution, friction, cable stiffness, support loads and operator motion have not been measured. Animated or simulated motion is illustrative.
- Hardware and firmware variants, touchscreen pixel dimensions, real sound, transducer field and calibration data are not established. The archive's manufacturer manuals document conditions and tolerances, but the study has not been measured against an actual device.

## Verification and reuse

The public file is a separate derivative of the preserved v86 working model. The release process removed two packed manufacturer reference images and retained the packed font and synthetic audio under their respective licenses. The scene was reopened and checked locally; its study scripts and generated images are included for inspection. Test results validate specific modeled behavior and file integrity only, not medical, regulatory, ergonomic or manufacturer acceptance.

Original scripts are MIT licensed; original model and generated renders are CC BY 4.0 to the extent contributors have rights. Third-party font and audio terms are separate, as are manufacturer materials and marks. Consult [NOTICE](../NOTICE.md) before reuse.
