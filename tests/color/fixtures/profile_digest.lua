local digest = dofile(app.params.digest)
local function read(path)
  local file = assert(io.open(path, "rb"))
  local bytes = assert(file:read("a"))
  file:close()
  return bytes
end
local result = {}
for _, path in ipairs(json.decode(read(app.params.source))) do
  result[#result + 1] = digest.sha256(read(path))
end
print(json.encode { sha256 = result })
