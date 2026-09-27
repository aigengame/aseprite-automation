std = "lua54"

-- Globals supplied by Aseprite's embedded scripting environment and used here.
read_globals = {
  "AniDir",
  "BlendMode",
  "Color",
  "ColorMode",
  "ColorSpace",
  "FlipType",
  "Image",
  "ImageSpec",
  "Palette",
  "Point",
  "Rectangle",
  "Selection",
  "Sprite",
  "SpriteSheetDataFormat",
  "SpriteSheetType",
  "TilesetMode",
  "json",
}

-- Aseprite scripts also assign to app's mutable editor state.
globals = { "app" }
