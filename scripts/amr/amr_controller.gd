class_name AMRController
extends Node3D

enum RobotState {
	MOVING = 0,
	WAITING = 1,
	BLOCKED = 2,
	CHARGING = 3,
	REROUTING = 4
}

@export var robot_id: String = "AMR-01"
@export var move_speed: float = 3.2
@export var turn_speed: float = 6.0
@export var loop_waypoints: bool = false
@export var show_debug_path: bool = true
@export var path_color: Color = Color(0.1, 0.9, 0.55)

var battery_level: float = 100.0
var current_state: RobotState = RobotState.MOVING
var current_task: String = "IDLE"
var current_grid_cell: Vector2i = Vector2i.ZERO
var target_destination_world: Vector3 = Vector3.ZERO
var waypoints: Array[Vector3] = []
var current_waypoint_index: int = 0
var has_cargo: bool = false

var grid_manager: Node3D = null
var pathfinder: Node3D = null
var path_visualizer: Node3D = null
var visualizer_script = preload("res://scripts/path_visualizer.gd")

@onready var label_3d: Label3D = get_node_or_null("Label3D") as Label3D
@onready var status_led_mesh: MeshInstance3D = get_node_or_null("Body/StatusLED") as MeshInstance3D
@onready var status_light: OmniLight3D = get_node_or_null("Body/StatusLight") as OmniLight3D
@onready var cargo_box: Node3D = get_node_or_null("Body/CargoBox") as Node3D

func _ready() -> void:
	var main_scene = get_tree().current_scene
	if main_scene:
		grid_manager = main_scene.get_node_or_null("Navigation/GridManager")
		pathfinder = main_scene.get_node_or_null("Navigation/AStarPathfinder")

	# Setup 3D Path Visualizer in global world space (top_level = true)
	if visualizer_script:
		path_visualizer = visualizer_script.new() as Node3D
		path_visualizer.name = "PathVisualizer_" + robot_id
		path_visualizer.set("top_level", true) # Independent global world transform!
		path_visualizer.set("is_enabled", show_debug_path)
		add_child(path_visualizer)

	# Connect obstacle listener
	if grid_manager and grid_manager.has_signal("obstacle_changed"):
		grid_manager.connect("obstacle_changed", Callable(self, "_on_obstacle_changed"))

	if label_3d:
		label_3d.text = robot_id

	set_has_cargo(has_cargo)
	update_status_visuals()

func set_waypoints(new_waypoints: Array[Vector3]) -> void:
	waypoints = new_waypoints
	current_waypoint_index = 0
	if waypoints.size() > 0:
		target_destination_world = waypoints[waypoints.size() - 1]
	if path_visualizer and show_debug_path and path_visualizer.has_method("draw_path"):
		path_visualizer.call("draw_path", waypoints, path_color)

func navigate_to_target(target_world_pos: Vector3) -> bool:
	target_destination_world = target_world_pos
	if not pathfinder or not pathfinder.has_method("calculate_world_path"):
		push_warning("AMRController: Pathfinding component unavailable.")
		return false

	set_robot_state(RobotState.REROUTING)
	var path: Array[Vector3] = pathfinder.call("calculate_world_path", global_position, target_destination_world)

	if path.size() > 0:
		set_waypoints(path)
		set_robot_state(RobotState.MOVING)
		return true
	else:
		waypoints.clear()
		if path_visualizer and path_visualizer.has_method("clear_path"):
			path_visualizer.call("clear_path")
		set_robot_state(RobotState.BLOCKED)
		return false

func set_robot_state(new_state: RobotState) -> void:
	current_state = new_state
	update_status_visuals()

func set_has_cargo(enabled: bool) -> void:
	has_cargo = enabled
	if cargo_box:
		cargo_box.visible = has_cargo

func update_status_visuals() -> void:
	var color = Color(0.1, 0.9, 0.4) # MOVING
	match current_state:
		RobotState.WAITING: color = Color(0.95, 0.8, 0.1)
		RobotState.BLOCKED: color = Color(0.95, 0.2, 0.1)
		RobotState.CHARGING: color = Color(0.1, 0.6, 1.0)
		RobotState.REROUTING: color = Color(0.7, 0.25, 0.95)

	if status_light:
		status_light.light_color = color

	if status_led_mesh:
		var mat = status_led_mesh.material_override as StandardMaterial3D
		if mat:
			mat.albedo_color = color
			mat.emission = color

func _on_obstacle_changed(cell: Vector2i, is_blocked: bool) -> void:
	# Update pathfinder internal solid state
	if pathfinder and pathfinder.has_method("set_obstacle_solid"):
		pathfinder.call("set_obstacle_solid", cell, is_blocked)

	# If currently moving, check if our planned route is affected by this cell change
	if current_state == RobotState.MOVING or current_state == RobotState.WAITING:
		var route_affected = false
		if grid_manager and grid_manager.has_method("world_to_grid"):
			for i in range(current_waypoint_index, waypoints.size()):
				var wp_cell: Vector2i = grid_manager.call("world_to_grid", waypoints[i])
				if wp_cell == cell:
					route_affected = true
					break

		if route_affected:
			# Trigger Dynamic Re-routing!
			set_robot_state(RobotState.REROUTING)
			if path_visualizer and path_visualizer.has_method("draw_path"):
				path_visualizer.call("draw_path", waypoints, Color(0.95, 0.2, 0.1))
			navigate_to_target(target_destination_world)

func _process(delta: float) -> void:
	# Update Grid Cell position
	if grid_manager and grid_manager.has_method("world_to_grid"):
		current_grid_cell = grid_manager.call("world_to_grid", global_position)

	# Battery consumption
	if current_state == RobotState.MOVING:
		battery_level = max(0.0, battery_level - (0.04 * delta))

	if waypoints.size() == 0 or current_state == RobotState.WAITING or current_state == RobotState.BLOCKED:
		return

	# Target Waypoint Navigation
	var target_wp = waypoints[current_waypoint_index]
	var target_pos_flat = Vector3(target_wp.x, global_position.y, target_wp.z)
	var distance = global_position.distance_to(target_pos_flat)

	if distance < 0.15:
		current_waypoint_index += 1
		if current_waypoint_index >= waypoints.size():
			if loop_waypoints:
				current_waypoint_index = 0
			else:
				current_state = RobotState.WAITING
				update_status_visuals()
				return
		target_wp = waypoints[current_waypoint_index]
		target_pos_flat = Vector3(target_wp.x, global_position.y, target_wp.z)

	# Rotate towards target
	var move_dir = (target_pos_flat - global_position).normalized()
	if move_dir.length_squared() > 0.001:
		var target_angle = atan2(-move_dir.x, -move_dir.z)
		rotation.y = lerp_angle(rotation.y, target_angle, turn_speed * delta)

	# Move forward
	global_position = global_position.move_toward(target_pos_flat, move_speed * delta)
