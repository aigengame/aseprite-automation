-- Small SHA-256 implementation for deterministic native Image content digests.
local module = {}

local constants = {
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
  0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
  0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
  0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
  0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
}

local function u32(value)
  return value & 0xffffffff
end

local function rotate_right(value, count)
  return u32((value >> count) | (value << (32 - count)))
end

local function transform(state, block)
  local words = {}
  for index = 0, 15 do
    local offset = index * 4 + 1
    words[index] = string.unpack(">I4", block, offset)
  end
  for index = 16, 63 do
    local previous = words[index - 15]
    local s0 = rotate_right(previous, 7) ~ rotate_right(previous, 18)
      ~ (previous >> 3)
    previous = words[index - 2]
    local s1 = rotate_right(previous, 17) ~ rotate_right(previous, 19)
      ~ (previous >> 10)
    words[index] = u32(words[index - 16] + s0 + words[index - 7] + s1)
  end

  local a, b, c, d = state[1], state[2], state[3], state[4]
  local e, f, g, h = state[5], state[6], state[7], state[8]
  for index = 0, 63 do
    local sum1 = rotate_right(e, 6) ~ rotate_right(e, 11) ~ rotate_right(e, 25)
    local choice = (e & f) ~ ((~e) & g)
    local temp1 = u32(h + sum1 + choice + constants[index + 1] + words[index])
    local sum0 = rotate_right(a, 2) ~ rotate_right(a, 13) ~ rotate_right(a, 22)
    local majority = (a & b) ~ (a & c) ~ (b & c)
    local temp2 = u32(sum0 + majority)
    h, g, f, e = g, f, e, u32(d + temp1)
    d, c, b, a = c, b, a, u32(temp1 + temp2)
  end
  state[1] = u32(state[1] + a)
  state[2] = u32(state[2] + b)
  state[3] = u32(state[3] + c)
  state[4] = u32(state[4] + d)
  state[5] = u32(state[5] + e)
  state[6] = u32(state[6] + f)
  state[7] = u32(state[7] + g)
  state[8] = u32(state[8] + h)
end

function module.hex(message)
  local state = {
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  }
  local bit_length = #message * 8
  local padding = "\128" .. string.rep("\0", (55 - #message) % 64)
  local high = math.floor(bit_length / 0x100000000)
  local low = bit_length & 0xffffffff
  local padded = message .. padding .. string.pack(">I4I4", high, low)
  for offset = 1, #padded, 64 do
    transform(state, padded:sub(offset, offset + 63))
  end
  local parts = {}
  for index = 1, 8 do
    parts[index] = string.format("%08x", state[index])
  end
  return table.concat(parts)
end

return module
