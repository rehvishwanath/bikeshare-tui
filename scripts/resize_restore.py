from PIL import Image
import os

# Mapping original downloads to repo assets
MAPPING = [
    ("/Users/rehanvishwanath/Downloads/demo 1.PNG", "/Users/rehanvishwanath/bikeshare-tui/assets/current_search_friction.png"),
    ("/Users/rehanvishwanath/Downloads/demo 4.PNG", "/Users/rehanvishwanath/bikeshare-tui/assets/current_map_clutter.png"),
    ("/Users/rehanvishwanath/Downloads/demo 5.PNG", "/Users/rehanvishwanath/bikeshare-tui/assets/current_hidden_details.png"),
    ("/Users/rehanvishwanath/Downloads/demo 3.PNG", "/Users/rehanvishwanath/bikeshare-tui/assets/current_no_widget.png")
]

def resize_and_save():
    for src, dest in MAPPING:
        try:
            with Image.open(src) as img:
                # Calculate new size (50%)
                new_width = int(img.width * 0.5)
                new_height = int(img.height * 0.5)
                
                # Resize using high-quality resampling
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save
                resized_img.save(dest, optimize=True)
                print(f"Resized and restored: {os.path.basename(dest)} ({new_width}x{new_height})")
        except Exception as e:
            print(f"Error processing {src}: {e}")

if __name__ == "__main__":
    resize_and_save()
