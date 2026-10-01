local digest = dofile(app.params.digest_real)
local original = digest.image_content
function digest.image_content(...)
  _G.SPA_TEST_DIGEST_CALLS = (_G.SPA_TEST_DIGEST_CALLS or 0) + 1
  if _G.SPA_TEST_DIGEST_CALLS == 2 then
    _G.SPA_TEST_NATIVE_EFFECT_OBSERVED = _G.SPA_TEST_TARGET.layers[1]:cel(1).image.bytes
      ~= _G.SPA_TEST_INITIAL_IMAGE_BYTES
    error("injected post-filter image observation failure")
  end
  return original(...)
end
return digest
