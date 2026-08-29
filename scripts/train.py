import os
from ultralytics import YOLO

def train_model():
    """
    Trains a YOLOv8 model on the warehouse dataset.
    We are using YOLOv8s (Small) as it offers a great balance between accuracy (which you requested) 
    and performance on edge devices. For the Raspberry Pi 5, this will be exported to ONNX later.
    """
    
    # Initialize the model (using the 'small' version for better accuracy than nano)
    print("Initializing YOLOv8s model...")
    model = YOLO("yolov8s.pt")
    
    # Path to your dataset configuration file
    # This YAML file should define the classes (person, forklift, pallet, etc.) 
    # and paths to your training/validation images.
    data_yaml_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs', 'data.yaml'))
    
    if not os.path.exists(data_yaml_path):
        print(f"Error: Could not find dataset config at {data_yaml_path}")
        print("Please create 'configs/data.yaml' with your dataset paths and classes.")
        return

    print("Starting training...")
    # Train the model
    # Adjust epochs and batch size based on your laptop's GPU capability
    results = model.train(
        data=data_yaml_path,
        epochs=50,             # Number of training epochs
        imgsz=640,             # Image size (640 is standard)
        batch=16,              # Batch size (reduce if you get Out Of Memory errors)
        name='amr_warehouse_v1', # Name of the run folder
        project=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models')), 
        device='',             # Leave empty to auto-detect GPU/CPU
        save=True              # Save the best weights
    )
    
    print(f"Training complete. Weights saved to models/amr_warehouse_v1/weights/best.pt")

if __name__ == "__main__":
    train_model()
