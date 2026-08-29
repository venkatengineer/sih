class_name FleetManager
extends Node3D

var amr_scene = preload("res://scenes/amr/amr.tscn")
var grid_manager: Node3D = null

func _ready() -> void:
	var main_scene = get_tree().current_scene
	if main_scene:
		grid_manager = main_scene.get_node_or_null("Navigation/GridManager")
	
	spawn_initial_fleet()

func spawn_initial_fleet() -> void:
	# 1. AMR-01 (Inbound Loop along West Corridor & Aisle 01)
	var amr1 = _instantiate_amr("AMR-01", Vector3(-20, 0, 0), true)
	var path1: Array[Vector3] = [
		Vector3(-20, 0, 0),
		Vector3(-20, 0, 14),
		Vector3(-9, 0, 14),
		Vector3(-9, 0, -16),
		Vector3(-20, 0, -16),
		Vector3(-20, 0, 0)
	]
	amr1.call("set_waypoints", _sanitize_path(path1))

	# 2. AMR-02 (Outbound Loop along West Corridor & Aisle 01)
	var amr2 = _instantiate_amr("AMR-02", Vector3(-20, 0, -6), true)
	var path2: Array[Vector3] = [
		Vector3(-20, 0, -6),
		Vector3(-20, 0, -16),
		Vector3(-9, 0, -16),
		Vector3(-9, 0, 14),
		Vector3(-20, 0, 14),
		Vector3(-20, 0, -6)
	]
	amr2.call("set_waypoints", _sanitize_path(path2))

	# 3. AMR-03 (Central Main Transit Loop along Central Corridor & Aisle 03)
	var amr3 = _instantiate_amr("AMR-03", Vector3(0, 0, -16), false)
	var path3: Array[Vector3] = [
		Vector3(0, 0, -16),
		Vector3(0, 0, 14),
		Vector3(9, 0, 14),
		Vector3(9, 0, -16),
		Vector3(0, 0, -16)
	]
	amr3.call("set_waypoints", _sanitize_path(path3))

	# 4. AMR-04 (East Charging Transit Loop along East Corridor & Aisle 03)
	var amr4 = _instantiate_amr("AMR-04", Vector3(20, 0, 14), false)
	var path4: Array[Vector3] = [
		Vector3(20, 0, 14),
		Vector3(20, 0, -16),
		Vector3(9, 0, -16),
		Vector3(9, 0, 14),
		Vector3(20, 0, 14)
	]
	amr4.call("set_waypoints", _sanitize_path(path4))

func _instantiate_amr(id: String, spawn_pos: Vector3, carries_cargo: bool) -> Node3D:
	var amr = amr_scene.instantiate() as Node3D
	amr.set("robot_id", id)
	amr.position = spawn_pos
	add_child(amr)
	if amr.has_method("set_has_cargo"):
		amr.call("set_has_cargo", carries_cargo)
	return amr

func _sanitize_path(raw_path: Array[Vector3]) -> Array[Vector3]:
	# Validates that all waypoints map to walkable grid cells
	var clean_path: Array[Vector3] = []
	for wp in raw_path:
		if grid_manager and grid_manager.has_method("world_to_grid") and grid_manager.has_method("grid_to_world"):
			var cell = grid_manager.call("world_to_grid", wp) as Vector2i
			# Snap waypoint to clean center of grid cell
			var clean_wp = grid_manager.call("grid_to_world", cell, 0.0) as Vector3
			clean_path.append(clean_wp)
		else:
			clean_path.append(wp)
	return clean_path
