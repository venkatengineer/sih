class_name FleetManager
extends Node3D

var amr_scene = preload("res://scenes/amr/amr.tscn")
var grid_manager: Node3D = null
var pathfinder: Node3D = null

var is_obstacle_active: bool = false
var test_obstacle_cell: Vector2i = Vector2i(12, 10) # Central aisle cell at Vector3(0,0,0)

func _ready() -> void:
	var main_scene = get_tree().current_scene
	if main_scene:
		grid_manager = main_scene.get_node_or_null("Navigation/GridManager")
		pathfinder = main_scene.get_node_or_null("Navigation/AStarPathfinder")

	# Ensure AStarPathfinder is initialized
	if pathfinder and pathfinder.has_method("initialize") and grid_manager:
		pathfinder.call("initialize", grid_manager)

	spawn_initial_fleet()

func spawn_initial_fleet() -> void:
	var pickup_pos = Vector3(-18, 0, 12)
	var dropoff_pos = Vector3(-18, 0, -12)
	var charging_pos = Vector3(18, 0, -12)
	var north_intersection = Vector3(0, 0, -16)

	if grid_manager:
		var p_list = grid_manager.call("get_pickup_points") as Array
		if p_list.size() > 0: pickup_pos = p_list[0]

		var d_list = grid_manager.call("get_dropoff_points") as Array
		if d_list.size() > 0: dropoff_pos = d_list[0]

		var c_list = grid_manager.call("get_charging_points") as Array
		if c_list.size() > 0: charging_pos = c_list[0]

	# 1. AMR-01: Cyan Route -> Pickup Station
	var amr1 = _instantiate_amr("AMR-01", Vector3(-20, 0, 0), true, Color(0.1, 0.9, 0.8))
	amr1.set("current_task", "PICKUP_CARGO")
	amr1.call("navigate_to_target", pickup_pos)

	# 2. AMR-02: Purple Route -> Dropoff Station
	var amr2 = _instantiate_amr("AMR-02", Vector3(-20, 0, -6), true, Color(0.75, 0.35, 0.95))
	amr2.set("current_task", "DELIVER_DROPOFF")
	amr2.call("navigate_to_target", dropoff_pos)

	# 3. AMR-03: Amber Route -> North Intersection
	var amr3 = _instantiate_amr("AMR-03", Vector3(20, 0, 0), false, Color(0.95, 0.65, 0.1))
	amr3.set("current_task", "PATROL_NORTH")
	amr3.call("navigate_to_target", north_intersection)

	# 4. AMR-04: Blue Route -> Charging Dock
	var amr4 = _instantiate_amr("AMR-04", Vector3(20, 0, 6), false, Color(0.1, 0.65, 1.0))
	amr4.set("current_task", "RECHARGE")
	amr4.call("navigate_to_target", charging_pos)

func _instantiate_amr(id: String, spawn_pos: Vector3, carries_cargo: bool, p_color: Color) -> Node3D:
	var amr = amr_scene.instantiate() as Node3D
	amr.set("robot_id", id)
	amr.set("path_color", p_color)
	amr.position = spawn_pos
	add_child(amr)
	if amr.has_method("set_has_cargo"):
		amr.call("set_has_cargo", carries_cargo)
	return amr

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_O:
			toggle_test_obstacle()

func toggle_test_obstacle() -> void:
	is_obstacle_active = not is_obstacle_active
	if grid_manager and grid_manager.has_method("set_dynamic_obstacle"):
		grid_manager.call("set_dynamic_obstacle", test_obstacle_cell, is_obstacle_active)
		print("FleetManager: Dynamic obstacle at cell ", test_obstacle_cell, " set to ", is_obstacle_active)
