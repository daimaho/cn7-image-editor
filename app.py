# Importar las librerías necesarias
from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import io
import requests # Todavía necesario si la imagen destacada es una URL de WordPress para N8N para descargarla
import os
import json
import base64
import time # Importar la librería time para añadir retrasos

# Librerías para Cloudinary
import cloudinary
import cloudinary.uploader


app = Flask(__name__)

# Define la ruta a tu plantilla base. Asegúrate de que este archivo esté en la misma carpeta que app.py
BASE_IMAGE_PATH = 'plantilla_base.jpg'

# Define la ruta a tu fuente. Asegúrate de que este archivo .ttf esté en la misma carpeta.
FONT_PATH = "Roboto-Bold.ttf"

# Factor de interlineado (ej. 0.2 = 20% de espacio adicional por línea)
LINE_SPACING_FACTOR = 0.3 

# --- Configuración de Cloudinary ---
# ¡IMPORTANTE! Configura estas variables de entorno en Railway para tu servicio.
# CLOUD_NAME, API_KEY, API_SECRET se obtienen de tu Dashboard de Cloudinary.
cloudinary.config( 
  cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', 'tu_cloud_name'), 
  api_key = os.environ.get('CLOUDINARY_API_KEY', 'tu_api_key'), 
  api_secret = os.environ.get('CLOUDINARY_API_SECRET', 'tu_api_secret') 
)

@app.route('/generate-image', methods=['POST'])
def generate_image():
    """
    Endpoint para generar una imagen combinando una plantilla, una imagen destacada y un título.
    Ahora espera la imagen destacada como un archivo binario en 'request.files['image_file']'
    y el título como un campo de formulario 'title_text' en 'request.form'.
    Guarda la imagen generada en Cloudinary y devuelve su URL pública.
    """
    if 'image_file' not in request.files:
        return jsonify({"error": "Falta el archivo de imagen en la petición (campo 'image_file')."}), 400
    
    image_file = request.files['image_file']
    title_text = request.form.get('title_text') # Obtener el título del formulario

    if not title_text:
        return jsonify({"error": "Falta el título en la petición (campo 'title_text')."}), 400

    try:
        # 1. Cargar la plantilla base
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)

        # 2. Cargar y procesar la imagen destacada (directamente desde el archivo recibido)
        featured_image = Image.open(image_file.stream).convert("RGBA") # Leer directamente del stream del archivo

        target_width_img = 1080
        target_height_img = 844
        target_position_x_img = 0
        target_position_y_img = 0

        original_aspect_ratio = featured_image.width / featured_image.height
        new_width_scaled = int(target_height_img * original_aspect_ratio)
        new_height_scaled = target_height_img

        scaled_featured_image = featured_image.resize((new_width_scaled, new_height_scaled), Image.Resampling.LANCZOS)

        if new_width_scaled < target_width_img:
            background_fill = Image.open(BASE_IMAGE_PATH).convert("RGBA")
            background_fill = ImageOps.fit(background_fill, 
                                          (target_width_img, target_height_img), 
                                          method=Image.Resampling.LANCZOS, 
                                          centering=(0.5, 0.5))
            background_fill = background_fill.filter(ImageFilter.GaussianBlur(radius=80))

            base_image.paste(background_fill, 
                             (target_position_x_img, target_position_y_img))

            paste_x = target_position_x_img + (target_width_img - scaled_featured_image.width) // 2
            paste_y = target_position_y_img + (target_height_img - scaled_featured_image.height) // 2
            
            base_image.paste(scaled_featured_image, (paste_x, paste_y), scaled_featured_image)

        else:
            left_crop = (scaled_featured_image.width - target_width_img) // 2
            right_crop = left_crop + target_width_img
            cropped_image = scaled_featured_image.crop((left_crop, 0, right_crop, target_height_img))
            
            base_image.paste(cropped_image, 
                             (target_position_x_img, target_position_y_img)) 


        # 3. Añadir el título
        text_area_width = 951
        text_area_height = 331
        text_area_x = 62 
        text_area_y = 873 

        text_area_y -= 47 
        
        reduction_factor = 0.10 
        reduced_height_amount = int(text_area_height * reduction_factor)
        text_area_height -= reduced_height_amount
        text_area_y += reduced_height_amount 

        text_color = (255, 255, 255, 255) 

        try:
            if os.path.exists(FONT_PATH):
                font_size = 80
                font = ImageFont.truetype(FONT_PATH, size=font_size)
            else:
                print(f"Advertencia: Fuente '{FONT_PATH}' no encontrada. Usando fuente por defecto.")
                font = ImageFont.load_default()
        except IOError:
            print("Advertencia: No se pudo cargar la fuente. Usando fuente por defecto.")
            font = ImageFont.load_default()

        # --- Lógica para texto multi-línea y ajuste de fuente ---
        lines = []
        words = title_text.split() 

        optimal_font_size = 100 
        max_lines = 4 

        while True:
            temp_font = ImageFont.truetype(FONT_PATH, size=optimal_font_size) if os.path.exists(FONT_PATH) else ImageFont.load_default()
            
            test_lines = []
            test_current_line_words = []
            
            for word in words:
                potential_line = " ".join(test_current_line_words + [word])
                bbox = draw.textbbox((0,0), potential_line, font=temp_font)
                test_width = bbox[2] - bbox[0]
                
                if test_width <= text_area_width:
                    test_current_line_words.append(word)
                else:
                    if test_current_line_words: 
                        test_lines.append(" ".join(test_current_line_words))
                    test_current_line_words = [word] 
            
            if test_current_line_words: 
                test_lines.append(" ".join(test_current_line_words))

            try: 
                line_height_estimate = temp_font.getbbox("Tg")[3] - temp_font.getbbox("Tg")[1]
            except AttributeError: 
                line_height_estimate = temp_font.getsize("Tg")[1]

            total_text_height = (len(test_lines) * line_height_estimate) + (max(0, len(test_lines) - 1) * int(line_height_estimate * LINE_SPACING_FACTOR))
            
            if total_text_height <= text_area_height and len(test_lines) <= max_lines:
                lines = test_lines 
                font = temp_font 
                break
            
            optimal_font_size -= 1
            if optimal_font_size <= 10: 
                print("Advertencia: El texto no cabe en el área con un tamaño de fuente razonable.")
                lines = test_lines 
                font = temp_font
                break
            
            temp_font = ImageFont.truetype(FONT_PATH, size=optimal_font_size) if os.path.exists(FONT_PATH) else ImageFont.load_default()

        y_offset = text_area_y 

        try: 
            base_line_height = font.getbbox("Tg")[3] - font.getbbox("Tg")[1]
        except AttributeError: 
            base_line_height = font.getsize("Tg")[1]

        extra_spacing_per_line = int(base_line_height * LINE_SPACING_FACTOR)

        total_text_block_height = (len(lines) * base_line_height) + (max(0, len(lines) - 1) * extra_spacing_per_line)
        if total_text_block_height < text_area_height:
            y_offset += (text_area_height - total_text_block_height) / 2

        for line in lines:
            bbox = draw.textbbox((0,0), line, font=font)
            line_width = bbox[2] - bbox[0]
            x_final = text_area_x + (text_area_width - line_width) / 2
            
            draw.text((x_final, y_offset), line, font=font, fill=text_color)
            y_offset += base_line_height + extra_spacing_per_line 

        # --- Subir la imagen generada a Cloudinary ---
        img_byte_arr = io.BytesIO()
        image_filename = f"cn7_noticia_{os.urandom(4).hex()}.png" # Nombre único

        base_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0) # Mueve el puntero al inicio del stream para la subida

        cloudinary_image_url = None
        
        try:
            # Crea una copia del stream para Cloudinary
            cloudinary_upload_stream = io.BytesIO(img_byte_arr.getvalue())
            cloudinary_upload_stream.seek(0)

            cloudinary_response = cloudinary.uploader.upload(cloudinary_upload_stream, 
                                                            folder="cn7_images", 
                                                            public_id=image_filename.split('.')[0], 
                                                            resource_type="image")
            cloudinary_image_url = cloudinary_response['secure_url']
            print(f"Imagen subida a Cloudinary: {cloudinary_image_url}")
        except Exception as cl_e:
            print(f"Error al subir la imagen a Cloudinary: {cl_e}")

        
        # --- Devolver la URL de la imagen de Cloudinary ---
        if cloudinary_image_url:
            return jsonify({"image_url": cloudinary_image_url}), 200
        else:
            return jsonify({"error": "No se pudo generar la URL pública de la imagen en Cloudinary."}), 500

    except Exception as e:
        print(f"Error al generar la imagen: {e}")
        return jsonify({"error": f"Error interno del servidor: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
