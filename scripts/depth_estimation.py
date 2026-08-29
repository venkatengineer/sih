import cv2
import torch
import time
import numpy as np
from ultralytics import YOLO
from collision_checker import CollisionZoneChecker

def run_depth_estimation():
    checker = CollisionZoneChecker()
    
    print("Loading YOLOv8 model...")
    # Load YOLOv8 model (fallback to pretrained if custom weights not found)
    yolo_model = YOLO("yolov8s.pt")
    
    print("Loading MiDaS depth model...")
    # Load MiDaS Small for monocular depth estimation (optimized for CPU/Edge)
    midas_model_type = "MiDaS_small"
    midas = torch.hub.load("intel-isl/MiDaS", midas_model_type)
    
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    midas.to(device)
    midas.eval()
    
    # Load transforms to resize and normalize the image for MiDaS
    midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
    transform = midas_transforms.small_transform

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    print("Models loaded. Starting video feed...")
    prev_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        height, width, _ = frame.shape
        
        # 1. Run MiDaS Depth Estimation
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        input_batch = transform(img).to(device)
        
        with torch.no_grad():
            prediction = midas(input_batch)
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=img.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()
            
        depth_map = prediction.cpu().numpy()
        
        # Normalize depth map for visualization (0-255)
        depth_map_visual = cv2.normalize(depth_map, None, 0, 255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        depth_colormap = cv2.applyColorMap(depth_map_visual, cv2.COLORMAP_MAGMA)
        
        # 2. Run YOLOv8 Object Detection
        results = yolo_model.predict(frame, conf=0.5, verbose=False)
        annotated_frame = frame.copy()
        
        # 3. Fuse YOLO and Depth
        detections_info = []
        
        for box in results[0].boxes:
            # Bounding box coordinates
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            name = yolo_model.names[cls]
            
            # Calculate average depth inside the bounding box
            box_depth = depth_map[y1:y2, x1:x2]
            avg_depth = np.mean(box_depth)
            
            approx_distance = 1000.0 / (avg_depth + 1e-6)
            
            # Calculate angle/position relative to robot center
            center_x = (x1 + x2) / 2
            angle = ((center_x / width) - 0.5) * 60
            
            # Check Collision Zone
            status = checker.check_object(approx_distance, angle)
            
            # Determine color based on status
            if status == "DANGER":
                color = (0, 0, 255) # Red (BGR)
            elif status == "CAUTION":
                color = (0, 255, 255) # Yellow
            else:
                color = (0, 255, 0) # Green
            
            detections_info.append({
                "class": name,
                "box": (x1, y1, x2, y2),
                "distance_metric": round(approx_distance, 2),
                "angle": round(angle, 1),
                "status": status
            })
            
            # Draw on frame
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            label = f"{name} | {status} | Dist: {approx_distance:.1f}"
            cv2.putText(annotated_frame, label, (x1, max(y1 - 10, 0)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # FPS Calculation
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        
        # Display FPS
        cv2.putText(annotated_frame, f"FPS: {fps:.1f}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    
        # Print info to terminal
        print(f"--- FPS: {fps:.1f} ---")
        for det in detections_info:
            print(f"Detected: {det['class']} at {det['distance_metric']} units, Angle: {det['angle']} deg")

        # Show frames side by side (RGB and Depth)
        combined_view = np.hstack((annotated_frame, depth_colormap))
        
        # Resize to fit on screen if too large
        combined_view = cv2.resize(combined_view, (width, int(height/2)))
        
        cv2.imshow("AMR Vision (RGB | Depth)", combined_view)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_depth_estimation()
