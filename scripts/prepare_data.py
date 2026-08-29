import os
import shutil
from pathlib import Path

def prepare_yolo_dataset(roboflow_dir, custom_data_dir, output_dir):
    """
    Merges a dataset downloaded from Roboflow with a custom dataset.
    Both should ideally be in YOLO format (images and labels in corresponding folders).
    
    Expected input format for both datasets:
    - dataset/
        - images/
            - train/
            - val/
        - labels/
            - train/
            - val/
            
    Run this on your laptop before training.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    for split in ['train', 'val']:
        (out_path / 'images' / split).mkdir(parents=True, exist_ok=True)
        (out_path / 'labels' / split).mkdir(parents=True, exist_ok=True)
        
        # Copy Roboflow data
        rf_images = Path(roboflow_dir) / 'images' / split
        rf_labels = Path(roboflow_dir) / 'labels' / split
        
        if rf_images.exists():
            for img in rf_images.glob('*'):
                shutil.copy(img, out_path / 'images' / split / img.name)
        if rf_labels.exists():
            for lbl in rf_labels.glob('*'):
                shutil.copy(lbl, out_path / 'labels' / split / lbl.name)
                
        # Copy Custom data
        custom_images = Path(custom_data_dir) / 'images' / split
        custom_labels = Path(custom_data_dir) / 'labels' / split
        
        if custom_images.exists():
            for img in custom_images.glob('*'):
                shutil.copy(img, out_path / 'images' / split / f"custom_{img.name}")
        if custom_labels.exists():
            for lbl in custom_labels.glob('*'):
                shutil.copy(lbl, out_path / 'labels' / split / f"custom_{lbl.name}")

    print(f"Dataset successfully merged into {output_dir}")
    print("Next step: Update your data.yaml file to point to this new output_dir.")

if __name__ == "__main__":
    # Example usage (update these paths)
    # prepare_yolo_dataset(
    #     roboflow_dir="../data/roboflow_dataset", 
    #     custom_data_dir="../data/my_custom_dataset", 
    #     output_dir="../data/merged_dataset"
    # )
    print("Open this script and update the paths to merge your datasets.")
