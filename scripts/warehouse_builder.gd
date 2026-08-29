class_name WarehouseBuilder
extends Node3D

@export var warehouse_width: float = 50.0  # X axis (meters)
@export var warehouse_length: float = 40.0 # Z axis (meters)
@export var warehouse_height: float = 10.0 # Y axis (meters)

# Preloaded Materials
var mat_floor = preload("res://materials/concrete_floor.tres")
var mat_wall = preload("res://materials/wall_concrete.tres")
var mat_truss = preload("res://materials/truss_metal.tres")
var mat_rack_blue = preload("res://materials/metal_rack_blue.tres")
var mat_rack_orange = preload("res://materials/metal_rack_orange.tres")
var mat_cardboard = preload("res://materials/cardboard.tres")
var mat_pallet = preload("res://materials/wood_pallet.tres")
var mat_tote = preload("res://materials/plastic_tote_blue.tres")
var mat_mark_yellow = preload("res://materials/floor_marking_yellow.tres")
var mat_mark_white = preload("res://materials/floor_marking_white.tres")
var mat_zone_pickup = preload("res://materials/zone_pickup.tres")
var mat_zone_dropoff = preload("res://materials/zone_dropoff.tres")
var mat_zone_charging = preload("res://materials/zone_charging.tres")
var mat_zone_obstacle = preload("res://materials/zone_obstacle.tres")
var mat_light_emitter = preload("res://materials/light_emitter.tres")

func _ready() -> void:
	build_warehouse_shell()
	build_overhead_lighting_trusses_and_ducts()
	build_storage_racks()
	build_pickup_dropoff_zones()
	build_charging_stations()
	build_loading_docks()
	build_obstacle_area()
	build_wall_accessories()
	build_floor_markings_and_signage()

# --- 1. WAREHOUSE SHELL & STRUCTURAL ELEMENTS ---
func build_warehouse_shell() -> void:
	var shell_node = Node3D.new()
	shell_node.name = "WarehouseShell"
	add_child(shell_node)

	# Main Concrete Floor Plane
	var floor_mesh = PlaneMesh.new()
	floor_mesh.size = Vector2(warehouse_width, warehouse_length)
	var floor_inst = MeshInstance3D.new()
	floor_inst.name = "Floor"
	floor_inst.mesh = floor_mesh
	floor_inst.material_override = mat_floor
	shell_node.add_child(floor_inst)

	# Perimeter Walls with Static Physics Colliders (Layer 1)
	var half_w = warehouse_width * 0.5
	var half_l = warehouse_length * 0.5
	var h_height = warehouse_height * 0.5

	# North & South Walls
	_create_static_box(shell_node, Vector3(0, h_height, -half_l), Vector3(warehouse_width, warehouse_height, 0.4), mat_wall, 1)
	_create_static_box(shell_node, Vector3(0, h_height, half_l), Vector3(warehouse_width, warehouse_height, 0.4), mat_wall, 1)
	# East & West Walls
	_create_static_box(shell_node, Vector3(-half_w, h_height, 0), Vector3(0.4, warehouse_height, warehouse_length), mat_wall, 1)
	_create_static_box(shell_node, Vector3(half_w, h_height, 0), Vector3(0.4, warehouse_height, warehouse_length), mat_wall, 1)

# --- 2. OVERHEAD TRUSSES, CEILING LIGHTS & DUCTS ---
func build_overhead_lighting_trusses_and_ducts() -> void:
	var ceiling_node = Node3D.new()
	ceiling_node.name = "CeilingLightingAndDucts"
	add_child(ceiling_node)

	# Steel Roof Trusses spanning across X
	for x_pos in range(-20, 21, 10):
		_create_box(ceiling_node, Vector3(x_pos, warehouse_height - 0.3, 0), Vector3(0.35, 0.65, warehouse_length), mat_truss)

	# Overhead HVAC Galvanized Ductwork
	_create_box(ceiling_node, Vector3(-10, warehouse_height - 1.2, 0), Vector3(1.0, 0.7, warehouse_length - 4.0), mat_truss)
	_create_box(ceiling_node, Vector3(10, warehouse_height - 1.2, 0), Vector3(1.0, 0.7, warehouse_length - 4.0), mat_truss)

	# Ceiling Light Grid with Soft SpotLights
	for x in range(-18, 19, 12):
		for z in range(-15, 16, 10):
			_create_ceiling_light(ceiling_node, Vector3(x, warehouse_height - 0.5, z))

func _create_ceiling_light(parent: Node, pos: Vector3) -> void:
	var light_rig = Node3D.new()
	light_rig.position = pos
	parent.add_child(light_rig)

	# Light fixture housing & emissive lens
	_create_box(light_rig, Vector3.ZERO, Vector3(1.4, 0.16, 0.7), mat_truss)
	_create_box(light_rig, Vector3(0, -0.09, 0), Vector3(1.2, 0.04, 0.5), mat_light_emitter)

	# SpotLight3D casting downward light cone
	var spot = SpotLight3D.new()
	spot.position = Vector3(0, -0.2, 0)
	spot.rotation_degrees = Vector3(-90, 0, 0)
	spot.spot_range = 15.0
	spot.spot_angle = 55.0
	spot.light_energy = 2.8
	spot.light_color = Color(0.98, 0.96, 0.9, 1.0)
	spot.shadow_enabled = true
	light_rig.add_child(spot)

# --- 3. DETAILED STORAGE RACKS & CARGO ---
func build_storage_racks() -> void:
	var racks_node = Node3D.new()
	racks_node.name = "StorageRacks"
	add_child(racks_node)

	var x_offsets = [-14.0, -4.0, 4.0, 14.0]
	var z_rows = [-12.0, -6.0, 2.0, 8.0]

	for x in x_offsets:
		for z in z_rows:
			_create_rack_unit(racks_node, Vector3(x, 0, z))

func _create_rack_unit(parent: Node, pos: Vector3) -> void:
	var rack_node = Node3D.new()
	rack_node.position = pos
	parent.add_child(rack_node)

	var rack_w = 6.0 # length along X
	var rack_d = 1.2 # depth along Z
	var rack_h = 4.5 # height along Y
	var levels = 3

	# Solid Static Physics Collider for the Rack Unit (Layer 1)
	var static_body = StaticBody3D.new()
	static_body.position = Vector3(0, rack_h / 2.0, 0)
	static_body.collision_layer = 1
	static_body.collision_mask = 0
	
	var col_shape = CollisionShape3D.new()
	var box_shape = BoxShape3D.new()
	box_shape.size = Vector3(rack_w, rack_h, rack_d)
	col_shape.shape = box_shape
	static_body.add_child(col_shape)
	rack_node.add_child(static_body)

	# Visual Rack Structure: Blue Pillars & Anchor Plates
	var pillar_coords = [
		Vector3(-rack_w/2, rack_h/2, -rack_d/2),
		Vector3(rack_w/2, rack_h/2, -rack_d/2),
		Vector3(-rack_w/2, rack_h/2, rack_d/2),
		Vector3(rack_w/2, rack_h/2, rack_d/2)
	]
	for p_pos in pillar_coords:
		_create_box(rack_node, p_pos, Vector3(0.08, rack_h, 0.08), mat_rack_blue)
		_create_box(rack_node, Vector3(p_pos.x, 0.01, p_pos.z), Vector3(0.18, 0.02, 0.18), mat_truss)

	# Diagonal Side Cross-Bracing
	_create_box(rack_node, Vector3(-rack_w/2, rack_h/2, 0), Vector3(0.04, rack_h * 0.9, 0.04), mat_truss)
	_create_box(rack_node, Vector3(rack_w/2, rack_h/2, 0), Vector3(0.04, rack_h * 0.9, 0.04), mat_truss)

	# Horizontal orange crossbeams & shelf platforms per level
	for lvl in range(levels):
		var y_level = 0.2 + (lvl * 1.4)

		_create_box(rack_node, Vector3(0, y_level, rack_d/2), Vector3(rack_w, 0.08, 0.05), mat_rack_orange)
		_create_box(rack_node, Vector3(0, y_level, -rack_d/2), Vector3(rack_w, 0.08, 0.05), mat_rack_orange)
		_create_box(rack_node, Vector3(0, y_level, 0), Vector3(rack_w - 0.1, 0.03, rack_d - 0.1), mat_truss)

		# Barcode Label Accents
		_create_box(rack_node, Vector3(-rack_w/4, y_level + 0.04, rack_d/2 + 0.03), Vector3(0.14, 0.03, 0.01), mat_mark_yellow)
		_create_box(rack_node, Vector3(rack_w/4, y_level + 0.04, rack_d/2 + 0.03), Vector3(0.14, 0.03, 0.01), mat_mark_yellow)

		# Populate shelf with cargo visuals
		_populate_shelf_content(rack_node, Vector3(0, y_level + 0.02, 0), rack_w)

func _populate_shelf_content(parent: Node, base_pos: Vector3, width: float) -> void:
	var items = randi() % 3 + 3
	var step = (width - 0.8) / float(items)
	var start_x = -width/2 + 0.4

	for i in range(items):
		var item_x = start_x + (i * step)
		var local_pos = base_pos + Vector3(item_x, 0, 0)
		_create_pallet(parent, local_pos)

		var stack_type = randi() % 3
		if stack_type == 0:
			_create_box_cargo(parent, local_pos + Vector3(0, 0.25, 0), Vector3(0.7, 0.5, 0.7))
		elif stack_type == 1:
			_create_box_cargo(parent, local_pos + Vector3(-0.15, 0.22, 0), Vector3(0.4, 0.4, 0.4))
			_create_box_cargo(parent, local_pos + Vector3(0.15, 0.22, 0), Vector3(0.4, 0.4, 0.4))
			_create_box_cargo(parent, local_pos + Vector3(0, 0.6, 0), Vector3(0.5, 0.35, 0.5))
		else:
			_create_plastic_tote(parent, local_pos + Vector3(0, 0.22, 0))

func _create_pallet(parent: Node, pos: Vector3) -> void:
	var pallet_node = Node3D.new()
	pallet_node.position = pos
	parent.add_child(pallet_node)

	_create_box(pallet_node, Vector3(0, 0.04, 0), Vector3(0.9, 0.04, 0.9), mat_pallet)
	_create_box(pallet_node, Vector3(-0.38, 0.09, 0), Vector3(0.08, 0.06, 0.9), mat_pallet)
	_create_box(pallet_node, Vector3(0, 0.09, 0), Vector3(0.08, 0.06, 0.9), mat_pallet)
	_create_box(pallet_node, Vector3(0.38, 0.09, 0), Vector3(0.08, 0.06, 0.9), mat_pallet)

func _create_box_cargo(parent: Node, pos: Vector3, size: Vector3) -> void:
	var box_node = Node3D.new()
	box_node.position = pos
	box_node.rotation_degrees.y = randf_range(-4.0, 4.0)
	parent.add_child(box_node)

	_create_box(box_node, Vector3.ZERO, size, mat_cardboard)
	_create_box(box_node, Vector3(0, size.y * 0.5 + 0.005, 0), Vector3(size.x * 0.9, 0.005, size.z * 0.15), mat_mark_yellow)

func _create_plastic_tote(parent: Node, pos: Vector3) -> void:
	_create_box(parent, pos, Vector3(0.65, 0.3, 0.45), mat_tote)

# --- 4. REFINED PICKUP & DROPOFF ZONES ---
func build_pickup_dropoff_zones() -> void:
	var zones_node = Node3D.new()
	zones_node.name = "PickupDropoffZones"
	add_child(zones_node)

	_create_refined_zone(zones_node, Vector3(-18, 0.02, 12), Vector3(6, 0.01, 5), mat_zone_pickup, mat_mark_yellow, "INBOUND PICKUP STATION")
	_create_zone_pallet_staging(zones_node, Vector3(-18, 0.02, 12))

	_create_refined_zone(zones_node, Vector3(-18, 0.02, -12), Vector3(6, 0.01, 5), mat_zone_dropoff, mat_mark_yellow, "OUTBOUND DROPOFF STATION")
	_create_zone_pallet_staging(zones_node, Vector3(-18, 0.02, -12))

func _create_refined_zone(parent: Node, pos: Vector3, size: Vector3, mat_zone: Material, mat_border: Material, zone_label: String) -> void:
	var z_rig = Node3D.new()
	z_rig.position = pos
	parent.add_child(z_rig)

	var plane = PlaneMesh.new()
	plane.size = Vector2(size.x - 0.2, size.z - 0.2)
	var inst = MeshInstance3D.new()
	inst.mesh = plane
	inst.material_override = mat_zone
	z_rig.add_child(inst)

	var border_w = 0.12
	_create_box(z_rig, Vector3(0, 0.005, -size.z/2), Vector3(size.x, 0.01, border_w), mat_border)
	_create_box(z_rig, Vector3(0, 0.005, size.z/2), Vector3(size.x, 0.01, border_w), mat_border)
	_create_box(z_rig, Vector3(-size.x/2, 0.005, 0), Vector3(border_w, 0.01, size.z), mat_border)
	_create_box(z_rig, Vector3(size.x/2, 0.005, 0), Vector3(border_w, 0.01, size.z), mat_border)

	for cx in [-size.x/2, size.x/2]:
		for cz in [-size.z/2, size.z/2]:
			var beacon = MeshInstance3D.new()
			var c_mesh = CylinderMesh.new()
			c_mesh.top_radius = 0.06
			c_mesh.bottom_radius = 0.08
			c_mesh.height = 0.4
			beacon.mesh = c_mesh
			beacon.material_override = mat_zone
			beacon.position = Vector3(cx, 0.2, cz)
			z_rig.add_child(beacon)

func _create_zone_pallet_staging(parent: Node, center_pos: Vector3) -> void:
	for x_off in [-1.5, 0, 1.5]:
		for z_off in [-1.0, 1.0]:
			var p_pos = center_pos + Vector3(x_off, 0, z_off)
			# Staged Pallet with Physical Collider (Layer 3: Dynamic Obstacles)
			_create_static_box(parent, p_pos + Vector3(0, 0.25, 0), Vector3(0.9, 0.5, 0.9), mat_pallet, 3)
			_create_box_cargo(parent, p_pos + Vector3(0, 0.22, 0), Vector3(0.8, 0.5, 0.8))

# --- 5. CHARGING STATIONS ---
func build_charging_stations() -> void:
	var charging_node = Node3D.new()
	charging_node.name = "ChargingStations"
	add_child(charging_node)

	var center_pos = Vector3(18, 0.02, -12)

	_create_refined_zone(charging_node, center_pos, Vector3(6, 0.01, 8), mat_zone_charging, mat_mark_yellow, "AMR FLEET CHARGING DOCKS")

	for i in range(4):
		var z_offset = -3.0 + (i * 2.0)
		var bay_pos = center_pos + Vector3(0, 0, z_offset)

		_create_box(charging_node, bay_pos, Vector3(1.4, 0.03, 1.2), mat_rack_orange)
		_create_box(charging_node, bay_pos + Vector3(0, 0.01, 0), Vector3(1.0, 0.03, 0.8), mat_truss)

		# Wall Terminal Station with Physical Collider (Layer 1)
		_create_static_box(charging_node, Vector3(24.5, 0.8, bay_pos.z), Vector3(0.3, 1.4, 0.8), mat_rack_blue, 1)

		var led = MeshInstance3D.new()
		var s_mesh = SphereMesh.new()
		s_mesh.radius = 0.08
		s_mesh.height = 0.16
		led.mesh = s_mesh
		led.material_override = mat_zone_pickup
		led.position = Vector3(24.3, 1.3, bay_pos.z)
		charging_node.add_child(led)

# --- 6. LOADING DOCK BAYS ---
func build_loading_docks() -> void:
	var dock_node = Node3D.new()
	dock_node.name = "LoadingDocks"
	add_child(dock_node)

	var dock_positions = [-10.0, 0.0, 10.0]
	for z_pos in dock_positions:
		# Rollup Door Panel with Physical Collider (Layer 1)
		_create_static_box(dock_node, Vector3(-24.8, 2.0, z_pos), Vector3(0.1, 4.0, 3.5), mat_truss, 1)
		_create_box(dock_node, Vector3(-24.7, 2.1, z_pos - 1.8), Vector3(0.2, 4.2, 0.15), mat_mark_yellow)
		_create_box(dock_node, Vector3(-24.7, 2.1, z_pos + 1.8), Vector3(0.2, 4.2, 0.15), mat_mark_yellow)
		_create_static_box(dock_node, Vector3(-24.6, 0.2, z_pos - 1.5), Vector3(0.25, 0.4, 0.2), mat_truss, 1)
		_create_static_box(dock_node, Vector3(-24.6, 0.2, z_pos + 1.5), Vector3(0.25, 0.4, 0.2), mat_truss, 1)

# --- 7. TEMPORARY OBSTACLE AREA ---
func build_obstacle_area() -> void:
	var obstacle_node = Node3D.new()
	obstacle_node.name = "TemporaryObstacles"
	add_child(obstacle_node)

	var block_pos = Vector3(0, 0.02, 10)
	_create_refined_zone(obstacle_node, block_pos, Vector3(4, 0.01, 4), mat_zone_obstacle, mat_mark_yellow, "DYNAMIC OBSTACLE AREA")

	# Safety Cones with Physical Colliders (Layer 3: Dynamic Obstacles)
	for x_off in [-1.5, 1.5]:
		for z_off in [-1.5, 1.5]:
			var cone_pos = block_pos + Vector3(x_off, 0, z_off)
			_create_static_box(obstacle_node, cone_pos + Vector3(0, 0.3, 0), Vector3(0.5, 0.6, 0.5), mat_rack_orange, 3)

# --- 8. PERIMETER WALL ACCESSORIES ---
func build_wall_accessories() -> void:
	var acc_node = Node3D.new()
	acc_node.name = "WallAccessories"
	add_child(acc_node)

	for z_pos in [-12.0, 0.0, 12.0]:
		_create_box(acc_node, Vector3(24.6, 1.5, z_pos), Vector3(0.2, 0.8, 0.6), mat_truss)
		_create_box(acc_node, Vector3(24.48, 1.5, z_pos), Vector3(0.02, 0.2, 0.2), mat_mark_yellow)

	for x_pos in [-15.0, 15.0]:
		var ext = MeshInstance3D.new()
		var c_mesh = CylinderMesh.new()
		c_mesh.top_radius = 0.1
		c_mesh.bottom_radius = 0.1
		c_mesh.height = 0.6
		ext.mesh = c_mesh
		ext.material_override = mat_rack_orange
		ext.position = Vector3(x_pos, 1.2, 19.6)
		acc_node.add_child(ext)

# --- 9. FLOOR MARKINGS & OVERHEAD SIGNAGE ---
func build_floor_markings_and_signage() -> void:
	var signs_node = Node3D.new()
	signs_node.name = "SignageAndMarkings"
	add_child(signs_node)

	_create_box(signs_node, Vector3(0, 0.01, 0), Vector3(46, 0.01, 0.15), mat_mark_yellow)
	_create_box(signs_node, Vector3(0, 0.01, -16), Vector3(46, 0.01, 0.15), mat_mark_yellow)
	_create_box(signs_node, Vector3(0, 0.01, 16), Vector3(46, 0.01, 0.15), mat_mark_yellow)

	_create_box(signs_node, Vector3(-9, 0.01, 0), Vector3(0.15, 0.01, 32), mat_mark_yellow)
	_create_box(signs_node, Vector3(0, 0.01, 0), Vector3(0.15, 0.01, 32), mat_mark_yellow)
	_create_box(signs_node, Vector3(9, 0.01, 0), Vector3(0.15, 0.01, 32), mat_mark_yellow)

	_create_hanging_sign(signs_node, Vector3(-14, 5.8, 0), "AISLE 01 - NORTH")
	_create_hanging_sign(signs_node, Vector3(-4, 5.8, 0), "AISLE 02 - CENTRAL")
	_create_hanging_sign(signs_node, Vector3(4, 5.8, 0), "AISLE 03 - CENTRAL")
	_create_hanging_sign(signs_node, Vector3(14, 5.8, 0), "AISLE 04 - SOUTH")

func _create_hanging_sign(parent: Node, pos: Vector3, text_label: String) -> void:
	var sign_rig = Node3D.new()
	sign_rig.position = pos
	parent.add_child(sign_rig)

	_create_box(sign_rig, Vector3.ZERO, Vector3(3.2, 0.6, 0.08), mat_rack_blue)
	_create_box(sign_rig, Vector3(0, 0, -0.02), Vector3(3.3, 0.68, 0.06), mat_mark_yellow)

	var wire_mesh = CylinderMesh.new()
	wire_mesh.top_radius = 0.01
	wire_mesh.bottom_radius = 0.01
	wire_mesh.height = 4.0

	var w1 = MeshInstance3D.new()
	w1.mesh = wire_mesh
	w1.material_override = mat_truss
	w1.position = Vector3(-1.2, 2.0, 0)
	sign_rig.add_child(w1)

	var w2 = MeshInstance3D.new()
	w2.mesh = wire_mesh
	w2.material_override = mat_truss
	w2.position = Vector3(1.2, 2.0, 0)
	sign_rig.add_child(w2)

# --- HELPER: VISUAL MESH BOX CREATOR ---
func _create_box(parent: Node, pos: Vector3, size: Vector3, mat: Material) -> void:
	var mesh = BoxMesh.new()
	mesh.size = size
	var inst = MeshInstance3D.new()
	inst.mesh = mesh
	inst.material_override = mat
	inst.position = pos
	parent.add_child(inst)

# --- HELPER: STATIC PHYSICS BOX CREATOR ---
func _create_static_box(parent: Node, pos: Vector3, size: Vector3, mat: Material, layer: int = 1) -> void:
	var static_body = StaticBody3D.new()
	static_body.position = pos
	static_body.collision_layer = layer
	static_body.collision_mask = 0

	var mesh = BoxMesh.new()
	mesh.size = size
	var inst = MeshInstance3D.new()
	inst.mesh = mesh
	inst.material_override = mat
	static_body.add_child(inst)

	var col_shape = CollisionShape3D.new()
	var box_shape = BoxShape3D.new()
	box_shape.size = size
	col_shape.shape = box_shape
	static_body.add_child(col_shape)

	parent.add_child(static_body)
