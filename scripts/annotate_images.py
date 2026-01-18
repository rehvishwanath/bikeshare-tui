from PIL import Image, ImageDraw, ImageFont
import os

# Configuration for images
# Mappings based on file sizes:
# demo 1: Search Ambiguity (Top list)
# demo 2: Favorites (List)
# demo 3: Home/No Widget (Center empty space)
# demo 4: Map View (Center pins)
# demo 5: Station Details (Bottom sheet details)

IMAGES = [
    {
        "input": "/Users/rehanvishwanath/Downloads/demo 1.PNG",
        "output": "current_search_friction.png",
        "text": "Which Wellington? Too many results.",
        "target": (0.5, 0.3),  # Middle of screen (search results)
        "shape": "ellipse"
    },
    {
        "input": "/Users/rehanvishwanath/Downloads/demo 4.PNG",
        "output": "current_map_clutter.png",
        "text": "Bikes or Docks? Must tap to know.",
        "target": (0.5, 0.5),  # Center map pin
        "shape": "ellipse"
    },
    {
        "input": "/Users/rehanvishwanath/Downloads/demo 5.PNG",
        "output": "current_hidden_details.png",
        "text": "Granular details hidden in sub-menu.",
        "target": (0.5, 0.8),  # Bottom sheet area
        "shape": "rectangle"
    },
    {
        "input": "/Users/rehanvishwanath/Downloads/demo 3.PNG",
        "output": "current_no_widget.png",
        "text": "No Widget - Zero Glanceability.",
        "target": (0.5, 0.4),  # Home screen empty space
        "shape": "ellipse"
    }
]

OUTPUT_DIR = os.path.expanduser("~/bikeshare-tui/assets")

def annotate(img_config):
    try:
        im = Image.open(img_config["input"])
        draw = ImageDraw.Draw(im)
        width, height = im.size
        
        # Calculate coordinates
        target_x = width * img_config["target"][0]
        target_y = height * img_config["target"][1]
        
        # Draw Red Highlight
        color = "#ff0000"
        line_width = 10
        radius = 150
        
        if img_config["shape"] == "ellipse":
            draw.ellipse(
                [target_x - radius, target_y - radius, target_x + radius, target_y + radius],
                outline=color,
                width=line_width
            )
        else:
            draw.rectangle(
                [target_x - 300, target_y - 100, target_x + 300, target_y + 100],
                outline=color,
                width=line_width
            )

        # Draw Line pointer
        text_x = target_x + 200
        text_y = target_y - 200
        # draw.line([target_x + radius, target_y - radius, text_x, text_y], fill=color, width=line_width)
        
        # Note: Drawing text requires a font, defaulting to simple drawing or just the shape
        # Since we might not have a nice ttf font loaded, we'll stick to the red circle visual
        # which is universal.
        
        output_path = os.path.join(OUTPUT_DIR, img_config["output"])
        im.save(output_path)
        print(f"Saved {output_path}")
        
    except Exception as e:
        print(f"Error processing {img_config['input']}: {e}")

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    for config in IMAGES:
        annotate(config)
