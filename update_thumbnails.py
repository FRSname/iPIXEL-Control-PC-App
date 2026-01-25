#!/usr/bin/env python3
"""
Update existing presets with thumbnail data
"""

import json
import os
import base64
from io import BytesIO
from PIL import Image

def generate_thumbnail(image_path, max_size=(64, 16)):
    """Generate a thumbnail from an image file and return as base64 string"""
    try:
        if not os.path.exists(image_path):
            print(f"Image not found: {image_path}")
            return None
        
        # Open and resize image
        img = Image.open(image_path)
        
        # Handle animated GIFs - get first frame
        if hasattr(img, 'is_animated') and img.is_animated:
            img.seek(0)
        
        # Convert RGBA to RGB if needed
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (0, 0, 0))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Crop to fill the thumbnail area (no black borders)
        img_ratio = img.width / img.height
        thumb_ratio = max_size[0] / max_size[1]
        
        if img_ratio > thumb_ratio:
            # Image is wider - crop width
            new_height = max_size[1]
            new_width = int(new_height * img_ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            left = (new_width - max_size[0]) // 2
            img = img.crop((left, 0, left + max_size[0], max_size[1]))
        else:
            # Image is taller - crop height
            new_width = max_size[0]
            new_height = int(new_width / img_ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            top = (new_height - max_size[1]) // 2
            img = img.crop((0, top, max_size[0], top + max_size[1]))
        
        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return img_str
    except Exception as e:
        print(f"Failed to generate thumbnail: {e}")
        return None

def update_presets():
    """Add thumbnails to existing image presets"""
    presets_file = "ipixel_presets.json"
    
    if not os.path.exists(presets_file):
        print("No presets file found")
        return
    
    # Load presets
    with open(presets_file, 'r') as f:
        presets = json.load(f)
    
    # Update image presets with thumbnails
    updated = 0
    for preset in presets:
        if preset.get('type') == 'image':
            image_path = preset.get('image_path', '')
            if image_path and not preset.get('thumbnail'):
                print(f"Generating thumbnail for: {preset.get('name', 'Unknown')}")
                thumbnail = generate_thumbnail(image_path)
                if thumbnail:
                    preset['thumbnail'] = thumbnail
                    updated += 1
                    print(f"  ✓ Thumbnail added")
                else:
                    print(f"  ✗ Failed to generate thumbnail")
    
    # Save updated presets
    if updated > 0:
        with open(presets_file, 'w') as f:
            json.dump(presets, f, indent=2)
        print(f"\n✓ Updated {updated} preset(s) with thumbnails")
    else:
        print("\nNo presets needed updating")

if __name__ == "__main__":
    update_presets()
