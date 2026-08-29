class_name PathVisualizer
extends Node3D

@export var is_enabled: bool = true
@export var marker_color: Color = Color(0.1, 0.9, 0.55)

var mat_marker: StandardMaterial3D = null

func _ready() -> void:
	mat_marker = StandardMaterial3D.new()
	mat_marker.albedo_color = marker_color
	mat_marker.emission_enabled = true
	mat_marker.emission = marker_color
	mat_marker.emission_energy_multiplier = 2.0
	mat_marker.roughness = 0.2

func draw_path(waypoints: Array[Vector3], color: Color = Color(0.1, 0.9, 0.55)) -> void:
	clear_path()
	if not is_enabled or waypoints.size() == 0:
		return

	mat_marker.albedo_color = color
	mat_marker.emission = color

	for i in range(waypoints.size()):
		var wp = waypoints[i]
		# Floor Node Marker Cylinder (flat on concrete floor)
		var marker = MeshInstance3D.new()
		var cyl = CylinderMesh.new()
		cyl.top_radius = 0.12
		cyl.bottom_radius = 0.12
		cyl.height = 0.04
		marker.mesh = cyl
		marker.material_override = mat_marker
		marker.position = Vector3(wp.x, 0.04, wp.z)
		add_child(marker)

		# Connecting floor beam to next waypoint
		if i < waypoints.size() - 1:
			var next_wp = waypoints[i + 1]
			var mid_point = (wp + next_wp) * 0.5
			var dist = wp.distance_to(next_wp)

			var line = MeshInstance3D.new()
			var box = BoxMesh.new()
			box.size = Vector3(0.08, 0.03, dist)
			line.mesh = box
			line.material_override = mat_marker
			line.position = Vector3(mid_point.x, 0.035, mid_point.z)

			var dir = (next_wp - wp).normalized()
			if dir.length_squared() > 0.001:
				var angle = atan2(dir.x, dir.z)
				line.rotation.y = angle
			add_child(line)

func clear_path() -> void:
	for child in get_children():
		child.queue_free()
