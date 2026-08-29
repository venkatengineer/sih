import cv2
import os
import time
from ultralytics import YOLO

def run_inference():
    """
    Runs real-time inference on a webcam feed using the trained YOLOv8 model.
    """
    
    # Path to your trained weights
    weights_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models', 'amr_warehouse_v1', 'weights', 'best.pt'))
    
    # Fallback to pretrained YOLOv8s if custom weights don't exist yet (for testing)
    if not os.path.exists(weights_path):
        print(f"Custom weights not found at {weights_path}.")
        print("Falling back to pretrained 'yolov8s.pt' for testing...")
        model = YOLO("yolov8s.pt")
    else:
        print(f"Loading custom model from {weights_path}")
        model = YOLO(weights_path)
        
    # Open the default webcam (0). Change to 1, 2, etc. if you have multiple cameras.
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return
        
    print("Starting video feed. Press 'q' to quit.")
    
    # Variables for FPS calculation
    prev_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break
            
        # Run YOLO inference
        # conf=0.5 means only show detections with >50% confidence
        results = model.predict(frame, conf=0.5, verbose=False)
        
        # Draw bounding boxes and labels on the frame
        annotated_frame = results[0].plot()
        
        # Calculate FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        
        # Display FPS on frame
        cv2.putText(annotated_frame, f"FPS: {fps:.1f}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    
        # Print FPS and Detections to terminal
        detections = []
        for box in results[0].boxes:
            conf = float(box.conf)
            cls = int(box.cls)
            name = model.names[cls]
            detections.append(f"{name} {conf:.2f}")
        
        print(f"FPS: {fps:.1f} | Detections: {', '.join(detections)}")
                    
        # Show the frame
        cv2.imshow("AMR Camera Feed", annotated_frame)
        
        # Break loop if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_inference()
