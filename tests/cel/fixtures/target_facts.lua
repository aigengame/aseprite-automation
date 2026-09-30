-- Nested identity fixture; the root and nested Image Layers share a name.
local sprite = Sprite(6, 4, ColorMode.RGB)
sprite.useLayerUuids = true
local decoy = sprite.layers[1]
decoy.name = "ink"
sprite:deleteCel(decoy, 1)
local outer = sprite:newGroup()
outer.name = "outer"
local inner = sprite:newGroup()
inner.name = "inner"
inner.parent = outer
local ink = sprite:newLayer()
ink.name = "ink"
ink.parent = inner
local image = Image(2, 2, ColorMode.RGB)
image:clear(app.pixelColor.rgba(30, 40, 50, 255))
local cel = sprite:newCel(ink, 1, image, Point(2, 1))
cel.opacity = 210
cel.zIndex = 2
assert(sprite:saveAs(app.params.out))
sprite:close()
