extends SceneTree

const RoundRules = preload("res://systems/target_practice.gd")
var _checks := 0
var _failures: Array[String] = []


func _init() -> void:
	var round_state = RoundRules.new()
	check(round_state.can_cast(), "A new round accepts a cast")
	check(not round_state.restart(), "Restart cannot erase an active round")
	check(not round_state.release_projectile(), "Idle cannot release a projectile")
	check(not round_state.resolve_projectile(true), "A hit needs a released projectile")
	for shot in range(RoundRules.CAST_LIMIT):
		check(round_state.request_cast(), "Idle admits cast %d" % (shot + 1))
		check(not round_state.request_cast(), "Charge rejects repeated input")
		check(not round_state.release_projectile(), "Charge cannot release early")
		check(not round_state.finish_phase(&"cast"), "An old phase event cannot advance charge")
		check(round_state.finish_phase(&"charge"), "Charge advances to cast")
		check(not round_state.request_cast(), "Cast rejects repeated input")
		check(not round_state.finish_phase(&"cast"), "Cast cannot finish before release")
		check(round_state.release_projectile(), "Cast releases one projectile")
		check(not round_state.release_projectile(), "A repeated release event is ignored")
		check(round_state.finish_phase(&"cast"), "Released cast advances to recovery")
		check(not round_state.request_cast(), "Recovery rejects repeated input")
		if shot == RoundRules.CAST_LIMIT - 1:
			check(round_state.finish_phase(&"recover"), "Last recovery can finish before flight")
			check(not round_state.complete, "The final unresolved flight delays the result")
			check(not round_state.request_cast(), "No sixth cast while final flight is pending")
			check(not round_state.restart(), "No restart before the final outcome")
			check(round_state.resolve_projectile(false), "The last flight resolves as a miss")
		else:
			check(round_state.resolve_projectile(shot % 2 == 0), "Each flight resolves")
			check(not round_state.resolve_projectile(true), "A second collision cannot score")
			check(not round_state.can_cast(), "A resolved projectile does not skip recovery")
			check(round_state.finish_phase(&"recover"), "Recovery unlocks the next cast")
	check(round_state.complete, "Five resolved casts finish the round")
	check(round_state.hits == 2, "Only two real hits contribute to score")
	check(round_state.releases == 5, "Exactly five projectiles were released")
	check(not round_state.request_cast(), "Results reject a sixth cast")
	check(round_state.restart(), "Results allow restart")
	check(round_state.casts == 0 and round_state.hits == 0, "Restart clears the score")
	check(round_state.can_cast(), "Restart enables the first cast")
	print(JSON.stringify({"checks": _checks, "failures": _failures}))
	print("ROUND_RULES_COMPLETE")
	quit(0 if _failures.is_empty() else 1)


func check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures.append(message)
