class_name AStarPathfinder
extends Node3D

var astar: AStarGrid2D = AStarGrid2D.new()
var grid_manager: Node3D = null
var is_initialized: bool = false

func initialize(p_grid_manager: Node3D) -> void:
	grid_manager = p_grid_manager
	if not grid_manager:
		push_error("AStarPathfinder: grid_manager is null!")
		return

	var g_width: int = grid_manager.get("grid_width")
	var g_height: int = grid_manager.get("grid_height")
	var c_size: float = grid_manager.get("cell_size")

	astar.region = Rect2i(0, 0, g_width, g_height)
	astar.cell_size = Vector2(c_size, c_size)
	# Orthogonal movement ONLY (no diagonal clipping)
	astar.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_NEVER
	astar.default_compute_heuristic = AStarGrid2D.HEURISTIC_MANHATTAN
	astar.default_estimate_heuristic = AStarGrid2D.HEURISTIC_MANHATTAN
	astar.update()

	# Synchronize grid walkability and costs from GridManager
	for x in range(g_width):
		for z in range(g_height):
			var cell = Vector2i(x, z)
			var is_walkable: bool = grid_manager.call("is_walkable", cell)
			astar.set_point_solid(cell, not is_walkable)
			var cost: float = grid_manager.call("get_cell_cost", cell)
			astar.set_point_weight_scale(cell, cost)

	is_initialized = true

func set_obstacle_solid(cell: Vector2i, is_solid: bool) -> void:
	if is_initialized and grid_manager and grid_manager.call("is_valid_cell", cell):
		astar.set_point_solid(cell, is_solid)

func calculate_grid_path(start_cell: Vector2i, target_cell: Vector2i) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	if not is_initialized or not grid_manager:
		return result

	if not grid_manager.call("is_valid_cell", start_cell) or not grid_manager.call("is_valid_cell", target_cell):
		return result

	if astar.is_point_solid(target_cell):
		return result # Unreachable solid target

	var raw_path = astar.get_id_path(start_cell, target_cell)
	for p in raw_path:
		result.append(Vector2i(p.x, p.y))
	return result

func calculate_world_path(start_world: Vector3, target_world: Vector3) -> Array[Vector3]:
	var world_path: Array[Vector3] = []
	if not is_initialized or not grid_manager:
		return world_path

	var start_cell: Vector2i = grid_manager.call("world_to_grid", start_world)
	var target_cell: Vector2i = grid_manager.call("world_to_grid", target_world)

	var grid_path = calculate_grid_path(start_cell, target_cell)
	if grid_path.is_empty():
		return world_path

	for cell in grid_path:
		var w_pos: Vector3 = grid_manager.call("grid_to_world", cell, 0.0)
		world_path.append(w_pos)
	return world_path
