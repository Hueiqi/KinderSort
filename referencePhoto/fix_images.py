import os
from PIL import Image
import face_recognition

# Input and output folders
input_folder = r"C:\Users\Lenovo\Documents\GitHub\KinderSort\referencePhoto"
output_folder = os.path.join(input_folder, "fixed")
os.makedirs(output_folder, exist_ok=True)

for filename in os.listdir(input_folder):
    if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp')):
        img_path = os.path.join(input_folder, filename)
        try:
            # Open and inspect
            img = Image.open(img_path)
            print(f"🔍 {filename} → Mode: {img.mode}, Format: {img.format}, Size: {img.size}")

            # Force conversion to 8-bit RGB
            img = img.convert("RGB")

            # Save as clean PNG
            new_name = os.path.splitext(filename)[0] + "_fixed.png"
            fixed_path = os.path.join(output_folder, new_name)
            img.save(fixed_path, "PNG")

            # Verify face detection
            image_array = face_recognition.load_image_file(fixed_path)
            faces = face_recognition.face_locations(image_array)

            if len(faces) > 0:
                print(f"✅ Converted & Face Found: {filename} → {new_name} ({len(faces)} face(s))")
            else:
                print(f"⚠️ Converted but NO face detected: {filename} → {new_name}")

        except Exception as e:
            print(f"❌ Failed: {filename} - {e}")
