extends RefCounted
## Consumer of the generated asset manifest. SPA Frame Numbers stay one-based here.

const BUNDLE_PATH := "res://content/wizard_assets/bundle.json"
const PHASE_NAMES := [&"idle", &"charge", &"cast", &"recover"]

var manifest: Dictionary = {}
var animations: Dictionary = {}
var _textures: Dictionary = {}
var _phases: Dictionary = {}


func load_bundle() -> String:
	if not FileAccess.file_exists(BUNDLE_PATH):
		return "Missing wizard_assets/bundle.json. Generate the SPA assets first."
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(BUNDLE_PATH))
	if not parsed is Dictionary or parsed.get("schema_version") != 1:
		return "The wizard asset manifest is not schema version 1."
	manifest = parsed
	var canvas: Dictionary = manifest.get("canvas", {})
	if float(canvas.get("width", 0)) != 128.0 or float(canvas.get("height", 0)) != 96.0:
		return "The wizard asset canvas must be 128 by 96 pixels."
	var frames: Array = manifest.get("frames", [])
	var phases: Array = manifest.get("phases", [])
	if frames.is_empty() or phases.size() != PHASE_NAMES.size():
		return "The asset manifest needs Frames and four animation Phases."
	var next_frame := 1
	for index in range(phases.size()):
		var phase: Dictionary = phases[index]
		var phase_name := StringName(phase.get("name", ""))
		if phase_name != PHASE_NAMES[index] or int(phase.get("from_frame", 0)) != next_frame:
			return "Animation Phases must cover idle, charge, cast, and recover in order."
		var last := int(phase.get("to_frame", 0))
		if last < next_frame or last > frames.size():
			return "An animation Phase has an invalid Frame Range."
		if bool(phase.get("loop", false)) != (phase_name == &"idle"):
			return "Only the idle Phase must loop."
		for source_number in range(next_frame, last + 1):
			var frame: Dictionary = frames[source_number - 1]
			if int(frame.get("frame_number", 0)) != source_number or float(frame.get("duration_ms", 0)) <= 0:
				return "A Frame Number or duration is invalid."
			if StringName(frame.get("phase", "")) != phase_name:
				return "A Frame does not match its animation Phase."
		_phases[phase_name] = phase
		next_frame = last + 1
	if next_frame != frames.size() + 1:
		return "Animation Phases do not cover every Frame."
	var cast_data: Dictionary = manifest.get("cast", {})
	var release := int(cast_data.get("release_frame", 0))
	if release < int(_phases[&"cast"]["from_frame"]) or release > int(_phases[&"cast"]["to_frame"]):
		return "The projectile release Frame must belong to the cast Phase."
	if not cast_data.get("muzzle") is Dictionary:
		return "The projectile muzzle anchor is missing."
	var components: Dictionary = manifest.get("components", {})
	for component_name in ["wizard", "background", "projectile", "target", "burst", "gem"]:
		if not components.get(component_name) is Dictionary:
			return "Missing asset component: %s." % component_name
		var component: Dictionary = components[component_name]
		var component_frames: Array = component.get("frames", [])
		var expected_count := 1 if component_name == "target" else frames.size()
		if component_frames.size() != expected_count:
			return "Unexpected Frame count for %s." % component_name
		var textures: Dictionary = {}
		for entry in component_frames:
			var relative_path := String(entry.get("path", ""))
			var path := BUNDLE_PATH.get_base_dir().path_join(relative_path)
			if relative_path.is_empty() or not ResourceLoader.exists(path):
				return "Missing imported texture: %s." % relative_path
			var texture := load(path) as Texture2D
			if texture == null:
				return "Cannot load texture: %s." % relative_path
			var size: Dictionary = component.get("size", {})
			if texture.get_width() != int(size.get("width", 0)) or texture.get_height() != int(size.get("height", 0)):
				return "Texture size does not match manifest: %s." % relative_path
			textures[int(entry.get("frame_number", 0))] = texture
		_textures[component_name] = textures
		if component_name != "target":
			var sprite_frames := SpriteFrames.new()
			sprite_frames.remove_animation(&"default")
			for phase_name in PHASE_NAMES:
				var phase: Dictionary = _phases[phase_name]
				sprite_frames.add_animation(phase_name)
				# duration_ms / 1000 fps gives the source duration in seconds.
				sprite_frames.set_animation_speed(phase_name, 1000.0)
				sprite_frames.set_animation_loop(phase_name, bool(phase["loop"]))
				for source_number in range(int(phase["from_frame"]), int(phase["to_frame"]) + 1):
					if not textures.has(source_number):
						return "Missing Frame %d in %s." % [source_number, component_name]
					sprite_frames.add_frame(phase_name, textures[source_number], float(frames[source_number - 1]["duration_ms"]))
			animations[component_name] = sprite_frames
	return ""


func anchor(component_name: String) -> Vector2:
	var point: Dictionary = manifest["components"][component_name]["anchor"]
	return Vector2(float(point["x"]), float(point["y"]))


func first_texture(component_name: String) -> Texture2D:
	return _textures[component_name].values()[0]


func source_frame(phase_name: StringName, native_index: int) -> int:
	return int(_phases[phase_name]["from_frame"]) + native_index


func muzzle() -> Vector2:
	var point: Dictionary = manifest["cast"]["muzzle"]
	return Vector2(float(point["x"]), float(point["y"]))


func release_frame() -> int:
	return int(manifest["cast"]["release_frame"])
