local palette = dofile(app.params.palette_real)
local original = palette.list
function palette.list(...)
  _G.SPA_TEST_PALETTE_CALLS = (_G.SPA_TEST_PALETTE_CALLS or 0) + 1
  if _G.SPA_TEST_PALETTE_CALLS == 2 then
    _G.SPA_TEST_NATIVE_EFFECT_OBSERVED = _G.SPA_TEST_TARGET.palettes[1]:getColor(1).red ~= 80
    error("injected post-filter Palette observation failure")
  end
  return original(...)
end
return palette
