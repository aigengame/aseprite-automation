extends Node
## Composition root. Content does not load or instantiate the UI.

const WizardRange = preload("res://content/wizard_range.gd")
const RangeHud = preload("res://ui/range_hud.gd")


func _ready() -> void:
	get_window().min_size = Vector2i(384, 288)
	var range_node := WizardRange.new()
	range_node.name = "Range"
	add_child(range_node)
	var hud := RangeHud.new()
	hud.name = "HUD"
	add_child(hud)
	hud.bind(range_node)
