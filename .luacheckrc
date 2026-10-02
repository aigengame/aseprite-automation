std = "lua54"

-- Globals supplied by Aseprite's embedded scripting environment and used here.
read_globals = {
  "AniDir",
  "BlendMode",
  "Brush",
  "BrushType",
  "Ink",
  "MouseButton",
  "TilemapMode",
  "Color",
  "ColorMode",
  "ColorSpace",
  "FilterChannels",
  "FlipType",
  "Grid",
  "Image",
  "ImageSpec",
  "Palette",
  "Point",
  "Rectangle",
  "Selection",
  "SelectionMode",
  "Sprite",
  "SpriteSheetDataFormat",
  "SpriteSheetType",
  "TilesetMode",
  "Uuid",
  "json",
}

-- Aseprite scripts also assign to app's mutable editor state.
globals = { "app" }
