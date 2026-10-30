# seca Scale-up Ultra — Blender and OpenUSD simulation studies

A measuring station, built to explore. This editable Blender reconstruction brings together the glass platform, handrail, ultrasonic column and ID display of the seca Scale-up Ultra, then adds a set of interactive studies that let you move through the experience of using it. A separate SimReady-style OpenUSD 3D model adds provisional wheel and display joints for simulation studies.

Change a weight, place a virtual subject beneath the measuring head, try the touchscreen, or tilt and move the station through a scene. The project combines detailed product modeling with approachable simulations of the systems around it—making it as interesting to investigate as it is to render.

[Start in Blender](#start-exploring) · [Explore the OpenUSD study](#openusd-and-simready-style-study) · [Read the assumptions](simready/ASSUMPTIONS.md)

![Full render of the Blender measuring station](images/01-overview.png)

*Product images are renders of the reconstruction; diagrams and motion previews are labeled as studies.*

## Start exploring

1. Open [`model/seca-scale-up-ultra.blend`](model/seca-scale-up-ultra.blend) in **Blender 5.2.2**.
2. In the **Text Editor**, select the embedded `seca_simulator.py`, inspect it, and choose **Run Script** (**Alt+P**).
3. In the 3D View, open the sidebar (**N**) and choose the **seca study** tab. If the calibration study is not complete, keep the scale unloaded, choose **Start calibration study**, and follow the prompts to confirm the area is clear, scan the empty platform, place the study rod and remove it again.
4. Set a synthetic weight and height, choose **Step on**, wait for the weight to stabilize, then choose **Measure height**. After the measurement, use **Accept height** on the review screen and **Step off** to finish.
5. To interact with the display in the viewport, choose **Enable 3D screen touch** in the sidebar, then press and release a control on the screen; dragging away cancels the press, and **Esc** exits touch mode.

The project opens with editable geometry and materials; running the script brings the interactive study controls to life. Try switching the **Height source** to **Single-ray phantom**, **Six-ray phantom study**, or **Adjustable echo fan study** to see different ways of exploring the height measurement.

## OpenUSD and SimReady-style study

The [articulated OpenUSD model](simready/asset/seca_scale_up_ultra_articulated/usd/seca_scale_up_ultra_articulated.usda) separates the station into five modeled rigid links with four revolute joints and 42 collision proxies. It is a starting point for robotics and physics-simulation exploration, with an [editable Blender copy](simready/source/seca-articulation-editable.blend) alongside it.

To open it, clone or download the repository, keep the adjacent `layers` folder with the USD, and open the root `.usda` in an OpenUSD application. Blender can import the visual scene through **File → Import → Universal Scene Description**; physics support depends on the application. The original [interactive Blender model](model/seca-scale-up-ultra.blend) remains available separately. See the [USD study guide](simready/README.md) for controls, dependencies and tests.

| USD visual geometry | USD collision proxies |
| :---: | :---: |
| [![Rendered OpenUSD visual geometry of the seca measuring station](simready/previews/articulated-overview.png)](simready/previews/articulated-overview.png) | [![Rendered guide-purpose collision proxies for the base, rail, wheels and display](simready/previews/usd-collision-proxies.png)](simready/previews/usd-collision-proxies.png) |

The proxy view uses blue for the base, orange for the wheels and teal for the display links. It shows the simplified collision shapes, not a measurement of the real device.

![Animation of the modeled display swiveling and tilting](simready/previews/display-articulation.gif)

*The preview manually poses the imported USD visuals; it is not a physics simulation or a recording of a physical unit.*

![Five rigid-body links: a base connected to two wheels and a display swivel, with a display tilt attached to the swivel](simready/previews/usd-joint-graph.png)

[Open the link graph at full size](simready/previews/usd-joint-graph.png).

The manufacturer lists a 29 kg total mass; the per-link masses, pivots, friction and display limits are estimates. The wheels use X-axis rotation; the display study limits are ±0.6 radians about Z and ±0.4 radians about X. The unpowered display reached its modeled tilt stop in a local gravity test, and the optional centering-drive layer has not been validated in PhysX. The main asset passes the **Robotics-Prop 4.0.0 static validation profile**; Isaac Sim, RTX, physical-device behavior and the NVIDIA runtime benchmark remain unverified. Read the [assumptions](simready/ASSUMPTIONS.md), [validation evidence](simready/README.md#evidence) and [remaining backlog](simready/BACKLOG-STATUS.md) before using the model for a simulation study.

## A closer look at the experience

### A touchscreen you can use

The display is built from editable Blender objects, with screen elements and touch regions that move with the display assembly. Explore a guided measurement or the staged self-measurement flow, review a height result, try the tare assistant and mother/child sequence, and open supported settings. Press feedback and drag-to-cancel make it possible to interact with the screen directly in the 3D view.

The study also includes synthetic voice and beeps, standby, fictional patient and user IDs, a mock scanner, and a local mock transfer with success, failure and retry scenarios. These are contained within the Blender study: no real scanner, patient record or network connection is used.

![Touchscreen render](images/03-touchscreen.png)

### Height measurement, from rays to a result

The measurement study connects the modeled sensor head, a virtual subject and the platform surface. Choose a numeric height or one of three geometry-based modes:

- **Single-ray phantom** casts a ray from the modeled head toward the phantom and compares the hit with the evaluated platform surface.
- **Six-ray phantom study** casts one ray from each of six modeled openings, combines valid readings in pairs and reports the number of valid pairs and their spread.
- **Adjustable echo fan study** sends a fan of geometric rays from each opening, scores first hits using adjustable study parameters such as reflectivity, angle, distance, attenuation and temperature, and combines the selected readings into a height estimate.

Move or resize the phantom, adjust the study parameters, and use **Sample echo fan** to explore how the result changes. The fan is a geometric approximation for experimentation, not an acoustic wave simulation or a reconstruction of seca's sensor algorithm.

![Underside of the modeled ultrasonic head](images/04-sensor-head.png)

### Weight, setup and movement

The scale study accepts a synthetic gross weight and can apply an adjustable motion signal and filter before reporting a stable reading. Try tare, pre-tare, hold and recall, or switch between weight and height units. A separate calibration sequence provides a way to explore setup before taking a height reading.

The station is built from separate editable parts, including the glass platform and illuminated markings, rail, column, display mount, wheels, feet, rear guard and schematic cables. Move the display, open the column-cover study to look at the modeled cable channel, or use the transport controls to tilt and move the station along an arc. The materials and lighting are set up for product renders, with separate finishes for glass, metal, white surfaces and the darker base.

![Glass platform, markings, handrail and wheel details](images/02-platform.png)

## Go deeper

Run `seca_simulator.py` first, then run these additional embedded scripts from the Text Editor to open their panels in the **seca study** sidebar:

- **`load_study.py`** explores an idealized four-support load distribution, including a configurable amount of force through the rail, and can apply its synthetic reading to the scale study.
- **`level_study.py`** lets you adjust the feet and an assumed floor tilt, with a visual bubble and displayed roll, pitch and foot gaps.
- **`clearance_study.py`** samples a transport arc against modeled obstacles using conservative proxy envelopes.
- **`display_fit_study.py`** checks selected modeled display surfaces for crossings with the rail, bridge or column at the current pose.

These are exploratory studies with adjustable assumptions. Re-run a check after changing the pose or geometry; a result is not a continuous motion or physical clearance assessment.

## How it was made

The reconstruction was built around the 654 platform, 455 handrail and standard 257 ultrasonic column using published specifications, product images and assembly and operation illustrations. Separate meshes, curves, controls and material nodes keep the model open to inspection and further work. Approximate camera comparisons helped shape the visible parts, while the interface and study scripts connect the modeled components to fictional inputs and results.

This is an independent, reference-informed interpretation rather than manufacturer CAD or firmware. The visual construction, movements, materials and simulated measurements have not been calibrated against a physical unit. For example, the selected v77 reconstruction measured **801 × 582.7 × 2387 mm** in its saved pose; seca publishes **801 × 650 × 2387 mm** for the configured device, and the 67.3 mm depth difference remains unresolved. See [modeling and fidelity](docs/MODELING-AND-FIDELITY.md), the [depth registration study](simready/research/depth-registration.png), and the [source index](docs/SOURCES.md) for the details.

The project is for visualization and exploration, not clinical use. seca and its product names are trademarks of their respective owners; this project is not affiliated with or endorsed by seca. Manufacturer images, manuals and Revit files are linked as references rather than redistributed here.

## Licenses

Original project scripts are offered under the [MIT License](LICENSE); the original model and project-created renders are offered under [CC BY 4.0](licenses/CC-BY-4.0.txt), limited to rights held by their contributors. The packed DejaVu font and synthetic Flite audio retain their [own notices](licenses/). These grants do not license seca trademarks or third-party reference materials; see [NOTICE.md](NOTICE.md).
