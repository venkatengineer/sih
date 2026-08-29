class_name WarehouseGridManager
extends Node3D

# Warehouse Grid Metadata & Navigation API
@export var grid_width: int = 25   # 25 cells along X axis (50 meters total)
@export var grid_height: int = 20  # 20 cells along Z axis (40 meters total)
@export var cell_size: float = 2.0  # 2.0m x 2.0m per grid cell

signal obstacle_changed(cell: Vector2i, is_blocked: bool)

enum CellType {
	FREE = 0,
	OBSTACLE = 1,
	PICKUP = 2,
	DROPOFF = 3,
	CHARGING = 4,
	TEMP_OBSTACLE = 5,
	INTERSECTION = 6,
	CHOKE_POINT = 7
}

# Grid Cell Storage: Vector2i -> CellType
var grid_cells: Dictionary = {}
# Cell Costs for Pathfinding: Vector2i -> float
var grid_costs: Dictionary = {}

# Pre-registered POIs for AMR Simulation
var amr_spawn_points: Array[Vector3] = []
var pickup_points: Array[Vector3] = []
var dropoff_points: Array[Vector3] = []
var charging_points: Array[Vector3] = []
var intersections: Array[Vector2i] = []
var choke_points: Array[Vector2i] = []
var dynamic_obstacle_cells: Array[Vector2i] = []

# Origin offset (bottom-left corner of the grid in world space)
var origin_offset: Vector3 = Vector3(-25.0, 0.0, -20.0)

func _ready() -> void:
	initialize_grid()

func initialize_grid() -> void:
	grid_cells.clear()
	grid_costs.clear()

	# 1. Default all cells to FREE
	for x in range(grid_width):
		for z in range(grid_height):
			var cell = Vector2i(x, z)
			grid_cells[cell] = CellType.FREE
			grid_costs[cell] = 1.0

	# 2. Mark Rack Obstacle Cells
	var rack_x_coords = [-14.0, -4.0, 4.0, 14.0]
	var rack_z_coords = [-12.0, -6.0, 2.0, 8.0]

	for rx in rack_x_coords:
		for rz in rack_z_coords:
			# Racks span 6m along X (-3 to +3) and 1.2m along Z (-0.6 to +0.6)
			var min_cell = world_to_grid(Vector3(rx - 3.0, 0, rz - 0.6))
			var max_cell = world_to_grid(Vector3(rx + 3.0, 0, rz + 0.6))
			for gx in range(min_cell.x, max_cell.x + 1):
				for gz in range(min_cell.y, max_cell.y + 1):
					set_cell_type(Vector2i(gx, gz), CellType.OBSTACLE)

	# 3. Perimeter Wall Obstacles
	for x in range(grid_width):
		set_cell_type(Vector2i(x, 0), CellType.OBSTACLE)
		set_cell_type(Vector2i(x, grid_height - 1), CellType.OBSTACLE)
	for z in range(grid_height):
		set_cell_type(Vector2i(0, z), CellType.OBSTACLE)
		set_cell_type(Vector2i(grid_width - 1, z), CellType.OBSTACLE)

	# 4. Register Zones & Target Points
	# Pickup Zone (-18, 0, 12)
	var pickup_cell = world_to_grid(Vector3(-18, 0, 12))
	set_cell_type(pickup_cell, CellType.PICKUP)
	pickup_points.append(grid_to_world(pickup_cell))

	# Dropoff Zone (-18, 0, -12)
	var dropoff_cell = world_to_grid(Vector3(-18, 0, -12))
	set_cell_type(dropoff_cell, CellType.DROPOFF)
	dropoff_points.append(grid_to_world(dropoff_cell))

	# Charging Bays (18, 0, -12)
	for i in range(4):
		var z_off = -15.0 + (i * 2.0)
		var c_cell = world_to_grid(Vector3(18, 0, z_off))
		set_cell_type(c_cell, CellType.CHARGING)
		charging_points.append(grid_to_world(c_cell))

	# Temporary Obstacle Area (0, 0, 10)
	var temp_cell = world_to_grid(Vector3(0, 0, 10))
	set_cell_type(temp_cell, CellType.TEMP_OBSTACLE)
	dynamic_obstacle_cells.append(temp_cell)

	# Intersections & Choke Points
	var inter_1 = world_to_grid(Vector3(0, 0, 0))
	var inter_2 = world_to_grid(Vector3(0, 0, -16))
	var inter_3 = world_to_grid(Vector3(0, 0, 16))
	set_cell_type(inter_1, CellType.INTERSECTION)
	set_cell_type(inter_2, CellType.INTERSECTION)
	set_cell_type(inter_3, CellType.INTERSECTION)
	intersections.append(inter_1)
	intersections.append(inter_2)
	intersections.append(inter_3)

	var choke_1 = world_to_grid(Vector3(-9, 0, -4))
	var choke_2 = world_to_grid(Vector3(9, 0, -4))
	set_cell_type(choke_1, CellType.CHOKE_POINT)
	set_cell_type(choke_2, CellType.CHOKE_POINT)
	choke_points.append(choke_1)
	choke_points.append(choke_2)

	# AMR Spawn Locations
	amr_spawn_points.append(grid_to_world(world_to_grid(Vector3(-20.0, 0, 0.0))))
	amr_spawn_points.append(grid_to_world(world_to_grid(Vector3(-20.0, 0, 6.0))))
	amr_spawn_points.append(grid_to_world(world_to_grid(Vector3(20.0, 0, 0.0))))
	amr_spawn_points.append(grid_to_world(world_to_grid(Vector3(20.0, 0, 6.0))))

# --- PUBLIC COORDINATE CONVERSION APIs ---
func world_to_grid(world_pos: Vector3) -> Vector2i:
	var local_pos = world_pos - origin_offset
	var gx = int(floor(local_pos.x / cell_size))
	var gz = int(floor(local_pos.z / cell_size))
	return Vector2i(
		clamp(gx, 0, grid_width - 1),
		clamp(gz, 0, grid_height - 1)
	)

func grid_to_world(grid_cell: Vector2i, height: float = 0.0) -> Vector3:
	var wx = origin_offset.x + (grid_cell.x * cell_size) + (cell_size * 0.5)
	var wz = origin_offset.z + (grid_cell.y * cell_size) + (cell_size * 0.5)
	return Vector3(wx, height, wz)

# --- NAVIGATION QUERY APIs ---
func is_valid_cell(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.x < grid_width and cell.y >= 0 and cell.y < grid_height

func is_walkable(cell: Vector2i) -> bool:
	if not is_valid_cell(cell): return false
	var type = grid_cells.get(cell, CellType.FREE)
	return type != CellType.OBSTACLE and type != CellType.TEMP_OBSTACLE

func get_cell_type(cell: Vector2i) -> CellType:
	return grid_cells.get(cell, CellType.FREE)

func set_cell_type(cell: Vector2i, type: CellType) -> void:
	if is_valid_cell(cell):
		grid_cells[cell] = type

func set_dynamic_obstacle(cell: Vector2i, is_blocked: bool) -> void:
	if is_valid_cell(cell):
		if is_blocked:
			grid_cells[cell] = CellType.TEMP_OBSTACLE
			if not dynamic_obstacle_cells.has(cell):
				dynamic_obstacle_cells.append(cell)
		else:
			grid_cells[cell] = CellType.FREE
			dynamic_obstacle_cells.erase(cell)
		emit_signal("obstacle_changed", cell, is_blocked)

func get_cell_cost(cell: Vector2i) -> float:
	var type = get_cell_type(cell)
	if type == CellType.INTERSECTION or type == CellType.CHOKE_POINT:
		return 1.4 # Slightly higher cost for intersections/choke points
	return grid_costs.get(cell, 1.0)

func get_neighbors(cell: Vector2i, allow_diagonals: bool = false) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	var offsets = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]
	if allow_diagonals:
		offsets.append_array([Vector2i(1, 1), Vector2i(-1, 1), Vector2i(1, -1), Vector2i(-1, -1)])

	for offset in offsets:
		var n_cell = cell + offset
		if is_walkable(n_cell):
			result.append(n_cell)
	return result

func get_spawn_points() -> Array[Vector3]:
	return amr_spawn_points

func get_pickup_points() -> Array[Vector3]:
	return pickup_points

func get_dropoff_points() -> Array[Vector3]:
	return dropoff_points

func get_charging_points() -> Array[Vector3]:
	return charging_points
