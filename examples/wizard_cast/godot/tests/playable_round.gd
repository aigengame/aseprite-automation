extends SceneTree
## Exercise the real scene, imported textures, native animation, and input path.

const WizardBundle = preload("res://content/wizard_bundle.gd")
const WizardRange = preload("res://content/wizard_range.gd")
var _checks := 0
var _failures: Array[String] = []
var _releases: Array[int] = []
var _last_release_count := 0


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var scene := load("res://main.tscn") as PackedScene
	var game := scene.instantiate()
	root.add_child(game)
	await process_frame
	var range_node := game.get_node("Range")
	var hud := game.get_node("HUD")
	var state: Dictionary = range_node.snapshot()
	check(state["loaded"], "The real SPA bundle must load: %s" % state["error"])
	if not state["loaded"]:
		await finish(game)
		return
	var bundle = WizardBundle.new()
	check(bundle.load_bundle().is_empty(), "The bundle is reusable by an independent consumer")
	var wizard: AnimatedSprite2D = range_node.get_node("World/Wizard")
	var background: AnimatedSprite2D = range_node.get_node("World/Background")
	for phase in bundle.manifest["phases"]:
		var animation := StringName(phase["name"])
		var source_duration := 0.0
		var native_duration := 0.0
		for number in range(int(phase["from_frame"]), int(phase["to_frame"]) + 1):
			source_duration += float(bundle.manifest["frames"][number - 1]["duration_ms"]) / 1000.0
		for frame in range(wizard.sprite_frames.get_frame_count(animation)):
			native_duration += wizard.sprite_frames.get_frame_duration(animation, frame) / wizard.sprite_frames.get_animation_speed(animation)
		check(is_equal_approx(source_duration, native_duration), "%s uses source Frame durations" % animation)
	range_node.state_changed.connect(_observe)
	# Wait for real target timing, then use normal input. Do not inject outcomes.
	var expected_hits := 0
	for shot in range(5):
		check(range_node.snapshot()["can_cast"], "Cast %d becomes available" % (shot + 1))
		var should_hit := shot % 2 == 0
		check(await wait_for_timing(range_node, bundle, should_hit), "A normal input window becomes available")
		if should_hit:
			expected_hits += 1
		if shot == 0:
			await push_click(hud.get_node("Controls/Cast").get_global_rect().get_center())
		else:
			push_key(KEY_SPACE)
		await process_frame
		check(range_node.snapshot()["casts"] == shot + 1, "Native input starts cast %d" % (shot + 1))
		push_key(KEY_SPACE)
		await process_frame
		check(range_node.snapshot()["casts"] == shot + 1, "Repeated Space does not spend another cast")
		var deadline := Time.get_ticks_msec() + 7000
		while not range_node.snapshot()["can_cast"] and not range_node.snapshot()["complete"] and Time.get_ticks_msec() < deadline:
			await process_frame
		check(range_node.snapshot()["outcomes"] == shot + 1, "The projectile resolves before the next cast")
		check(range_node.snapshot()["hits"] == expected_hits, "Timed input produces the expected hit or miss")
		check(background.animation == wizard.animation and background.frame == wizard.frame, "Background follows the source Frame")
		print("CAST_%d_COMPLETE %s" % [shot + 1, JSON.stringify(range_node.snapshot())])
	state = range_node.snapshot()
	check(state["complete"], "Five casts show the result after recovery")
	check(state["hits"] > 0 and state["hits"] < 5, "Actual target motion produces both a hit and a miss")
	check(state["releases"] == 5 and _releases.size() == 5, "Exactly five projectiles were released")
	for source_number in _releases:
		check(source_number == bundle.release_frame(), "Projectile release matches the source Frame")
	check(hud._results.visible, "The result panel is visible")
	push_key(KEY_SPACE)
	await process_frame
	check(range_node.snapshot()["casts"] == 5, "Space cannot fire a sixth cast")
	push_key(KEY_R)
	await process_frame
	state = range_node.snapshot()
	check(state["casts"] == 0 and state["hits"] == 0 and state["can_cast"], "R restarts a clean round")
	check(not hud._results.visible, "Restart hides the result panel")
	await finish(game)


func push_key(key: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = key
	event.pressed = true
	root.push_input(event, true)
	event = InputEventKey.new()
	event.keycode = key
	event.pressed = false
	root.push_input(event, true)


func push_click(point: Vector2) -> void:
	var move := InputEventMouseMotion.new()
	move.position = point
	move.global_position = point
	root.push_input(move, true)
	await process_frame
	for pressed in [true, false]:
		var event := InputEventMouseButton.new()
		event.button_index = MOUSE_BUTTON_LEFT
		event.position = point
		event.global_position = point
		event.pressed = pressed
		root.push_input(event, true)
		await process_frame


func wait_for_timing(range_node: Node, bundle: RefCounted, should_hit: bool) -> bool:
	var muzzle: Vector2 = WizardRange.WIZARD_FOOT + bundle.muzzle()
	var delay := 0.0
	for frame in bundle.manifest["frames"]:
		if frame["phase"] != "idle" and int(frame["frame_number"]) < bundle.release_frame():
			delay += float(frame["duration_ms"]) / 1000.0
	delay += (WizardRange.TARGET_X - muzzle.x) / WizardRange.PROJECTILE_SPEED
	var deadline := Time.get_ticks_msec() + 4000
	while Time.get_ticks_msec() < deadline:
		var arrival_time: float = range_node.snapshot()["target_time"] + delay
		var arrival_y: float = WizardRange.TARGET_CENTER_Y + sin(arrival_time * WizardRange.TARGET_ANGULAR_SPEED) * WizardRange.TARGET_AMPLITUDE
		var separation := absf(arrival_y - muzzle.y)
		if (should_hit and separation <= 1.0) or (not should_hit and separation >= 17.0):
			return true
		await process_frame
	return false


func _observe(state: Dictionary) -> void:
	if int(state["releases"]) > _last_release_count:
		_releases.append(int(state["source_frame"]))
		_last_release_count = int(state["releases"])


func check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)


func finish(game: Node) -> void:
	game.queue_free()
	await process_frame
	print(JSON.stringify({"checks": _checks, "failures": _failures, "release_frames": _releases}))
	print("PLAYABLE_ROUND_COMPLETE")
	quit(0 if _failures.is_empty() else 1)
