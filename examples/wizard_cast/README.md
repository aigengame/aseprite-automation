# Wizard casting tracer

This maintained example uses the installed public SPA CLI to author reusable pixel
assets, then uses gda and Godot to exercise them in spell target practice.
[Issue #19](https://github.com/aigengame/aseprite-automation/issues/19) owns the
delivery contract. The example is a downstream consumer, outside SPA production modules.

## Component proof

The first executable slice creates three Frames, changes one independent Image from
5×5 to 7×7 with an explicit pivot, varies Cel position and opacity, normalizes a
copied Sprite, and exports transparent PNG Frames with a fixed anchor.

Run from the repository root, with an installed SPA executable and a new output path:

```sh
python -m examples.wizard_cast.probe \
  --spa /path/to/installed/bin/spa \
  --aseprite /path/to/aseprite \
  --output /tmp/wizard-component-proof
```

`operations.jsonl` records public requests, results, and elapsed time. `evidence.json`
links the PNGs. Pixel validation uses independently decoded PNGs in
`tests/examples/test_e2e_wizard_probe.py`.

## Ownership

The finite recipe owns art inputs and sampled poses. SPA owns Aseprite mutation,
persistence, and PNG export. The Godot consumer owns gameplay and presentation.
One layered tracer Sprite supplies derived component assets. Local pose offsets,
scene shake, and projectile world movement remain separate so an exported component
can be reused at another position. Normalize position before cropping: SPA crop
removes pixels outside its rectangle.

Linked Cels share Image, position, and opacity. Use copy/unlink before independent
Frame changes. Compose only Descriptor-eligible Steps in Plans; sequence other
public Operations explicitly. No raw Lua authoring path substitutes for SPA.

## Delivery stages

1. Prove component geometry, transparency, and a real Godot import.
2. Complete the four-phase wizard and reusable component bundle.
3. Finish target practice, real input checks, and a macOS player package.
4. Record deterministic rebuild evidence, tool feedback, and visual review status.

Human visual acceptance remains separate from automated structure and pixel checks.
