class_name WarehouseCameraController
extends Node3D

@export var pan_speed: float = 24.0
@export var orbit_sensitivity: float = 0.005
@export var zoom_sensitivity: float = 2.5
@export var min_zoom: float = 5.0
@export var max_zoom: float = 65.0
@export var lerp_speed: float = 12.0

var target_position: Vector3 = Vector3(0, 0, 0)
var target_yaw: float = -0.785398 # -45 degrees
var target_pitch: float = -0.610865 # -35 degrees
var target_distance: float = 38.0

var current_yaw: float = -0.785398
var current_pitch: float = -0.610865
var current_distance: float = 38.0

var is_orbiting: bool = false
var is_panning: bool = false
var last_mouse_pos: Vector2 = Vector2.ZERO

@onready var camera: Camera3D = $Camera3D

func _ready() -> void:
	target_position = global_position
	set_view_overview()

func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		# Support Right Click, Middle Click, and Left Click (with Shift or Control) for dragging
		if event.button_index == MOUSE_BUTTON_RIGHT or (event.button_index == MOUSE_BUTTON_LEFT and not event.shift_pressed):
			is_orbiting = event.pressed
			last_mouse_pos = event.position
		elif event.button_index == MOUSE_BUTTON_MIDDLE or (event.button_index == MOUSE_BUTTON_LEFT and event.shift_pressed):
			is_panning = event.pressed
			last_mouse_pos = event.position
		
		# Mouse Wheel Zoom
		if event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
			target_distance = clamp(target_distance - zoom_sensitivity, min_zoom, max_zoom)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
			target_distance = clamp(target_distance + zoom_sensitivity, min_zoom, max_zoom)

	elif event is InputEventMouseMotion:
		var delta = event.position - last_mouse_pos
		last_mouse_pos = event.position
		
		if is_orbiting:
			target_yaw -= delta.x * orbit_sensitivity
			target_pitch -= delta.y * orbit_sensitivity
			target_pitch = clamp(target_pitch, -deg_to_rad(89.0), -deg_to_rad(5.0))
		elif is_panning:
			var right = global_transform.basis.x
			var forward = Vector3(right.z, 0, -right.x).normalized()
			target_position += (-right * delta.x + forward * delta.y) * (target_distance * 0.002)

	elif event is InputEventKey and event.pressed:
		# Quick View Switcher Hotkeys
		if event.keycode == KEY_1:
			set_view_overview()
		elif event.keycode == KEY_2:
			set_view_topdown()
		elif event.keycode == KEY_3:
			set_view_pickup_drop()
		elif event.keycode == KEY_4:
			set_view_charging()

func _process(delta: float) -> void:
	# WASD & Arrow Key Panning (Checked continuously in _process)
	var move_vec = Vector3.ZERO
	var right = basis.x
	var forward = Vector3(right.z, 0, -right.x).normalized()
	
	if Input.is_physical_key_pressed(KEY_W) or Input.is_physical_key_pressed(KEY_UP):
		move_vec += forward
	if Input.is_physical_key_pressed(KEY_S) or Input.is_physical_key_pressed(KEY_DOWN):
		move_vec -= forward
	if Input.is_physical_key_pressed(KEY_A) or Input.is_physical_key_pressed(KEY_LEFT):
		move_vec -= right
	if Input.is_physical_key_pressed(KEY_D) or Input.is_physical_key_pressed(KEY_RIGHT):
		move_vec += right

	if move_vec.length_squared() > 0.001:
		target_position += move_vec.normalized() * pan_speed * delta

	# Smooth camera transitions
	current_yaw = lerp_angle(current_yaw, target_yaw, lerp_speed * delta)
	current_pitch = lerp_angle(current_pitch, target_pitch, lerp_speed * delta)
	current_distance = lerp(current_distance, target_distance, lerp_speed * delta)
	global_position = global_position.lerp(target_position, lerp_speed * delta)

	# Update rotation & camera offset distance
	rotation = Vector3(current_pitch, current_yaw, 0)
	if camera:
		camera.position = Vector3(0, 0, current_distance)

func set_view_overview() -> void:
	target_position = Vector3(0, 0, 0)
	target_yaw = deg_to_rad(-45.0)
	target_pitch = deg_to_rad(-35.0)
	target_distance = 38.0

func set_view_topdown() -> void:
	target_position = Vector3(0, 0, 0)
	target_yaw = deg_to_rad(0.0)
	target_pitch = deg_to_rad(-88.5)
	target_distance = 45.0

func set_view_pickup_drop() -> void:
	target_position = Vector3(-12, 0, 10)
	target_yaw = deg_to_rad(-30.0)
	target_pitch = deg_to_rad(-25.0)
	target_distance = 18.0

func set_view_charging() -> void:
	target_position = Vector3(14, 0, -10)
	target_yaw = deg_to_rad(45.0)
	target_pitch = deg_to_rad(-25.0)
	target_distance = 18.0
