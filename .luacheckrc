std = "lua54"

-- Globals supplied by Aseprite's embedded scripting environment and used here.
read_globals = {
  "AniDir",
  "BlendMode",
  "Color",
  "ColorMode",
  "ColorSpace",
  "Image",
  "Palette",
  "Point",
  "Rectangle",
  "Sprite",
  "SpriteSheetDataFormat",
  "SpriteSheetType",
  "TilesetMode",
  "json",
}

-- Aseprite scripts also assign to app's mutable editor state.
globals = { "app" }
