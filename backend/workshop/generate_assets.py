import os
from PIL import Image, ImageDraw, ImageFont

def generate_sample_images():
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "frontend", "static", "img", "sample_jewellery")
    os.makedirs(output_dir, exist_ok=True)
    
    samples = [
        # (filename, bg_color, title, subtitle, shape_type)
        ("peacock_ring_ref.jpg", "#fbf9f5", "REFERENCE SKETCH", "22K Peacock Ring (Front/Side)", "ring_sketch"),
        ("peacock_ring_final.jpg", "#ffffff", "FINAL CRAFTED PIECE", "22K Antique Peacock Ring - Hallmark 916", "ring_final"),
        ("diamond_necklace_ref.jpg", "#fbf9f5", "CUSTOMER SPECIFICATION", "VVS Diamond Bridal Choker Design", "necklace_sketch"),
        ("diamond_necklace_final.jpg", "#ffffff", "FINAL CRAFTED PIECE", "Certified Natural Diamond Choker", "necklace_final"),
        ("temple_bangle_ref.jpg", "#fbf9f5", "REFERENCE BLUEPRINT", "Lakshmi Kada 2.6 Size 45g", "bangle_sketch"),
        ("temple_bangle_final.jpg", "#ffffff", "FINAL CRAFTED PIECE", "22K Hand-Engraved Temple Bangle", "bangle_final"),
        ("emerald_pendant_ref.jpg", "#fbf9f5", "REFERENCE SKETCH", "Zambian Emerald & CZ Halo", "pendant_sketch"),
        ("emerald_pendant_final.jpg", "#ffffff", "FINAL CRAFTED PIECE", "Natural Emerald Masterpiece", "pendant_final"),
    ]
    
    for filename, bg, title, subtitle, shape in samples:
        filepath = os.path.join(output_dir, filename)
        img = Image.new("RGB", (800, 800), bg)
        draw = ImageDraw.Draw(img)
        
        # Subtle vitrine border
        draw.rounded_rectangle([20, 20, 780, 780], radius=24, outline="#e5e5ea", width=2)
        
        # Draw jewellery representation
        cx, cy = 400, 380
        if "ring" in shape:
            if "sketch" in shape:
                # Pencil style sketch ring
                draw.ellipse([cx - 150, cy - 80, cx + 150, cy + 180], outline="#636366", width=5)
                draw.ellipse([cx - 110, cy - 50, cx + 110, cy + 150], outline="#8e8e93", width=3)
                # Crown
                draw.polygon([(cx - 70, cy - 80), (cx, cy - 180), (cx + 70, cy - 80)], outline="#3a3a3c", width=4)
                draw.ellipse([cx - 25, cy - 140, cx + 25, cy - 90], outline="#1c1c1e", width=3)
            else:
                # Polished gold ring
                draw.ellipse([cx - 155, cy - 85, cx + 155, cy + 185], fill="#dfb15b", outline="#c59837", width=6)
                draw.ellipse([cx - 115, cy - 55, cx + 115, cy + 155], fill=bg, outline="#c59837", width=4)
                # Crown with brilliant gems
                draw.polygon([(cx - 75, cy - 85), (cx, cy - 195), (cx + 75, cy - 85)], fill="#e8c374", outline="#b88928", width=5)
                draw.ellipse([cx - 30, cy - 150, cx + 30, cy - 90], fill="#ff3b30", outline="#c59837", width=3) # Ruby accent
                # Highlights
                draw.arc([cx - 140, cy - 70, cx + 140, cy + 170], start=190, end=270, fill="#fff2b2", width=6)
        elif "necklace" in shape:
            if "sketch" in shape:
                draw.arc([cx - 220, cy - 180, cx + 220, cy + 220], start=20, end=160, fill="#636366", width=5)
                draw.arc([cx - 180, cy - 140, cx + 180, cy + 180], start=20, end=160, fill="#8e8e93", width=3)
                for i in range(-5, 6):
                    x = cx + i * 35
                    draw.ellipse([x - 12, cy + 120 - abs(i)*8, x + 12, cy + 144 - abs(i)*8], outline="#3a3a3c", width=3)
            else:
                draw.arc([cx - 220, cy - 180, cx + 220, cy + 220], start=20, end=160, fill="#d4af37", width=10)
                draw.arc([cx - 180, cy - 140, cx + 180, cy + 180], start=20, end=160, fill="#f3e5ab", width=6)
                for i in range(-6, 7):
                    x = cx + i * 32
                    y = cy + 115 - abs(i)*6
                    draw.ellipse([x - 14, y, x + 14, y + 28], fill="#ffffff", outline="#0071e3", width=2) # Sparkling diamond drops
        elif "bangle" in shape:
            if "sketch" in shape:
                draw.ellipse([cx - 180, cy - 140, cx + 180, cy + 140], outline="#636366", width=6)
                draw.ellipse([cx - 140, cy - 100, cx + 140, cy + 100], outline="#8e8e93", width=4)
            else:
                draw.ellipse([cx - 190, cy - 150, cx + 190, cy + 150], fill="#dfb15b", outline="#b88928", width=12)
                draw.ellipse([cx - 135, cy - 95, cx + 135, cy + 95], fill=bg, outline="#b88928", width=5)
                # Engraved motifs
                for ang in range(0, 360, 30):
                    rad = 162
                    import math
                    px = cx + rad * math.cos(math.radians(ang))
                    py = cy + rad * 0.78 * math.sin(math.radians(ang))
                    draw.ellipse([px-6, py-6, px+6, py+6], fill="#e03030")
        else: # pendant
            if "sketch" in shape:
                draw.ellipse([cx - 120, cy - 80, cx + 120, cy + 160], outline="#636366", width=5)
                draw.rectangle([cx - 30, cy - 170, cx + 30, cy - 90], outline="#3a3a3c", width=4)
            else:
                draw.ellipse([cx - 120, cy - 80, cx + 120, cy + 160], fill="#00a86b", outline="#dfb15b", width=10) # Emerald
                draw.rectangle([cx - 30, cy - 170, cx + 30, cy - 90], fill="#dfb15b", outline="#b88928", width=4)
                draw.ellipse([cx - 15, cy - 150, cx + 15, cy - 120], fill=bg)

        # Header Pill
        tag_bg = "#e8e8ed" if "sketch" in shape or "CUSTOMER" in title else "#0071e3"
        tag_txt = "#1d1d1f" if "sketch" in shape or "CUSTOMER" in title else "#ffffff"
        draw.rounded_rectangle([cx - 160, 60, cx + 160, 96], radius=999, fill=tag_bg)
        draw.text((cx, 78), title, fill=tag_txt, anchor="mm")
        
        # Subtitle caption at bottom
        draw.text((cx, 720), subtitle, fill="#1d1d1f", anchor="mm")
        
        img.save(filepath, quality=95)
        print(f"Generated sample: {filename}")

if __name__ == '__main__':
    generate_sample_images()
