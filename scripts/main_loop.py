import cv2
import torch
import time
import numpy as np
import os
from ultralytics import YOLO

# Import our custom modules
from collision_checker import CollisionZoneChecker
from decision_logic import RobotController

import platform

def main_integration_loop():
    print("--- AMR Vison & Control System Initializing ---")
    
    # --- DEBUG 1: GPU/CPU CHECK ---
    print(f"\n[DEBUG 1] CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"[DEBUG 1] GPU Device: {torch.cuda.get_device_name(0)}")
    else:
        print("[DEBUG 1] No GPU found. You are running entirely on CPU. CPU inference is the main limit for your FPS.")
        
    TEST_CAMERA_ONLY = False # --- DEBUG 5: Set to True to isolate camera capture bottleneck ---
    
    # Check if we are on the Raspberry Pi (Linux ARM architecture)
    is_pi = platform.machine() in ["aarch64", "armv7l"]
    if is_pi:
        print("Detected Raspberry Pi! Enabling performance mode...")
    
    # Initialize all subsystems
    print("1. Loading YOLOv8...")
    
    # Try to load the optimized ONNX model first
    onnx_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models', 'amr_warehouse_v1', 'weights', 'best.onnx'))
    if os.path.exists("yolov8n.onnx"):
        print("Loading local ONNX optimized model: yolov8n.onnx")
        yolo_model = YOLO("yolov8n.onnx", task='detect')
    elif os.path.exists(onnx_path):
        print(f"Loading optimized ONNX model: {onnx_path}")
        yolo_model = YOLO(onnx_path, task='detect')
    else:
        print("ONNX model not found. Falling back to PyTorch .pt model...")
        yolo_model = YOLO("yolov8n.pt") # Changed from yolov8s.pt to the much faster Nano model
        
    print("2. Loading MiDaS Depth Model...")
    midas = torch.hub.load("intel-isl/MiDaS", "MiDaS_small", trust_repo=True)
    device = torch.device("cpu") # Force CPU for MiDaS to avoid Pi GPU overhead
    midas.to(device)
    midas.eval()
    transform = torch.hub.load("intel-isl/MiDaS", "transforms", trust_repo=True).small_transform
    
    print("3. Initializing Safety & Control Logic...")
    collision_checker = CollisionZoneChecker()
    controller = RobotController()
    
    # We are getting a glitchy "Virtual Camera" feed. 
    # Let's bypass the auto-detector and explicitly try camera 1 or 0.
    print("4. Connecting to webcam...")
    cap = cv2.VideoCapture(1, cv2.CAP_ANY)
    if not cap.isOpened() or not cap.read()[0]:
        print("Camera 1 failed, falling back to Camera 0...")
        cap = cv2.VideoCapture(0, cv2.CAP_ANY)
        
    if not cap.isOpened():
        print("CRITICAL ERROR: Could not open any webcam.")
        return
    
    # Lower resolution to 640x480 on all platforms to help reach 30 FPS
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # Explicitly request 30 FPS from the camera hardware
    cap.set(cv2.CAP_PROP_FPS, 30)
        
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    print("\nSystem Ready. Entering Main Loop...")
    
    # --- DEBUG 3: INPUT RESOLUTION CHECK ---
    print("[DEBUG 3] YOLO Input Resolution (imgsz) set to: 320 (Down from 640 for speed)")
    
    prev_time = time.time()
    frame_count = 0
    depth_map = None
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        height, width, _ = frame.shape
        annotated_frame = frame.copy()
        
        # --- DEBUG 5: ISOLATE CAMERA BOTTLENECK ---
        if TEST_CAMERA_ONLY:
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
            prev_time = curr_time
            print(f"CAMERA RAW CAPTURE FPS: {fps:.1f}")
            cv2.imshow("AMR Main Loop", annotated_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'): break
            continue
            
        frame_count += 1
        
        # --- PERCEPTION: Depth ---
        # --- DEBUG 4: INFERENCE LOOP EFFICIENCY ---
        # MiDaS is very heavy on CPU. We now only run it every 5 frames instead of every frame.
        if frame_count % 5 == 1 or depth_map is None:
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            input_batch = transform(img).to(device)
            with torch.no_grad():
                prediction = midas(input_batch)
                prediction = torch.nn.functional.interpolate(
                    prediction.unsqueeze(1), size=img.shape[:2], 
                    mode="bicubic", align_corners=False
                ).squeeze()
            depth_map = prediction.cpu().numpy()
        
        # --- PERCEPTION: Detection ---
        # --- DEBUG 3: INPUT RESOLUTION CHECK ---
        # The ONNX model was exported at 640x640, so it strictly requires imgsz=640. 
        results = yolo_model.predict(frame, conf=0.5, imgsz=320, verbose=False)
        
        # --- ANALYSIS: Collision Checking ---
        detections_info = []
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cls = int(box.cls[0])
            name = yolo_model.names[cls]
            
            box_depth = depth_map[y1:y2, x1:x2]
            avg_depth = np.mean(box_depth)
            approx_distance = 1000.0 / (avg_depth + 1e-6)
            
            center_x = (x1 + x2) / 2
            angle = ((center_x / width) - 0.5) * 60
            
            # Check safety zone
            status = collision_checker.check_object(approx_distance, angle)
            detections_info.append({"class": name, "status": status})
            
            # Draw box
            color = (0, 0, 255) if status == "DANGER" else (0, 255, 255) if status == "CAUTION" else (0, 255, 0)
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(annotated_frame, f"{name} | {status}", (x1, max(y1 - 10, 0)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # --- DECISION: Control Action ---
        action = controller.decide_action(detections_info)
        
        # --- VISUALIZATION ---
        # Draw the action in huge text at the top center
        action_color = (0, 0, 255) if action == "STOP" else (0, 255, 255) if action == "SLOW_DOWN" else (0, 255, 0)
        cv2.putText(annotated_frame, f"COMMAND: {action}", (width//2 - 150, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, action_color, 3)

        # Calculate FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        # cv2.putText(annotated_frame, f"FPS: {fps:.1f}", (10, 30), 
        #             cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    
        print(f"FPS: {fps:.1f} | Final Command: {action} | Detected: {len(detections_info)} objects")
                    
        cv2.imshow("AMR Main Loop", annotated_frame)
        
        # --- ACTION EXECUTION (Phase 7 Placeholder) ---
        # If running on Raspberry Pi connected to motors, you would send commands here:
        # if action == "STOP": motors.stop()
        # elif action == "SLOW_DOWN": motors.set_speed(0.5)
        # else: motors.set_speed(1.0)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main_integration_loop()
