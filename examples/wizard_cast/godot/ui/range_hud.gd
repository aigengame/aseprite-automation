extends CanvasLayer
## Native controls present Content state and send player actions back to Content.

const WizardRange = preload("res://content/wizard_range.gd")
const INK := Color("e8dcbb")
const TEAL := Color("70c9b0")
const DIM := Color("aaa3b0")

var _range: WizardRange
var _root := Control.new()
var _score: Label
var _status: Label
var _cast_button: Button
var _feedback: Label
var _feedback_time := 0.0
var _results: Panel
var _result_text: Label
var _error_panel: Panel
var _error_text: Label
var _state: Dictionary = {}


func _ready() -> void:
	layer = 1
	_root.name = "Controls"
	_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.theme = _theme()
	add_child(_root)
	_panel(_root, Rect2(0, 0, 128, 15), Color("111626"))
	_label(_root, "MOONLIT PRACTICE", Rect2(4, 1, 86, 11), 8, INK)
	_score = _label(_root, "", Rect2(91, 3, 34, 9), 6, TEAL)
	_score.name = "Score"
	_panel(_root, Rect2(0, 83, 128, 13), Color("111626"))
	_status = _label(_root, "SPACE / CAST to begin", Rect2(3, 85, 85, 9), 6, INK)
	_status.name = "Status"
	_cast_button = _button(_root, "CAST", Rect2(91, 84, 34, 11), _cast)
	_feedback = _label(_root, "", Rect2(78, 17, 48, 13), 9, TEAL)
	_feedback.name = "Feedback"
	_feedback.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_results = _panel(_root, Rect2(18, 23, 92, 54), Color("141e32"))
	_results.name = "Results"
	_label(_results, "ROUND COMPLETE", Rect2(6, 4, 82, 10), 7, TEAL)
	_result_text = _label(_results, "", Rect2(6, 16, 80, 17), 7, INK)
	_result_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_button(_results, "AGAIN", Rect2(7, 38, 40, 11), _restart)
	_button(_results, "QUIT", Rect2(51, 38, 34, 11), _quit)
	_results.hide()
	_error_panel = _panel(_root, Rect2(5, 20, 118, 60), Color("141e32"))
	_error_panel.name = "AssetError"
	_label(_error_panel, "ASSETS UNAVAILABLE", Rect2(5, 4, 108, 10), 7, Color("ffb58a"))
	_error_text = _label(_error_panel, "", Rect2(5, 17, 108, 29), 6, INK)
	_error_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_button(_error_panel, "QUIT", Rect2(40, 46, 38, 11), _quit)
	_error_panel.hide()


func bind(range_node: WizardRange) -> void:
	_range = range_node
	_range.state_changed.connect(_present)
	_range.feedback.connect(_show_feedback)
	_present(_range.snapshot())


func _present(state: Dictionary) -> void:
	_state = state
	_score.text = "%d/%d HITS" % [state["hits"], state["cast_limit"]]
	_cast_button.disabled = not state["can_cast"]
	_results.visible = state["complete"]
	_error_panel.visible = not String(state["error"]).is_empty()
	_error_text.text = state["error"]
	if state["complete"]:
		_result_text.text = "%d / %d hits\n%s" % [state["hits"], state["cast_limit"], "Perfect timing!" if state["hits"] == state["cast_limit"] else "Read the rhythm."]
		_status.text = "R / AGAIN to restart"
	elif not state["loaded"]:
		_status.text = "Generate the SPA bundle"
	else:
		match state["phase"]:
			"charge":
				_status.text = "CAST %d/%d  -  CHARGING" % [state["casts"], state["cast_limit"]]
			"cast":
				_status.text = "CAST %d/%d  -  RELEASE" % [state["casts"], state["cast_limit"]]
			"recover":
				_status.text = "CAST %d/%d  -  RECOVER" % [state["casts"], state["cast_limit"]]
			_:
				_status.text = "SPACE / CAST  -  %d LEFT" % (state["cast_limit"] - state["casts"])


func _unhandled_key_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	var key: int = event.physical_keycode if event.physical_keycode != 0 else event.keycode
	match key:
		KEY_SPACE:
			_cast()
		KEY_R, KEY_ENTER:
			if _state.get("complete", false):
				_restart()
		KEY_ESCAPE:
			_quit()
		_:
			return
	get_viewport().set_input_as_handled()


func _process(delta: float) -> void:
	_feedback_time = maxf(0, _feedback_time - delta)
	_feedback.visible = _feedback_time > 0 and not _results.visible


func _cast() -> void:
	if _range != null:
		_range.request_cast()


func _restart() -> void:
	if _range != null and _range.restart():
		_feedback_time = 0


func _quit() -> void:
	get_tree().quit()


func _show_feedback(message: String, hit: bool) -> void:
	_feedback.text = message
	_feedback.modulate = TEAL if hit else Color("f1ac86")
	_feedback_time = 0.8


func _theme() -> Theme:
	var theme := Theme.new()
	theme.default_font_size = 7
	theme.set_color("font_color", "Button", INK)
	theme.set_color("font_disabled_color", "Button", DIM)
	for state_name in ["normal", "hover", "pressed", "disabled", "focus"]:
		var style := StyleBoxFlat.new()
		style.bg_color = Color("29414b") if state_name != "disabled" else Color("252737")
		if state_name == "hover" or state_name == "pressed":
			style.bg_color = Color("3b655f")
		style.content_margin_left = 2
		style.content_margin_right = 2
		style.content_margin_top = 0
		style.content_margin_bottom = 0
		theme.set_stylebox(state_name, "Button", style)
	return theme


func _panel(parent: Node, bounds: Rect2, color: Color) -> Panel:
	var panel := Panel.new()
	panel.position = bounds.position
	panel.size = bounds.size
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = color
	panel.add_theme_stylebox_override("panel", style)
	parent.add_child(panel)
	return panel


func _label(parent: Node, text: String, bounds: Rect2, font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	label.position = bounds.position
	label.size = bounds.size
	return label


func _button(parent: Node, text: String, bounds: Rect2, callback: Callable) -> Button:
	var button := Button.new()
	button.name = text.capitalize()
	button.text = text
	button.focus_mode = Control.FOCUS_NONE
	button.pressed.connect(callback)
	parent.add_child(button)
	# Apply bounds after the small UI theme supplies the intrinsic minimum size.
	button.position = bounds.position
	button.size = bounds.size
	return button
