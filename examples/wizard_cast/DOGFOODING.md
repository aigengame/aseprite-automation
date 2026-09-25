# Tool feedback

Evidence comes from the workflow in this directory. Record a demonstrated failure or
measured obstacle before classifying it. Tool versions and exact build inputs belong
in each run's evidence. Local sandbox restrictions are environment findings unless
a supported tool contract is violated.

| ID | Tool / task | Observation and impact | Classification / disposition |
| --- | --- | --- | --- |
| SPA-WIZ-01 | SPA / procedural Paint | The public limit is 256 addressed pixels per Paint request and 64 eligible Steps per Plan. The recipe splits canonical runs and uses existing Plans. Full-scene command count and elapsed time will determine whether this is material authoring friction. | Declared limit; measurement pending. Native drawing is already tracked by #26. |
| SPA-WIZ-02 | SPA / reusable component export | PNG export selects one Frame and all visible Layers. Isolating components requires a copied Sprite, Layer visibility changes, position normalization, fixed crop, and per-Frame export. | Enhancement candidate; relate measured cost to #59 and #49. |

## Required evidence for a new finding

Record the tool/version, workflow step, expected and observed result, exact input or
command, evidence path, impact, workaround cost, and disposition. A bug violates an
existing contract. An enhancement improves an existing capability. A feature adds
a demonstrated missing capability. Link an existing issue when it owns that work.
