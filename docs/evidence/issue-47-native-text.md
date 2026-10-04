# Issue #47: bounded native text investigation

## Delivery and evidence boundary

[Issue #47](https://github.com/aigengame/aseprite-automation/issues/47) accepts an
evidence-backed Capability Gap when the investigated native paths cannot deliver
text. Installed `spa info` and `spa schema` report `native text rasterization`
through the existing `CapabilityGap` type. There is no text Descriptor, callable
command, request schema, successful text Result, or Plan Step.

The Gap identifies the selected Aseprite version separately from the retained
macOS baseline. It describes this SPA delivery and its evidence; discovery does
not run the text probes. The same Gap can therefore be reported on a different
installation without claiming that its native text behavior was tested. Linux
discovery validation is not Linux text-rasterization evidence.

Text authoring remains a product goal. A later accepted contract and verified
native path can extend this delivery. No permanent native impossibility, support
for every font or release, GUI fallback, Python renderer, or font registry follows
from this investigation. The conditional callable-operation acceptance in #47 is
not claimed by this Gap-only delivery. Source Sprite and Target Commit behavior
are unchanged because no mutation Operation is added.

## Retained observations from 2026-10-03

The installed macOS bundle was Aseprite 1.3.18.5; the Lua runtime reported
`app.version = 1.3.18.5-dev`, API 41, and `app.isUIAvailable = false`. The early
crash report recorded macOS 27.0 (26A428), ARM64. Each process used `--batch
--script`, a private prepared invocation with adjacent data resources, and isolated
preferences. A direct bundle-launch abort is a separate environment failure and
is not the text evidence.

The original input was a new transparent 96×32 RGB Sprite with one Cel,
`text = "SPA Test"`, white RGBA `(255,255,255,255)`, and position `(2,2)`.
PasteText received `ui=false`, `fontName=/System/Library/Fonts/Monaco.ttf`, and
`fontSize=12`. The font file existed. GraphicsContext received the same text,
color, and position; its public API offers no explicit font-file/size setters.
An assigned `text_tool.font_face` preference does not prove GraphicsContext uses
that font.

| Route | Process and pixel observation | Persistence observation |
| --- | --- | --- |
| PasteText, fresh preferences | Return code `-11` (SIGSEGV), 0.183 seconds; stdout/stderr empty. | No save/reopen observation; process crashed. |
| PasteText, `text_tool.font_face` set to the explicit font first | Return code `0`, 0.051 seconds; Lua call completed, Image bytes unchanged, zero nontransparent pixels. | Saved, closed, reopened: zero nontransparent pixels. |
| Image.context `fillText` / `measureText` | Lua call completed, Image bytes unchanged, zero nontransparent pixels; measured size `0×0`. | Saved, closed, reopened: zero nontransparent pixels. |

The crash stack was `FontInfo::getFromPreferences` →
`PasteTextCommand::onExecute` → `Context::executeCommand` → `Command_call`.
The report was named `aseprite-2026-10-03-012920.ips`, with capture time
`2026-10-03 01:29:19.6212 +0800`. The original temporary directory and `.ips` file
are no longer present. The exact input scripts, process JSON, pixel facts, and
stack above were recovered from retained tool output during implementation;
they are historical observations, not a repeated crash run. The graphics facts
survive, but its early process receipt was not retained in that excerpt.

A second retained GraphicsContext run at 20:13 used `"SPA"` at `(4,4)` in the
same-size RGB Image. It exited `0`, measured `0×0`, and contained zero text pixels
before and after save/reopen. A separate opaque `fillRect(4,4,3,2)` control
produced exactly six nontransparent pixels. The process emitted a macOS
notification diagnostic on stderr, so process success alone was not used as an
output claim.

## Source explanation

Source inspection is pinned to Aseprite commit
`375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9`. The source checkout and installed
executable are distinct evidence; the source does not prove binary provenance.

- [PasteText](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/src/app/commands/cmd_paste_text.cpp#L83-L127)
  reads font preferences before applying the explicit non-UI font parameters.
- [FontInfo](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/src/app/fonts/font_info.cpp#L106-L130)
  falls back to the main-window theme when no valid font preference exists.
- [render_text](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/src/app/util/render_text.cpp#L98-L108)
  returns no Image without the Fonts owner or a resolved font. PasteText returns
  without mutation when it receives no Image.
- [GraphicsContext](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/src/app/script/graphics_context.cpp#L61-L86)
  needs SkinTheme for text drawing and measurement; absent that owner, drawing does
  nothing and measurement is empty.

The [public GraphicsContext API](https://github.com/aseprite/api/blob/main/api/graphicscontext.md)
documents `fillText` and `measureText`. In the inspected source, PasteText is the
only caller of `render_text`; GraphicsContext supplies the other public scripted
text path. No usable independent public headless route was found in this bounded
search. This is not a proof about every possible native path or future release.

## Safe bounded reproduction

The retained [manual fixture](../../tests/paint/fixtures/native_text_probe.lua)
uses the original explicit inputs and seeds the font preference before PasteText.
It measures bytes and nontransparent pixels, saves/closes/reopens, and uses the
six-pixel rectangle control. It reports observations without asserting that a
future native runtime must remain blank. It is not called by pytest or production
discovery, and has no option to repeat the known fresh-preference crash.

From the repository root on macOS, choose the executable, an existing font file,
and a new output directory. The baseline used Monaco.ttf. Other fonts are new
investigations, not a promise established here.

```sh
export SPA_TEST_ASEPRITE=/absolute/path/to/Aseprite.app/Contents/MacOS/aseprite
export SPA_TEXT_FONT=/System/Library/Fonts/Monaco.ttf
export SPA_TEXT_PROBE_OUTPUT=/tmp/spa47-text-observation
uv run --frozen python - <<'PY'
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path

from spa.adapters.aseprite.invocation import prepare_invocation

font = Path(os.environ["SPA_TEXT_FONT"]).resolve(strict=True)
root = Path(os.environ["SPA_TEXT_PROBE_OUTPUT"]).resolve()
root.mkdir(parents=True, exist_ok=False)
binary = Path(os.environ["SPA_TEST_ASEPRITE"]).expanduser().resolve(strict=True)
resource = binary.parent.parent / "Resources/data/gui.xml"
assert resource.is_file(), "This reproduction uses a macOS app bundle"
fixture = Path("tests/paint/fixtures/native_text_probe.lua").resolve()
records = []
for kind in ("paste", "graphics"):
    work = root / kind
    work.mkdir()
    prepared = prepare_invocation(binary, resource, work)
    argv = [str(prepared.executable), "--batch",
            "--script-param", f"kind={kind}",
            "--script-param", f"font={font}",
            "--script-param", f"out={work / 'result.aseprite'}",
            "--script", str(fixture)]
    run = subprocess.run(argv, env=prepared.environment, text=True,
                         capture_output=True, check=False, timeout=30)
    facts = [json.loads(line.removeprefix("SPA47_PROBE="))
             for line in run.stdout.splitlines() if line.startswith("SPA47_PROBE=")]
    records.append(dict(kind=kind, argv=argv, returncode=run.returncode,
                        stdout=run.stdout, stderr=run.stderr, facts=facts))
receipt = dict(platform=platform.platform(),
               binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
               font=str(font), font_sha256=hashlib.sha256(font.read_bytes()).hexdigest(),
               records=records)
(root / "observations.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
PY
```

## Implementation recheck

The documented reproduction was run again on 2026-10-03 at 20:53 +0800 on macOS
27.0.1 ARM64. Both processes exited `0` and both commands completed. For each
route, initial, post-command, and reopened nontransparent counts were `0`, bytes
were unchanged, reopened bytes matched the initial bytes, and the control count
was `6`. GraphicsContext measured `0×0`. Both processes emitted the same macOS
notification diagnostic described above. The fresh-preference crash was not rerun.

- Executable SHA-256: `724f4cc88566c9d63013d1e9cca31d34ee7f9e12497ec07ae930aa6cafe63b7c`.
- Monaco.ttf SHA-256: `c6e990f6429fae28eb85321375dd335252f1122aa64c19fec553619a140724ef`.

These hashes identify the observed local inputs, not a runtime allowlist.

## Installed discovery regression

`tests/paint/test_e2e_text_discovery.py` runs real installed `info` and `schema`,
validates their typed results, checks retained evidence and selected-version
identity, and checks that no callable text entry or command schema exists.
`tests/paint/test_integration_text_discovery.py` separates baseline evidence from a
different selected version and checks that independently supported Paint remains
callable. These tests verify SPA discovery, not a permanent native text failure.

```sh
uv run --frozen --group test pytest tests/paint/test_e2e_text_discovery.py
uv run --frozen --group test pytest tests/paint/test_integration_text_discovery.py
```

Set `SPA_TEST_ASEPRITE` as in [the testing guide](../testing.md). To verify a clean
wheel installation, also set `SPA_TEST_INSTALLED_CLI` to its `bin/spa`. The text
discovery test uses that executable when supplied.
