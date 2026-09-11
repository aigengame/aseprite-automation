# ADR-0094: Fix the native Export Image operation order

## Status

Accepted

## Context

The accepted `export image` request combines several native Aseprite capabilities on
one disposable Sprite: Frame and Layer rendering, rectangular Export Image Area,
Assign or Convert Color Profile, Palette preparation, Change Color Mode, Background
behavior, and File Format encoding. These steps are not generally commutative.

Converting a Color Profile after Indexed quantization can map and dither colors in the
wrong profile. Applying Background before the final Color Mode or Color Profile makes
the declared Background Color ambiguous and can transform it after the caller chose
it. Allowing the encoder to choose conversions recreates the warning-driven and
preference-dependent behavior that the typed request is intended to remove.

SPA therefore needs one operation-owned order. It does not need a configurable
workflow engine: every accepted branch already has one defined role in producing the
single requested static raster Artifact.

## Decision

- `spa export image` executes exactly these functional steps in order:
  1. render the requested Frame, Layer Composition, and Export Image Area into one
     disposable Sprite;
  2. apply the declared Color Profile branch;
  3. when Change Color Mode targets Indexed, perform the declared Palette preparation;
  4. apply the declared Change Color Mode branch;
  5. apply the declared transparency branch; and
  6. invoke the declared File Format encoder.
- Rendering establishes the exact pixel content and rectangular dimensions on which
  every later step operates. Later steps never return to the Source Sprite or render
  a different Layer/Frame selection.
- `color_profile.preserve`, `omit`, and `assign` do not change pixel values.
  `color_profile.convert` performs Aseprite's native pixel and Palette transformation
  before any later quantization, Dithering, or grayscale mapping.
- Palette preparation exists only when a requested Change Color Mode to Indexed needs
  it. It observes the rendered, profile-adjusted disposable Sprite and completes
  before the shared Change Color Mode handler consumes the resulting Palette.
- Change Color Mode completes before transparency handling. A Background Color is
  therefore a Color Value in the final Color Mode and effective Color Profile. SPA
  never interprets it in the Source Sprite's representation and converts it later.
- `transparency.preserve` verifies that the final selected pixels and declared File
  Format can retain the applicable Alpha Channel, Transparent Color Index, and Palette
  Entry alpha. `transparency.background` applies native Background behavior before
  encoding. The encoder never resolves transparency by warning and continuing.
- File Format encoding is terminal. The encoder receives the final disposable Sprite
  and cannot perform an undeclared Color Profile, Palette, Color Mode, or Background
  conversion on SPA's behalf.
- The fixed sequence is an `export image` application-use-case contract. The Python
  Application Layer validates and resolves the applicable branches, selects and
  orders the packaged Kernel capabilities, constructs one private structured
  execution, invokes Aseprite, and manages response, verification, and Artifact
  publication.
- The Lua Kernel remains the sole authority for every core step. It dispatches the
  selected packaged handlers against the same disposable Sprite in one Aseprite
  process and owns all native rendering, profile, Palette, Dithering, Color Mode,
  Background, and encoder semantics. Python may schedule and compose those handlers;
  it cannot implement their algorithms or silently change this accepted semantic
  order. A future evidence-backed order change updates this decision, the descriptor,
  Application Layer orchestration, Kernel bindings, and tests together.
- This sequence is private operation structure, not a caller-configurable pipeline,
  Operation Plan, stage registry, plug-in seam, or intermediate Artifact model. The
  request contains semantic choices but no step list, ordering controls, repeat count,
  conditional execution, or partial output.
- A failure in any step prevents final Artifact publication and leaves the Source
  Sprite unchanged under the accepted Export Destination behavior. No intermediate
  Sprite or file becomes a returned Artifact.
- Results report the requested and effective facts for each applicable step in this
  order, plus the final encoded File Format facts and Artifact. An inapplicable step is
  identified by its request branch rather than represented as an executed no-op.
- Evidence for a File Format slice must distinguish this order from meaningful adjacent
  swaps and independently verify the final output. The owning feature issue defines the
  concrete acceptance matrix for that slice.

## Consequences

- Color Profile conversion, Palette mapping, Dithering, and Background composition
  have one reproducible interpretation.
- Each native capability retains its own accepted contract while the Application
  Layer composes packaged handlers through one private in-process execution.
- Agent requests stay semantic and compact instead of encoding an execution graph.
- File Format slices can validate one known input state at the encoder boundary.
- Every File Format slice validates the same accepted order without inheriting another
  format's support claims.

## Rejected alternatives

### Let the caller order export steps

It creates a workflow language, permits semantically invalid permutations, and makes
each File Format test a combinatorial pipeline test.

### Change Color Mode before Color Profile

RGB-to-Indexed mapping and Dithering would run on values interpreted in the source
profile instead of the requested output profile.

### Apply Background before Color Profile or Color Mode

The explicit Background Color would be interpreted in an earlier representation and
then transformed, contradicting its final-output meaning.

### Let the encoder perform necessary conversions

Aseprite can warn, discard information, return truthy success without a file, or read
preferences. Those effects are not an explicit agent contract.

### Model each step as an Operation Plan

Export Operations are not Plan Steps, the disposable Sprite is private, and the
caller has no need to observe or mutate intermediate state.
