local sprite = assert(app.open(app.params.source))
local layer = sprite.layers[1]
local first = assert(layer:cel(1))
local second = assert(layer:cel(2))
local result = { linked = first.image == second.image }
local out = assert(io.open(app.params.out, "wb"))
out:write(json.encode(result))
out:close()
sprite:close()
