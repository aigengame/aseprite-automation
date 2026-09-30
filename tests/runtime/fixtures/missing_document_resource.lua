local ok, message = pcall(dofile, assert(app.params.consumer))
assert(not ok, "Missing dependency must fail module loading")
local expected = "Missing Kernel resource: " .. assert(app.params.missing)
assert(tostring(message):find(expected, 1, true), tostring(message))
