-- Read encoded profile identity; Aseprite remains the color engine.
local module = {}
-- Aseprite 1.3.18.5 saves None by omitting the Color Profile chunk, but
-- app.open() assigns sRGB to that old-file form. Read only this file fact.
function module.declared_profile(source_file)
  local file = assert(io.open(source_file, "rb"), "could not read Source Sprite File")
  local ok, result, icc_color_space = pcall(function()
    local header = assert(file:read(128), "incomplete Sprite header")
    local file_size, magic, frames = string.unpack("<I4I2I2", header)
    assert(magic == 0xa5e0 and frames > 0, "invalid Sprite header")
    local actual_size = assert(file:seek("end"))
    assert(file_size <= actual_size, "incomplete Source Sprite File")
    local frame_at = 128
    local observed = nil
    local observed_icc_space = nil
    for _ = 1, frames do
      assert(frame_at + 16 <= file_size, "incomplete Sprite Frame")
      assert(file:seek("set", frame_at))
      local frame_header = assert(file:read(16))
      local frame_size, frame_magic, old_chunks, _, new_chunks =
        string.unpack("<I4I2I2I2xxI4", frame_header)
      assert(frame_magic == 0xf1fa and frame_size >= 16, "invalid Sprite Frame")
      local frame_end = frame_at + frame_size
      assert(frame_end <= file_size, "incomplete Sprite Frame")
      local chunks = old_chunks == 0xffff and new_chunks or old_chunks
      local chunk_at = frame_at + 16
      for _ = 1, chunks do
        assert(chunk_at + 6 <= frame_end, "incomplete Sprite chunk")
        assert(file:seek("set", chunk_at))
        local chunk_header = assert(file:read(6))
        local chunk_size, chunk_type = string.unpack("<I4I2", chunk_header)
        assert(chunk_size >= 6 and chunk_at + chunk_size <= frame_end, "invalid Sprite chunk")
        if chunk_type == 0x2007 then
          assert(chunk_size >= 22, "incomplete Color Profile chunk")
          local profile_type, flags = string.unpack("<I2I2", assert(file:read(4)))
          -- A gamma flag changes both None and sRGB to a gamma Color Space.
          assert(flags == 0, "unsupported Source Sprite Color Profile")
          local kind = profile_type == 0 and "none"
            or profile_type == 1 and "srgb"
            or profile_type == 2 and "icc"
            or "unsupported"
          assert(observed == nil or observed == kind, "conflicting Color Profile chunks")
          if kind == "icc" then
            assert(chunk_size >= 46, "incomplete ICC profile header")
            assert(file:seek("set", chunk_at + 22))
            local icc_size = string.unpack("<I4", assert(file:read(4)))
            assert(icc_size >= 20 and icc_size <= chunk_size - 26, "incomplete ICC profile")
            assert(file:seek("cur", 16))
            local space = assert(file:read(4))
            assert(
              observed_icc_space == nil or observed_icc_space == space,
              "conflicting ICC color spaces"
            )
            observed_icc_space = space
          end
          observed = kind
        end
        chunk_at = chunk_at + chunk_size
      end
      frame_at = frame_end
    end
    return observed or "none", observed_icc_space
  end)
  file:close()
  if not ok then error(result) end
  return result, icc_color_space
end

return module
