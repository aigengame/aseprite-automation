-- Fast deterministic digests for bounded mutation evidence.
local module = {}
local fnv_offset_basis = -3750763034362895579
local fnv_prime = 1099511628211

-- SHA-256 identifies the complete ICC input without retaining a reference copy.
-- All arithmetic is explicitly reduced to 32 bits on Lua's 64-bit integers.
local sha256_constants = {
  0x428a2f98,
  0x71374491,
  0xb5c0fbcf,
  0xe9b5dba5,
  0x3956c25b,
  0x59f111f1,
  0x923f82a4,
  0xab1c5ed5,
  0xd807aa98,
  0x12835b01,
  0x243185be,
  0x550c7dc3,
  0x72be5d74,
  0x80deb1fe,
  0x9bdc06a7,
  0xc19bf174,
  0xe49b69c1,
  0xefbe4786,
  0x0fc19dc6,
  0x240ca1cc,
  0x2de92c6f,
  0x4a7484aa,
  0x5cb0a9dc,
  0x76f988da,
  0x983e5152,
  0xa831c66d,
  0xb00327c8,
  0xbf597fc7,
  0xc6e00bf3,
  0xd5a79147,
  0x06ca6351,
  0x14292967,
  0x27b70a85,
  0x2e1b2138,
  0x4d2c6dfc,
  0x53380d13,
  0x650a7354,
  0x766a0abb,
  0x81c2c92e,
  0x92722c85,
  0xa2bfe8a1,
  0xa81a664b,
  0xc24b8b70,
  0xc76c51a3,
  0xd192e819,
  0xd6990624,
  0xf40e3585,
  0x106aa070,
  0x19a4c116,
  0x1e376c08,
  0x2748774c,
  0x34b0bcb5,
  0x391c0cb3,
  0x4ed8aa4a,
  0x5b9cca4f,
  0x682e6ff3,
  0x748f82ee,
  0x78a5636f,
  0x84c87814,
  0x8cc70208,
  0x90befffa,
  0xa4506ceb,
  0xbef9a3f7,
  0xc67178f2,
}

local function rotate_right(value, bits)
  return ((value >> bits) | (value << (32 - bits))) & 0xffffffff
end

function module.sha256(bytes)
  local padded = bytes
    .. "\128"
    .. string.rep("\0", (55 - #bytes) % 64)
    .. string.pack(">I8", #bytes * 8)
  local hash = {
    0x6a09e667,
    0xbb67ae85,
    0x3c6ef372,
    0xa54ff53a,
    0x510e527f,
    0x9b05688c,
    0x1f83d9ab,
    0x5be0cd19,
  }
  for offset = 1, #padded, 64 do
    local words = {}
    for i = 1, 16 do
      words[i] = string.unpack(">I4", padded, offset + (i - 1) * 4)
    end
    for i = 17, 64 do
      local x, y = words[i - 15], words[i - 2]
      local s0 = rotate_right(x, 7) ~ rotate_right(x, 18) ~ (x >> 3)
      local s1 = rotate_right(y, 17) ~ rotate_right(y, 19) ~ (y >> 10)
      words[i] = (words[i - 16] + s0 + words[i - 7] + s1) & 0xffffffff
    end
    local a, b, c, d, e, f, g, h = table.unpack(hash)
    for i = 1, 64 do
      local s1 = rotate_right(e, 6) ~ rotate_right(e, 11) ~ rotate_right(e, 25)
      local choose = (e & f) ~ (~e & g)
      local t1 = (h + s1 + choose + sha256_constants[i] + words[i]) & 0xffffffff
      local s0 = rotate_right(a, 2) ~ rotate_right(a, 13) ~ rotate_right(a, 22)
      local majority = (a & b) ~ (a & c) ~ (b & c)
      local t2 = (s0 + majority) & 0xffffffff
      h, g, f, e, d, c, b, a = g, f, e, (d + t1) & 0xffffffff, c, b, a, (t1 + t2) & 0xffffffff
    end
    local block = { a, b, c, d, e, f, g, h }
    for i = 1, 8 do
      hash[i] = (hash[i] + block[i]) & 0xffffffff
    end
  end
  return string.format("%08x%08x%08x%08x%08x%08x%08x%08x", table.unpack(hash))
end

function module.fnv1a64(...)
  local hash = fnv_offset_basis
  for argument = 1, select("#", ...) do
    local value = select(argument, ...)
    for offset = 1, #value do
      hash = (hash ~ string.byte(value, offset)) * fnv_prime
    end
  end
  return string.format("%016x", hash)
end

function module.image_content(image, color_mode)
  local header = table.concat({
    color_mode,
    ":",
    image.width,
    "x",
    image.height,
    ":",
    image.bytesPerPixel,
    ":",
    image.rowStride,
    ":",
  })
  return { algorithm = "fnv1a64", value = module.fnv1a64(header, image.bytes) }
end

return module
