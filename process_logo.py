import os
from PIL import Image

def process_image(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return
        
    img = Image.open(input_path).convert("RGBA")
    datas = img.getdata()

    new_data = []
    # Gold: RGB(212, 175, 55)
    for item in datas:
        r, g, b, a = item
        # Calculate grayscale intensity (brightness)
        intensity = (r + g + b) / 3.0
        
        if a == 0:
            new_data.append((212, 175, 55, 0))
            continue
            
        # The darker the pixel, the more opaque it should be
        # White background (intensity ~ 255) becomes alpha ~ 0
        new_alpha = int(255 - intensity)
        
        # Combine with original alpha
        final_alpha = int(min(new_alpha, a))
        
        new_data.append((212, 175, 55, final_alpha))

    img.putdata(new_data)
    img.save(output_path, "PNG")
    print(f"Processed image saved to {output_path}")

if __name__ == "__main__":
    process_image(r"d:\masjid\static\img\logo.png", r"d:\masjid\static\img\logo.png")
