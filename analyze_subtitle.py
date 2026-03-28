#!/usr/bin/env python3
"""Analyze subtitle position in extracted frames."""
import os
from PIL import Image

output_dir = "outputs/subtitle_check"

# Analyze each frame
for filename in sorted(os.listdir(output_dir)):
    if filename.endswith('.png'):
        filepath = os.path.join(output_dir, filename)
        img = Image.open(filepath)
        width, height = img.size
        
        # Convert to RGB and analyze bottom half of image
        img_rgb = img.convert('RGB')
        
        # Look for white text in the bottom half
        # White text has high RGB values
        found_white = False
        white_y_positions = []
        
        # Scan from top to bottom in the lower half of image
        for y in range(height // 2, height):
            white_pixels = 0
            for x in range(width):
                r, g, b = img_rgb.getpixel((x, y))
                # Check if pixel is white or near-white (subtitle text)
                if r > 200 and g > 200 and b > 200:
                    white_pixels += 1
            
            # If significant white pixels found, record position
            if white_pixels > width * 0.1:  # At least 10% of width has white
                white_y_positions.append(y)
                found_white = True
        
        if white_y_positions:
            # Get the topmost white position (subtitle top)
            subtitle_top = min(white_y_positions)
            subtitle_bottom = max(white_y_positions)
            print(f"{filename}: Subtitle Y position = {subtitle_top}-{subtitle_bottom} (height={height})")
        else:
            print(f"{filename}: No subtitle detected")

print("\nIf subtitle Y positions vary significantly, the subtitle is jumping.")
