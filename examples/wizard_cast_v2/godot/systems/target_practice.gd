extends RefCounted
## Rules for a round of timed casts. Animation and collision are supplied by Content.

const CAST_LIMIT := 5

var phase: StringName = &"idle"
var casts := 0
var hits := 0
var outcomes := 0
var releases := 0
var projectile_pending := false
var complete := false
var _released_this_cast := false


func can_cast() -> bool:
	return phase == &"idle" and not projectile_pending and not complete and casts < CAST_LIMIT


func request_cast() -> bool:
	if not can_cast():
		return false
	casts += 1
	_released_this_cast = false
	phase = &"charge"
	return true


func finish_phase(finished: StringName) -> bool:
	if finished != phase:
		return false
	match phase:
		&"charge":
			phase = &"cast"
		&"cast":
			if not _released_this_cast:
				return false
			phase = &"recover"
		&"recover":
			phase = &"idle"
		_:
			return false
	_update_complete()
	return true


func release_projectile() -> bool:
	if phase != &"cast" or _released_this_cast:
		return false
	_released_this_cast = true
	projectile_pending = true
	releases += 1
	return true


func resolve_projectile(hit: bool) -> bool:
	if not projectile_pending:
		return false
	projectile_pending = false
	outcomes += 1
	if hit:
		hits += 1
	_update_complete()
	return true


func restart() -> bool:
	if not complete:
		return false
	phase = &"idle"
	casts = 0
	hits = 0
	outcomes = 0
	releases = 0
	projectile_pending = false
	complete = false
	_released_this_cast = false
	return true


func snapshot() -> Dictionary:
	return {
		"phase": String(phase),
		"casts": casts,
		"cast_limit": CAST_LIMIT,
		"hits": hits,
		"outcomes": outcomes,
		"releases": releases,
		"projectile_pending": projectile_pending,
		"complete": complete,
		"can_cast": can_cast(),
	}


func _update_complete() -> void:
	complete = casts == CAST_LIMIT and outcomes == CAST_LIMIT and phase == &"idle"
