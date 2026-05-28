# Device Pose & Hands template

A single self-contained HTML file (`DevicePoseAndHands.html`) that renders a 3D Three.js scene of the Aria glasses pose and hand skeleton. It uses an orbit camera (drag = rotate, wheel = zoom), supports six render styles (`wireframe`, `solid`, `xray`, `mesh`, `xrayMesh`, `dotted`), and consumes `vio` + `hand_tracking` messages over the Aria WebSocket on `ws://localhost:17300` (it also listens for the in-page `nebulaDataUpdate` event so it can be embedded inside a host that already owns the socket).

## Asset dependencies

`DevicePoseAndHands.html` loads the glasses geometry from sibling files in `../resources/`:

- `../resources/glasses.json` (preferred, baked + tonemapped)
- `../resources/aria-glasses.obj` (fallback raw mesh)

Keep `resources/` next to `device-pose-and-hands/` so the relative paths resolve when the file is dropped into `generated_components/<id>/component.html` (the loader walks two levels up to find the templates folder).

## When to use this template

Pick this template when the LLM-generated component needs to:

- Visualize the wearer's head pose in 3D (yaw/pitch/roll + position drift).
- Show live left/right hand skeletons co-located with the glasses model.
- Demonstrate AR / spatial overlays anchored to the device frame.

Avoid this template if the goal is purely 2D sensor charts — use `../stream-panels/StreamPanel.html` as a starting point instead.
