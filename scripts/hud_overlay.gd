class_name WarehouseHUD
extends Control

var camera_controller: Node3D = null
var fleet_manager: Node3D = null
var amrs: Array[Node3D] = []
var selected_amr: Node3D = null
var system_time: float = 0.0
var event_logs: Array[String] = []

@onready var lbl_kpi: Label = get_node_or_null("HeaderPanel/HBox/Title") as Label
@onready var fleet_vbox: VBoxContainer = get_node_or_null("FleetPanel/VBox/AMRListVBox") as VBoxContainer
@onready var detail_panel: PanelContainer = get_node_or_null("SelectedAMRPanel") as PanelContainer
@onready var detail_text: RichTextLabel = get_node_or_null("SelectedAMRPanel/VBox/DetailText") as RichTextLabel
@onready var event_log_text: RichTextLabel = get_node_or_null("EventLogPanel/VBox/LogText") as RichTextLabel
@onready var decision_text: RichTextLabel = get_node_or_null("DecisionPanel/VBox/DecisionText") as RichTextLabel

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_PASS
	
	var main_scene = get_tree().current_scene
	if main_scene:
		camera_controller = main_scene.get_node_or_null("CameraPivot")
		fleet_manager = main_scene.get_node_or_null("AMR_Fleet")

	_add_event_log("SYSTEM INITIALIZED", "25x20 Grid Graph & Fleet Docks Online")
	_add_event_log("NAVIGATION ENGINE", "AStarGrid2D Manhattan Orthogonal Router Active")

	if detail_panel:
		detail_panel.visible = false

func _process(delta: float) -> void:
	system_time += delta

	# Discover active AMRs in fleet
	if amrs.size() == 0 and fleet_manager:
		for child in fleet_manager.get_children():
			if child.has_method("set_waypoints"):
				amrs.append(child as Node3D)
				var amr_id = child.get("robot_id")
				_add_event_log("AMR ONLINE", "Registered " + str(amr_id) + " at grid origin")

	# Update Top Status Bar KPIs
	_update_top_kpis()

	# Update AMR Fleet List
	_update_fleet_list()

	# Update Selected AMR Detail Panel if visible
	_update_selected_detail()

	# Update Decision Engine Metrics
	_update_decision_panel()

func _update_top_kpis() -> void:
	if not lbl_kpi:
		return

	var total_amrs = amrs.size()
	var active_moving = 0
	var blocked_waiting = 0
	var total_battery = 0.0

	for amr in amrs:
		var state = amr.get("current_state")
		var batt = amr.get("battery_level")
		if batt != null:
			total_battery += batt
		if state == 0: # MOVING
			active_moving += 1
		elif state == 1 or state == 2: # WAITING or BLOCKED
			blocked_waiting += 1

	var avg_batt = int(total_battery / max(1, total_amrs))
	lbl_kpi.text = "  🏭 SMART WAREHOUSE DIGITAL TWIN  |  ● SYSTEM ONLINE  |  AMRs: %d  |  ACTIVE: %d  |  WAITING: %d  |  AVG BATT: %d%%" % [total_amrs, active_moving, blocked_waiting, avg_batt]

func _update_fleet_list() -> void:
	if not fleet_vbox:
		return

	# Re-populate fleet buttons if count changed
	if fleet_vbox.get_child_count() != amrs.size():
		for c in fleet_vbox.get_children():
			c.queue_free()

		for i in range(amrs.size()):
			var amr = amrs[i]
			var btn = Button.new()
			btn.focus_mode = Control.FOCUS_NONE
			btn.mouse_filter = Control.MOUSE_FILTER_STOP
			btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
			btn.custom_minimum_size = Vector2(0, 32)
			btn.pressed.connect(func(): _on_amr_selected(amr))
			fleet_vbox.add_child(btn)

	# Update button text & status badges
	for i in range(min(fleet_vbox.get_child_count(), amrs.size())):
		var amr = amrs[i]
		var btn = fleet_vbox.get_child(i) as Button
		if btn:
			var id = str(amr.get("robot_id"))
			var state = amr.get("current_state")
			var batt = int(amr.get("battery_level"))
			var badge = "🟢 MOVING"
			match state:
				1: badge = "🟡 WAITING"
				2: badge = "🔴 BLOCKED"
				3: badge = "🔵 CHARGING"
				4: badge = "🟣 REROUTING"

			var is_sel = (amr == selected_amr)
			var prefix = "▶ " if is_sel else "  "
			btn.text = "%s%s  |  %s  |  %d%%" % [prefix, id, badge, batt]

func select_amr(amr: Node3D) -> void:
	_on_amr_selected(amr)

func _on_amr_selected(amr: Node3D) -> void:
	selected_amr = amr
	if detail_panel:
		detail_panel.visible = true
	var id = str(amr.get("robot_id"))
	_add_event_log("AMR SELECTED", "Inspecting telemetry for " + id)

func _update_selected_detail() -> void:
	if not detail_panel or not detail_panel.visible or not selected_amr or not is_instance_valid(selected_amr):
		return

	var id = str(selected_amr.get("robot_id"))
	var state = selected_amr.get("current_state")
	var batt = int(selected_amr.get("battery_level"))
	var speed = float(selected_amr.get("move_speed"))
	var cell = selected_amr.get("current_grid_cell")
	var task = str(selected_amr.get("current_task"))
	var cargo = selected_amr.get("has_cargo")

	var badge = "🟢 MOVING"
	match state:
		1: badge = "🟡 WAITING"
		2: badge = "🔴 BLOCKED"
		3: badge = "🔵 CHARGING"
		4: badge = "🟣 REROUTING"

	var cargo_text = "[color=#22c55e]PALLET LOADED[/color]" if cargo else "[color=#94a3b8]UNLOADED[/color]"
	var bar_fill = "█".repeat(int(batt / 10.0)) + "░".repeat(10 - int(batt / 10.0))

	detail_text.text = """[color=#38bdf8][b]%s TELEMETRY[/b][/color]  [color=#94a3b8]%s[/color]
[color=#64748b]Battery:[/color] [color=#e2e8f0]%s %d%%[/color]
[color=#64748b]Velocity:[/color] [color=#e2e8f0]%.1f m/s[/color]
[color=#64748b]Grid Location:[/color] [color=#38bdf8]Cell %s[/color]
[color=#64748b]Task Directive:[/color] [color=#f59e0b]%s[/color]
[color=#64748b]Cargo Payload:[/color] %s""" % [id, badge, bar_fill, batt, speed, str(cell), task, cargo_text]

func _update_decision_panel() -> void:
	if not decision_text:
		return

	var blocked_count = 0
	for amr in amrs:
		if amr.get("current_state") == 2:
			blocked_count += 1

	var risk_color = "[color=#22c55e]LOW (0 DETECTED)[/color]" if blocked_count == 0 else "[color=#ef4444]COLLISION STOP (%d)[/color]" % blocked_count
	decision_text.text = """[color=#64748b]Path Graph:[/color] [color=#38bdf8]AStarGrid2D (Manhattan)[/color]
[color=#64748b]Network Grid:[/color] [color=#e2e8f0]25 × 20 (500 Cells @ 2.0m)[/color]
[color=#64748b]Congestion Level:[/color] [color=#22c55e]OPTIMAL (0.04)[/color]
[color=#64748b]Conflict Risk:[/color] %s""" % risk_color

func _add_event_log(event_type: String, details: String) -> void:
	var mins = int(system_time) / 60
	var secs = int(system_time) % 60
	var time_stamp = "%02d:%02d" % [mins, secs]
	var log_entry = "[color=#64748b]%s[/color] [color=#38bdf8]%s[/color] %s" % [time_stamp, event_type, details]
	event_logs.append(log_entry)
	if event_logs.size() > 8:
		event_logs.remove_at(0)

	if event_log_text:
		event_log_text.text = "\n".join(event_logs)

# --- BUTTON SIGNALS ---
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

func _on_track_camera_pressed() -> void:
	if selected_amr and camera_controller and camera_controller.has_method("focus_node"):
		camera_controller.call("focus_node", selected_amr)
		var id = str(selected_amr.get("robot_id"))
		_add_event_log("CAMERA TRACK", "Locking camera target to " + id)

func _on_toggle_block_pressed() -> void:
	if selected_amr:
		var state = selected_amr.get("current_state")
		if state == 2 or state == 1:
			selected_amr.call("set_robot_state", 0) # MOVING
			_add_event_log("SCENARIO OVERRIDE", str(selected_amr.get("robot_id")) + " Resumed Patrol")
		else:
			selected_amr.call("set_robot_state", 2) # BLOCKED
			_add_event_log("SCENARIO OVERRIDE", str(selected_amr.get("robot_id")) + " Force Blocked")

func _on_close_detail_pressed() -> void:
	if detail_panel:
		detail_panel.visible = false

func _on_scenario_normal_pressed() -> void:
	for amr in amrs:
		amr.call("set_robot_state", 0) # MOVING
	_add_event_log("SCENARIO RESET", "All fleet AMRs set to Normal Patrol")

func _on_scenario_conflict_pressed() -> void:
	if amrs.size() >= 2:
		amrs[0].call("set_robot_state", 2) # BLOCKED
		amrs[1].call("set_robot_state", 1) # WAITING
		_add_event_log("SIMULATE CONFLICT", "AMR-01 & AMR-02 simulated aisle intersection bottleneck")
