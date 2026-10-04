local root = assert(app.params.output)
local report = { runtime=tostring(app.version), api=app.apiVersion, cases={} }
local function record(name, fn)
  local ok, result = pcall(fn)
  report.cases[#report.cases+1] = {name=name, ok=ok, result=result}
  local f=assert(io.open(root..'/native.json','w')); f:write(json.encode(report)); f:close()
end
local function tsLayer(s,name)
  app.activeSprite=s
  assert(app.command.NewLayer{tilemap=true,ask=false,gridBounds=Rectangle(0,0,2,2)})
  local l=app.activeLayer; l.name=name; l.tileset.name=name
  return l,l.tileset
end
local function metadata(o,text)
  o.data=text; o.color=Color{r=1,g=2,b=3,a=200}
  o.properties.note=text
  o.properties('outside.spa').int64=9007199254740993
  o.properties('outside.spa').point=Point(3,-7)
  o.properties('outside.spa').binary=string.char(255,254)
end
local function observed(o)
  local p=o.properties('outside.spa').point
  return {data=o.data,color=o.color.rgbaPixel,note=o.properties.note,int64=o.properties('outside.spa').int64==9007199254740993,
    point=p~=nil and p.x==3 and p.y==-7,binary=o.properties('outside.spa').binary==string.char(255,254)}
end
local function fixture()
  local s=Sprite(8,8); local l,t=tsLayer(s,'selected'); t.baseIndex=77
  metadata(t,'tileset'); metadata(t:tile(0),'tile0')
  local tile=s:newTile(t); metadata(tile,'tile1'); tile.image:clear(app.pixelColor.rgba(50,90,120,255))
  local map=Image(1,1,ColorMode.TILEMAP); map:putPixel(0,0,1|0xe0000000)
  s:newCel(l,1,map,Point(-2,4)); return s,l,t
end
record('batch-layer-copy-paste',function()
  local s,l,t=fixture(); app.range.layers={l}
  local before_type=app.range.type
  local copy=app.command.Copy()
  local dest=Sprite(8,8); app.activeSprite=dest
  local paste=app.command.Paste()
  local out={range_type=before_type,copy=copy,paste=paste,layers=#dest.layers,tilesets=#dest.tilesets}
  if #dest.tilesets>0 then out.metadata=observed(dest.tilesets[1]); out.tile0=observed(dest.tilesets[1]:tile(0)); out.tile1=observed(dest.tilesets[1]:tile(1)) end
  dest:close(); s:close(); return out
end)
record('sprite-clone-and-tile0-restore',function()
  local s,l,t=fixture(); assert(s:saveAs(root..'/before.aseprite')); s:close(); s=assert(app.open(root..'/before.aseprite'))
  local source=s.tilesets[1]; local dup=Sprite(s); local target=dup.tilesets[1]
  local before={ts=observed(target),zero=observed(target:tile(0)),one=observed(target:tile(1)),base=target.baseIndex}
  local d0,c0=target:tile(0).data,target:tile(0).color
  app.activeSprite=dup
  assert(app.command.SpriteSize{ui=false,width=16,height=16,method='nearest-neighbor'})
  target=dup.tilesets[1]
  local resized={ts=observed(target),zero=observed(target:tile(0)),one=observed(target:tile(1)),base=target.baseIndex}
  target.baseIndex=source.baseIndex; target:tile(0).data=d0; target:tile(0).color=c0
  local restored={ts=observed(target),zero=observed(target:tile(0)),one=observed(target:tile(1)),base=target.baseIndex}
  assert(dup:saveAs(root..'/restored.aseprite')); dup:close(); dup=assert(app.open(root..'/restored.aseprite')); target=dup.tilesets[1]
  local reopened={ts=observed(target),zero=observed(target:tile(0)),one=observed(target:tile(1)),base=target.baseIndex}
  dup:close(); s:close(); return {before=before,resized=resized,restored=restored,reopened=reopened}
end)

record('tile0-opaque-default-properties',function()
  local s,l,t=fixture()
  t:tile(0).properties={zero_opaque='SPA45_NATIVE_TILE_ZERO_OPAQUE_SENTINEL',exact=9007199254740993}
  local before_getter={zero=t:tile(0).properties.zero_opaque,tileset=t.properties.zero_opaque}
  assert(s:saveAs(root..'/zero-before.aseprite')); s:close()
  s=assert(app.open(root..'/zero-before.aseprite')); t=s.tilesets[1]
  local d0,c0=t:tile(0).data,t:tile(0).color
  local copy=s:newTileset(t); copy.name='opaque-copy'; copy.baseIndex=t.baseIndex
  assert(s:saveAs(root..'/zero-clone.aseprite'))
  app.activeSprite=s
  assert(app.command.SpriteSize{ui=false,width=16,height=16,method='nearest-neighbor'})
  t=s.tilesets[1]; t.baseIndex=77; t:tile(0).data=d0; t:tile(0).color=c0
  assert(s:saveAs(root..'/zero-after-restored.aseprite')); s:close()
  s=assert(app.open(root..'/zero-after-restored.aseprite')); assert(s:saveAs(root..'/zero-after-reopened.aseprite')); s:close()
  return {getter=before_getter,native_file_markers='Verified by read-only Python byte search in markers.json',restored_data=d0,restored_color=c0.rgbaPixel}
end)
record('public-cross-sprite-transfer',function()
  local source,l,t=fixture(); local dest=Sprite(8,8)
  local clone_ok,clone_error=pcall(function() return dest:newTileset(t) end)
  local layer_ok,layer_error=pcall(function() l.parent=dest end)
  dest:close(); source:close()
  return {clone_ok=clone_ok,clone_error=tostring(clone_error),layer_ok=layer_ok,layer_error=tostring(layer_error)}
end)
