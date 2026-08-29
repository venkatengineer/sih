import os
from ultralytics import YOLO

def export_model_for_pi():
    """
    Exports the trained PyTorch (.pt) model to ONNX format.
    ONNX (Open Neural Network Exchange) is heavily optimized for CPU inference,
    which is essential for the Raspberry Pi 5.
    """
    
    # Path to your trained weights (from Phase 1)
    weights_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models', 'amr_warehouse_v1', 'weights', 'best.pt'))
    
    # Fallback to pretrained if custom doesn't exist
    if not os.path.exists(weights_path):
        print(f"Custom weights not found at {weights_path}.")
        print("Exporting the default 'yolov8s.pt' instead...")
        weights_path = "yolov8s.pt"
        
    print(f"Loading model: {weights_path}")
    model = YOLO(weights_path)
    
    print("Exporting to ONNX format... (this may take a minute)")
    # 'opset=12' ensures maximum compatibility with standard ONNX Runtime on ARM
    success = model.export(format="onnx", opset=12, simplify=True)
    
    if success:
        print(f"\nSUCCESS! ONNX model saved at: {success}")
        print("You should now use the .onnx file in your main_loop.py on the Raspberry Pi.")
    else:
        print("\nExport failed. Ensure you have the 'onnx' Python package installed.")

if __name__ == "__main__":
    export_model_for_pi()
