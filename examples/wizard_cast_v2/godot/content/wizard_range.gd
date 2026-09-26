extends Node2D
## Authored range: connect the source animation to casts and moving targets.

signal state_changed(state: Dictionary)
signal feedback(message: String, hit: bool)

const RoundRules = preload("res://systems/target_practice.gd")
const WizardBundle = preload("res://content/wizard_bundle.gd")
const WIZARD_FOOT := Vector2(102, 234)
const TARGET_X := 324.0
const TARGET_CENTER_OFFSET_Y := 25.0
const TARGET_AMPLITUDE := 28.0
const TARGET_ANGULAR_SPEED := 2.4
const PROJECTILE_SPEED := 300.0
const MISS_X := 420.0

var _rules = RoundRules.new()
var _bundle = WizardBundle.new()
var _world: Node2D
var _wizard: AnimatedSprite2D
var _background: AnimatedSprite2D
var _projectile: AnimatedSprite2D
var _burst: AnimatedSprite2D
var _target: Sprite2D
var _target_time := 0.0
var _projectile_position := Vector2.ZERO
var _target_position := Vector2.ZERO
var _target_center_y := 0.0
var _target_radius := 0.0
var _projectile_radius := 0.0
var _shake_time := 0.0
var _error := ""
var _loaded := false


func _ready() -> void:
	_error = _bundle.load_bundle()
	if not _error.is_empty():
		state_changed.emit(snapshot())
		return
	_target_center_y = WIZARD_FOOT.y + _bundle.muzzle().y + TARGET_CENTER_OFFSET_Y
	_target_radius = _bundle.component_size("target").x * 0.35
	_projectile_radius = _bundle.component_size("projectile").y / 6.0
	_world = Node2D.new()
	_world.name = "World"
	add_child(_world)
	_background = _animated_component("background", Vector2.ZERO)
	_wizard = _animated_component("wizard", WIZARD_FOOT)
	_target = Sprite2D.new()
	_target.name = "Target"
	_target.texture = _bundle.first_texture("target")
	_target.centered = false
	_target.offset = -_bundle.anchor("target")
	_world.add_child(_target)
	_projectile = _animated_component("projectile", Vector2.ZERO)
	_projectile.sprite_frames.set_animation_loop(&"cast", true)
	_projectile.hide()
	_burst = _animated_component("burst", Vector2.ZERO)
	_burst.hide()
	_burst.animation_finished.connect(_burst.hide)
	_wizard.frame_changed.connect(_on_wizard_frame)
	_wizard.animation_finished.connect(_on_phase_finished)
	_loaded = true
	_update_target()
	_play_phase()
	state_changed.emit(snapshot())


func request_cast() -> bool:
	if not _loaded or not _rules.request_cast():
		return false
	_play_phase()
	state_changed.emit(snapshot())
	return true


func restart() -> bool:
	if not _loaded or not _rules.restart():
		return false
	_target_time = 0.0
	_shake_time = 0.0
	_world.position = Vector2.ZERO
	_projectile.hide()
	_burst.hide()
	_update_target()
	_play_phase()
	state_changed.emit(snapshot())
	return true


func snapshot() -> Dictionary:
	var state: Dictionary = _rules.snapshot()
	state["loaded"] = _loaded
	state["error"] = _error
	state["can_cast"] = _loaded and _rules.can_cast()
	state["source_frame"] = _bundle.source_frame(_wizard.animation, _wizard.frame) if _loaded else 0
	state["target_position"] = {"x": _target_position.x, "y": _target_position.y}
	state["target_time"] = _target_time
	state["target_center_y"] = _target_center_y
	state["target_radius"] = _target_radius
	state["projectile_radius"] = _projectile_radius
	state["projectile_position"] = {"x": _projectile_position.x, "y": _projectile_position.y}
	return state


func _physics_process(delta: float) -> void:
	if not _loaded:
		return
	var previous_target := _target_position
	if not _rules.complete:
		_target_time += delta
		_update_target()
	if _rules.projectile_pending:
		var previous_projectile := _projectile_position
		_projectile_position.x += PROJECTILE_SPEED * delta
		_projectile.position = _projectile_position.round()
		# A relative sweep catches collisions between physics ticks for both movers.
		var relative_start := previous_projectile - previous_target
		var relative_end := _projectile_position - _target_position
		var closest := Geometry2D.get_closest_point_to_segment(Vector2.ZERO, relative_start, relative_end)
		if closest.length_squared() <= pow(_target_radius + _projectile_radius, 2):
			_resolve_shot(true)
		elif _projectile_position.x > MISS_X:
			_resolve_shot(false)
	_shake_time = maxf(0.0, _shake_time - delta)
	_world.position = Vector2(1 if int(_shake_time * 60.0) % 2 == 0 else -1, 0) if _shake_time > 0 else Vector2.ZERO


func _animated_component(component_name: String, anchor_position: Vector2) -> AnimatedSprite2D:
	var sprite := AnimatedSprite2D.new()
	sprite.name = component_name.capitalize()
	sprite.sprite_frames = _bundle.animations[component_name]
	sprite.centered = false
	sprite.offset = -_bundle.anchor(component_name)
	sprite.position = anchor_position
	_world.add_child(sprite)
	return sprite


func _update_target() -> void:
	_target_position = Vector2(TARGET_X, _target_center_y + sin(_target_time * TARGET_ANGULAR_SPEED) * TARGET_AMPLITUDE)
	_target.position = _target_position.round()


func _play_phase() -> void:
	_wizard.play(_rules.phase)
	# Explicitly handle a release at the first Frame of a Phase as well.
	_on_wizard_frame()


func _on_wizard_frame() -> void:
	if not _loaded:
		return
	_background.animation = _wizard.animation
	_background.set_frame_and_progress(_wizard.frame, _wizard.frame_progress)
	var source_number: int = _bundle.source_frame(_wizard.animation, _wizard.frame)
	if source_number == _bundle.release_frame() and _rules.release_projectile():
		_projectile_position = WIZARD_FOOT + _bundle.muzzle()
		_projectile.position = _projectile_position.round()
		_projectile.show()
		_projectile.play(&"cast")
		_shake_time = 0.12
		state_changed.emit(snapshot())


func _on_phase_finished() -> void:
	if _rules.finish_phase(_wizard.animation):
		_play_phase()
		state_changed.emit(snapshot())


func _resolve_shot(hit: bool) -> void:
	if not _rules.resolve_projectile(hit):
		return
	_projectile.hide()
	_projectile.stop()
	if hit:
		_burst.position = _target_position.round()
		_burst.show()
		_burst.stop()
		_burst.play(&"cast")
	feedback.emit("HIT!" if hit else "MISS", hit)
	state_changed.emit(snapshot())
