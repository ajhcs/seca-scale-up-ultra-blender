# SimReady derivative backlog status

The statuses apply to this local articulated study. A partial item is not accepted as complete; the numbered rows retain the original WHAT and one-sentence HOW.

## SR-01 — Baseline — partial

**WHAT:** Choose the intended consumer, runtime and release scope, with Robotics-Prop 4.0.0 as the proposed first target.

**HOW:** Record the selected profile, resolved feature versions, runtime, operating modes and permitted claims before changing the derivative.

**Current evidence and remaining work:** Robotics-Prop 4.0.0 is the static profile for the five-body study; a target dynamics runtime and functional interaction contract are not established.

## SR-02 — Baseline — blocked

**WHAT:** Resolve the configured device envelope, physical floor and front/rear datums without a global stretch that distorts known parts.

**HOW:** Measure a matching unit or reconcile reliable dimensional drawings against named model surfaces and document remaining uncertainty.

**Current evidence and remaining work:** The 582.7 vs 650 mm discrepancy is quantified and three hypothetical registrations are recorded; physical front/rear datum evidence is missing.

## SR-03 — Geometry — partial

**WHAT:** Audit actual solid/contact shapes for open seams, degenerate faces, wrong normals and unintended internal surfaces.

**HOW:** Inspect flagged evaluated meshes by function and repair or replace collision solids while retaining legitimate planar artwork.

**Current evidence and remaining work:** 42 collision meshes pass closed-topology checks. Of 272 visual meshes, 22 have indexed boundary edges and 220 triangles are exactly zero-area; 3,004 have cross-product magnitude below 2e-14 m². Intended artwork and seam repair remain to be assessed.

## SR-04 — Geometry — partial

**WHAT:** Resolve impossible intersections and verify assembly relationships before adding dynamics.

**HOW:** Check evaluated surfaces and clearances through each released pose and repair the fitted parts or constrain the permitted motion.

**Current evidence and remaining work:** Forty-nine modeled display poses show no crossings in selected Blender surfaces and no tested head-proxy/base-proxy overlaps outside the excluded mount pair; no continuous sweep, containment, full geometry or physical clearance is established.

## SR-05 — Geometry — done

**WHAT:** Define the exact equipment membership and configurations for export.

**HOW:** Build an explicit component manifest that includes the product parts and excludes staging, phantoms and unused variants from the runtime asset.

**Current evidence and remaining work:** The 272-object visual selection, including three channel covers, is recorded in the visual export receipt.

## SR-06 — Geometry — done

**WHAT:** Normalize the derivative hierarchy, transforms, floor pivot and stable part names.

**HOW:** Map native names to stable USD paths and verify world-space surfaces after applying the chosen transform and naming policy.

**Current evidence and remaining work:** Meters, Z-up, floor-centered origin and all 272 source-selected component bounds and material bindings are checked in the assembled stage; relocation is separately verified from the delivery archive.

## SR-07 — Materials — partial

**WHAT:** Repair display backlight and UI divider, secondary, ink, white and cool grey blue materials in the USD derivative.

**HOW:** Replace unsupported node groups with exportable USD Preview Surface networks and verify their bound outputs in the target renderer.

**Current evidence and remaining work:** All visible USD material bindings resolve; the saved display renders in Blender, while RTX and all UI states remain untested.

## SR-08 — Materials — partial

**WHAT:** Create UVs and portable texture inputs where the selected material representation requires them.

**HOW:** Unwrap the affected surfaces and bake procedural appearance into correctly tagged maps while preserving the editable Blender materials.

**Current evidence and remaining work:** Procedural group shaders were translated into editable preview approximations; no texture bake or texel-density study was performed.

## SR-09 — Materials — partial

**WHAT:** Improve glass thickness and transmission, metal and white finish separation, labels and emissive screen appearance.

**HOW:** Compare matched neutral-light reference views and target-runtime renders while recording which material parameters are measured or estimated.

**Current evidence and remaining work:** Glass, display and finishes render in Blender; target RTX comparison and measured optical properties are unavailable.

## SR-10 — Physics — partial

**WHAT:** Author valid rigid bodies, mass, center of mass and inertia at the level needed by the release.

**HOW:** Use the verified assembly mass where applicable and distribute measured or explicitly estimated part properties with sensitivity checks.

**Current evidence and remaining work:** Five body masses sum to the published 29 kg and have finite positive inertia satisfying triangle inequalities; the distribution, inertia, center of mass and response are estimated.

## SR-11 — Physics — partial

**WHAT:** Create efficient contact geometry for the platform, rail, feet, wheels, column and display.

**HOW:** Author simple or compound colliders that preserve the handrail opening and support surfaces independently of render detail.

**Current evidence and remaining work:** 42 closed convex collision proxies represent separate links; the unpowered reconstructed Bullet drop settled on a floor while its display reached the tilt stop, with mounting arm omitted from the Bullet test.

## SR-12 — Physics — partial

**WHAT:** Define physical materials for feet, tires, floor contact and any manipulation surfaces.

**HOW:** Measure representative behavior or declare provisional coefficients and test their effect over the intended contact scenarios.

**Current evidence and remaining work:** Placeholder friction and restitution are documented and three friction values were compared on an illustrative slope; material measurements are absent.

## SR-13 — Articulation — partial

**WHAT:** Add display pivot and wheel joints only where supported by the chosen use case and device evidence.

**HOW:** Author connected bodies, joint frames, axes, limits and drives from measured or explicitly estimated mechanisms.

**Current evidence and remaining work:** Two wheel revolutes and two display revolutes, estimated pivots and study limits are authored; reconstructed fixed-base Bullet probes exercise both directions, but the physical mechanism, stops, resistance and USD/PhysX motion remain unverified.

## SR-14 — Articulation — partial

**WHAT:** Define intentional self-collision and contact filtering for connected links.

**HOW:** Test contact pairs and disable only structurally justified adjacent-link collisions while keeping useful external contacts active.

**Current evidence and remaining work:** Connected-body pairs and one display/mount collider pair are filtered in USD, while mast/rail remain enabled; sampled proxy checks and a broader-exclusion Bullet test do not establish runtime contact behavior.

## SR-15 — Behavior — partial

**WHAT:** Represent static artwork and dynamic UI with a compact runtime display surface while preserving native editability.

**HOW:** Bake static elements and generate display textures or a dedicated UI layer for dynamic values and touch targets.

**Current evidence and remaining work:** The USD retains the saved display artwork and the display geometry moves with its study link; dynamic screen states, touch alignment and compact baked representation are not implemented.

## SR-16 — Behavior — partial

**WHAT:** Separate the synthetic device state and calculations from Blender and implement a target-runtime adapter when interaction is required.

**HOW:** Define typed inputs, state transitions, deterministic timing and outputs with adapters for scene movement, display and synthetic audio.

**Current evidence and remaining work:** A separate deterministic offline fictional subset exercises tare, hold, units, synthetic scans and mock failure/retry, including independent instances; no USD or Blender adapter or behavioral parity is claimed.

## SR-17 — Measurement — blocked

**WHAT:** Establish an engineering validation scope before claiming physical weight or ultrasonic fidelity.

**HOW:** Acquire calibration observations and appropriate sensor/load parameters and compare model outputs against independent measurements across declared conditions.

**Current evidence and remaining work:** Physical weighing and acoustic validation require instrument parameters and independent measurements.

## SR-18 — Semantics — partial

**WHAT:** Add stable equipment and part semantics appropriate to the profile and downstream synthetic data tasks.

**HOW:** Author current USD semantic labels and verify a real relevant Wikidata class plus the instance and material label outputs.

**Current evidence and remaining work:** Equipment, part and estimated material labels are authored across links; target-runtime instance and material masks and taxonomy application remain untested.

## SR-19 — Interchange — partial

**WHAT:** Organize geometry, appearance, physics and runtime-specific opinions into maintainable USD composition.

**HOW:** Keep shared visual content referenced by separate physics and runtime layers with explicit variants and relative dependencies.

**Current evidence and remaining work:** Five relative visual layers and a separate optional illustrative display-drive overlay are composed under an unpowered main stage; target-runtime-specific behavior is unverified.

## SR-20 — Performance — not done

**WHAT:** Reduce geometry and draw calls where they do not improve silhouette, contact or task-visible detail.

**HOW:** Bake artwork, simplify threads and small hidden parts, and define optional detail variants against a measured target scene budget.

**Current evidence and remaining work:** The render inventory measures 272 meshes, 81,964 points and 145,872 triangles; draw-call optimization, LOD, texture bake and target-scene performance remain open.

## SR-21 — Metadata — partial

**WHAT:** Supply the required thumbnail and provenance including reconstruction origin, source revision and limitations.

**HOW:** Author the selected profile metadata and permitted sidecars with measured-versus-estimated status and a thumbnail of the actual derivative.

**Current evidence and remaining work:** Profile metadata, source revision and a new USD-imported thumbnail are authored; material and dimensional provenance are still incomplete.

## SR-22 — Licensing — done

**WHAT:** Carry accurate licensing and attribution into the derived package without bundling unlicensed reference media.

**HOW:** Inventory every distributed dependency and reconcile its notices with the asset-package and dataset license declarations.

**Current evidence and remaining work:** Original attribution and applicable font, model and script licenses are carried with the corresponding local files.

## SR-23 — Validation — done

**WHAT:** Run real SimReady static validation against the resolved profile and selected optional features.

**HOW:** Use a qualified isolated tool environment to retain per-requirement reports, failing prim paths and exact tier and library versions.

**Current evidence and remaining work:** NVIDIA validator 2026.8.0 reports Robotics-Prop 4.0.0 static PASS; FET_004_STANDARD and FET_004_PHYSX static checks pass, while the report lists unmet optional features including FET_100_ISAAC.

## SR-24 — Validation — blocked

**WHAT:** Run the supported benchmark suite and actual RTX/PhysX load tests on the derived asset.

**HOW:** Execute the installed suite with retained logs, reports and recordings and review drop, settling, contact and material behavior.

**Current evidence and remaining work:** Isaac/RTX/PhysX execution and the NVIDIA benchmark require a supported runtime and graphics environment; local Bullet reconstruction does not replace them.

## SR-25 — Validation — partial

**WHAT:** Add scale-specific per-joint, placement, support and behavior checks beyond the generic benchmark.

**HOW:** Exercise every released motion and representative supported-load and transport scenario using explicit tolerances tied to the intended task.

**Current evidence and remaining work:** Two-way four-joint Bullet tests, a five-body drop, 49 visual and 49 proxy display samples, an ideal one-axis drive calculation and portable fictional workflow scenarios are recorded; actual transport, PhysX, hold-under-gravity and validated device behavior remain open.

## SR-26 — Packaging — partial

**WHAT:** Build a complete runtime package with dependency inventory, validation results, benchmark evidence and content hashes.

**HOW:** Use the current supported packaging workflow on a derivative-only folder and reopen the exact packaged bytes in a clean location.

**Current evidence and remaining work:** Local layers, original and editable sources, prior inputs, licenses, static reports, assumptions, failure history and hashes are included; no official submission, target-runtime benchmark or manufacturer-verified BOM exists.

## SR-27 — Publication — not authorized

**WHAT:** Prepare a Hugging Face dataset and Central registration only if public catalog contribution is desired.

**HOW:** Follow the current collaborator process and submit immutable package-definition URLs with matching licenses and retained release history.

**Current evidence and remaining work:** No public dataset, catalog registration, upload or submission was requested.

## SR-28 — Delivery — partial

**WHAT:** Deliver the editable source, generated runtime artifact and evidence with precise usage and fidelity documentation.

**HOW:** Document supported configurations, dependencies, tests, parameter provenance and known gaps beside the versioned release artifacts.

**Current evidence and remaining work:** Original and editable Blender sources, articulated USD, local preview and supporting reports are provided; physical correctness, target runtime and interactive USD behavior remain unverified.
