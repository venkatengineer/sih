class_name WarehouseHUD
extends Control

var camera_controller: Node3D = null

func _ready() -> void:
	# Enable MOUSE_FILTER_PASS on root HUD control so mouse clicks pass to buttons & viewport
	mouse_filter = Control.MOUSE_FILTER_PASS
	
	var main_scene = get_tree().current_scene
	if main_scene:
		camera_controller = main_scene.get_node_or_null("CameraPivot")

func _on_overview_btn_pressed() -> void:
	if camera_controller and camera_controller.has_method("set_view_overview"):
		camera_controller.call("set_view_overview")

func _on_topdown_btn_pressed() -> void:
	if camera_controller and camera_controller.has_method("set_view_topdown"):
		camera_controller.call("set_view_topdown")

func _on_pickup_btn_pressed() -> void:
	if camera_controller and camera_controller.has_method("set_view_pickup_drop"):
		camera_controller.call("set_view_pickup_drop")

func _on_charging_btn_pressed() -> void:
	if camera_controller and camera_controller.has_method("set_view_charging"):
		camera_controller.call("set_view_charging")
