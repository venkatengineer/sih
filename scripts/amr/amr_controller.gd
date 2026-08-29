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
@export var loop_waypoints: bool = true

var battery_level: float = 100.0
var current_state: RobotState = RobotState.MOVING
var current_task: String = "PATROL"
var current_grid_cell: Vector2i = Vector2i.ZERO
var target_destination_world: Vector3 = Vector3.ZERO
var waypoints: Array[Vector3] = []
var current_waypoint_index: int = 0
var has_cargo: bool = false

var grid_manager: Node3D = null

@onready var label_3d: Label3D = get_node_or_null("Label3D") as Label3D
@onready var status_led_mesh: MeshInstance3D = get_node_or_null("Body/StatusLED") as MeshInstance3D
@onready var status_light: OmniLight3D = get_node_or_null("Body/StatusLight") as OmniLight3D
@onready var cargo_box: Node3D = get_node_or_null("Body/CargoBox") as Node3D

func _ready() -> void:
	# Locate GridManager in scene tree
	var main_scene = get_tree().current_scene
	if main_scene:
		grid_manager = main_scene.get_node_or_null("Navigation/GridManager")
	
	if label_3d:
		label_3d.text = robot_id
	
	set_has_cargo(has_cargo)
	update_status_visuals()

func set_waypoints(new_waypoints: Array[Vector3]) -> void:
	waypoints = new_waypoints
	current_waypoint_index = 0
	if waypoints.size() > 0:
		target_destination_world = waypoints[waypoints.size() - 1]

func set_grid_waypoints(grid_cells: Array[Vector2i]) -> void:
	var w_points: Array[Vector3] = []
	if grid_manager and grid_manager.has_method("grid_to_world"):
		for cell in grid_cells:
			var w_pos = grid_manager.call("grid_to_world", cell, 0.0)
			w_points.append(w_pos)
	set_waypoints(w_points)

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

func _process(delta: float) -> void:
	# Update Grid Cell position
	if grid_manager and grid_manager.has_method("world_to_grid"):
		current_grid_cell = grid_manager.call("world_to_grid", global_position)

	# Slow natural battery consumption
	if current_state == RobotState.MOVING:
		battery_level = max(0.0, battery_level - (0.04 * delta))

	if waypoints.size() == 0 or current_state == RobotState.WAITING or current_state == RobotState.BLOCKED:
		return

	# Target Waypoint
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
