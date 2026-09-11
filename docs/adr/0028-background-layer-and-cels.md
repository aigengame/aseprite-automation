# ADR-0028: Preserve Background Layer lifecycle semantics

## Status

Accepted

Issues #10, #11, and #13 own exact feature contracts and acceptance.

## Context

Aseprite permits one Background Layer per Sprite. It is opaque and has one
full-canvas Cel at every Frame. Native conversion can create Cels, expand
Images, fill transparency, and normalize position and opacity. Native Cel
deletion also removes a transparent Cel but fills a Background Cel.

Mapping these behaviors to one generic mutation would make the same public verb
mean different lifecycle effects and could depend on hidden editor color state.

## Decision

- SPA preserves the single opaque Background Layer and its full-canvas,
  per-Frame Cel invariant.
- Conversion to and from Background is explicit rather than a hidden mode of a
  general Layer setter.
- Any Background fill uses an explicit compatible Color Value from the request,
  not an editor foreground/background preference.
- `cel remove` means that a Cel becomes absent and is invalid for a Background
  Cel.
- `cel clear` preserves the Cel. It clears a transparent Cel to transparency
  and fills a Background Cel with the explicit Background Color.
- Operations that add Frames or convert a Layer preserve the Background Cel
  invariant and report their observable native effects.

## Consequences

Layer conversion, Frame creation, and Cel lifecycle share one meaning for
Background content. A destructive or normalizing native effect cannot be hidden
behind deletion, an unrelated property update, or editor state.

## Rejected alternatives

Projecting native `deleteCel` directly would make removal mean either absence
or replacement pixels. Treating Background as a normal transparent Layer would
claim a state that Aseprite cannot persist faithfully.
