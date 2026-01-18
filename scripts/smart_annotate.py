import os
import base64
import json
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Define the tasks
TASKS = [
    {
        "input_path": "/Users/rehanvishwanath/Downloads/demo 1.PNG",
        "output_path": "/Users/rehanvishwanath/bikeshare-tui/assets/current_search_friction.png",
        "prompt": "Find the list of search results that show 'Wellington St'. I want the bounding box around the text list items.",
        "label": "For Wellington locations difficult for the user to figure out which is the appropriate one.",
        "shape": "rectangle"
    },
    {
        "input_path": "/Users/rehanvishwanath/Downloads/demo 4.PNG",
        "output_path": "/Users/rehanvishwanath/bikeshare-tui/assets/current_map_clutter.png",
        "prompt": "Find the green circle icon located roughly in the center-left of the image. It represents a location pin.",
        "label": "Ambiguous: Is this 10 bikes or 10 docks?",
        "shape": "circle"
    },
    {
        "input_path": "/Users/rehanvishwanath/Downloads/demo 5.PNG",
        "output_path": "/Users/rehanvishwanath/bikeshare-tui/assets/current_hidden_details.png",
        "prompt": "Find the small text that says '0 Ebikes' or 'Classic' or 'Docks'. I want the bounding box around that specific row of details.",
        "label": "Granular details hidden behind a tap.",
        "shape": "rectangle"
    },
    {
        "input_path": "/Users/rehanvishwanath/Downloads/demo 3.PNG",
        "output_path": "/Users/rehanvishwanath/bikeshare-tui/assets/current_no_widget.png",
        "prompt": "Identify the large empty space in the center of the screen where a widget typically would be. Return a bounding box for the center area.",
        "label": "No Widget available for quick status.",
        "shape": "circle"
    }
]

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_coordinates(image_path, prompt_text):
    base64_image = encode_image(image_path)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{prompt_text} Return the bounding box as a JSON object with keys 'ymin', 'xmin', 'ymax', 'xmax'. The values should be normalized from 0 to 1000 (where 1000 is the full width/height). Do not include markdown formatting, just the JSON."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        max_tokens=300
    )
    
    content = response.choices[0].message.content.strip()
    # Clean up markdown if present
    if content.startswith("```json"):
        content = content[7:-3]
    elif content.startswith("```"):
        content = content[3:-3]
        
    print(f"API Response for {os.path.basename(image_path)}: {content}")
    return json.loads(content)

def draw_annotation(task, bbox):
    im = Image.open(task["input_path"])
    draw = ImageDraw.Draw(im)
    width, height = im.size
    
    # Handle list of bboxes (pick the first one)
    if isinstance(bbox, list):
        bbox = bbox[0]
    
    # Handle wrapper object
    if "bounding_boxes" in bbox:
        bbox = bbox["bounding_boxes"][0]
        
    # Convert normalized 0-1000 coordinates to pixels
    xmin = (bbox["xmin"] / 1000) * width
    xmax = (bbox["xmax"] / 1000) * width
    ymin = (bbox["ymin"] / 1000) * height
    ymax = (bbox["ymax"] / 1000) * height
    
    # Draw Red Highlight
    color = "#ff0000"
    line_width = 8
    
    if task["shape"] == "circle":
        # Draw ellipse based on bbox
        draw.ellipse([xmin, ymin, xmax, ymax], outline=color, width=line_width)
        # Target point for line is center of circle
        target_pt = ((xmin + xmax) / 2, (ymin + ymax) / 2)
        # Edge point for line start
        edge_pt = (xmax, (ymin + ymax) / 2)
    else:
        # Rectangle
        draw.rectangle([xmin, ymin, xmax, ymax], outline=color, width=line_width)
        target_pt = (xmax, (ymin + ymax) / 2) # Right center edge
        edge_pt = target_pt

    # Draw Line and Text
    # We'll place text to the right or below depending on space
    
    # Try to load a font, fallback to default
    try:
        # Try a standard Mac font
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
    except:
        font = ImageFont.load_default()

    label = task["label"]
    
    # Position logic: Draw a line to the side
    # Line end point
    text_x = width - 50 if edge_pt[0] < width/2 else 50
    text_y = edge_pt[1]
    
    # If text is too long, wrap or just place it
    # Simplified: Draw line from object to a somewhat fixed position
    
    # Let's put the text near the object but slightly offset
    # If object is on left, put text on right
    if (xmin + xmax) / 2 < width / 2:
        text_anchor_x = xmax + 50
        text_anchor_y = ymin
    else:
        text_anchor_x = xmin - 600 # Rough guess for text width
        text_anchor_y = ymin
        
    # Ensure text stays on screen
    text_anchor_x = max(50, min(width - 600, text_anchor_x))
    text_anchor_y = max(50, min(height - 100, text_anchor_y))

    # Draw line from target to text
    # draw.line([edge_pt, (text_anchor_x, text_anchor_y + 30)], fill=color, width=5)
    
    # Draw text with red background for readability? Or just red text?
    # Let's draw text
    # draw.text((text_anchor_x, text_anchor_y), label, fill=color, font=font)
    
    # ALTERNATIVE: Just draw the red circle as requested, and maybe a simple line
    # The prompt asked for: Draw a line that points to it, and at the end of that line, it should say [Label]
    
    # Calculate text bounding box to draw background
    # text_bbox = draw.textbbox((text_anchor_x, text_anchor_y), label, font=font)
    # draw.rectangle(text_bbox, fill="white")
    # draw.text((text_anchor_x, text_anchor_y), label, fill=color, font=font)
    
    # Better line drawing
    line_end_x = text_anchor_x
    line_end_y = text_anchor_y + 20
    
    # Draw line
    draw.line([target_pt[0], target_pt[1], line_end_x, line_end_y], fill=color, width=5)
    
    # Draw text
    draw.text((line_end_x, line_end_y), label, fill=color, font=font)

    im.save(task["output_path"])
    print(f"Annotated {task['output_path']}")

def main():
    if not os.path.exists(os.path.dirname(TASKS[0]["output_path"])):
        os.makedirs(os.path.dirname(TASKS[0]["output_path"]))

    for task in TASKS:
        try:
            print(f"Processing {task['input_path']}...")
            bbox = get_coordinates(task["input_path"], task["prompt"])
            draw_annotation(task, bbox)
        except Exception as e:
            print(f"Failed to process {task['input_path']}: {e}")

if __name__ == "__main__":
    main()
