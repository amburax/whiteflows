import os
from PIL import Image
from pathlib import Path

def convert_to_webp(directory):
    print(f"Opening directory: {directory}")
    files = os.listdir(directory)
    converted_count = 0
    
    for filename in files:
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_path = os.path.join(directory, filename)
            # Create WebP path
            file_stem = Path(filename).stem
            webp_path = os.path.join(directory, f"{file_stem}.webp")
            
            try:
                img = Image.open(image_path)
                # Convert to RGB (to handle transparency/RGBA if necessary)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")
                    
                img.save(webp_path, "WEBP", quality=85)
                print(f"  [OK] Converted: {filename} -> {file_stem}.webp")
                converted_count += 1
            except Exception as e:
                print(f"  [ERROR] Failed to convert {filename}: {e}")
                
    return converted_count

if __name__ == "__main__":
    base_path = Path("D:/WhiteFlows")
    dirs_to_process = [
        base_path / "backend/static/images",
        base_path / "frontend/public/static/images"
    ]
    
    total_converted = 0
    for d in dirs_to_process:
        if d.exists():
            total_converted += convert_to_webp(d)
        else:
            print(f"Directory not found: {d}")
            
    print(f"\nDone! Total images converted: {total_converted}")
