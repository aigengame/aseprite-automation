extends SceneTree


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	if FileAccess.file_exists("res://content/wizard_assets/bundle.json"):
		printerr("Run this check only before asset generation, or in a copy without bundle.json.")
		quit(2)
		return
	var scene := load("res://main.tscn") as PackedScene
	var game := scene.instantiate()
	root.add_child(game)
	await process_frame
	var range_node := game.get_node("Range")
	var state: Dictionary = range_node.snapshot()
	var hud := game.get_node("HUD")
	var passed: bool = not state["loaded"] and not state["can_cast"] and hud._error_panel.visible and not String(state["error"]).is_empty()
	print(JSON.stringify({"visible_asset_error": passed, "message": state["error"]}))
	game.queue_free()
	await process_frame
	print("MISSING_ASSETS_COMPLETE")
	quit(0 if passed else 1)
