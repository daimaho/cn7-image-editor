# Importar las librerías necesarias
from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import io
import requests
import os
import json
import base64
import time

# Librerías para Cloudinary
import cloudinary
import cloudinary.uploader


app = Flask(__name__)

# Rutas base para plantillas y fuentes (ahora no son hardcodeadas, se construyen dinámicamente)
TEMPLATES_FOLDER = os.path.join(os.path.dirname(__file__), 'templates') # Asume una carpeta 'templates'
FONTS_FOLDER = os.path.join(os.path.dirname(__file__), 'fonts') # Asume una carpeta 'fonts'

# Factor de interlineado
LINE_SPACING_FACTOR = 0.3 

# --- Configuración de Cloudinary ---
cloudinary.config( 
  cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', 'tu_cloud_name'), 
  api_key = os.environ.get('CLOUDINARY_API_KEY', 'tu_api_key'), 
  api_secret = os.environ.get('CLOUDINARY_API_SECRET', 'tu_api_secret') 
)

@app.route('/generate-image', methods=['POST'])
def generate_image():
    """
    Endpoint para generar una imagen combinando una plantilla, una imagen destacada y un título.
    Ahora espera la imagen destacada como 'image_file', el título como 'title_text',
    el nombre de la plantilla base como 'template_name' y el nombre de la fuente como 'font_name'.
    Guarda la imagen generada en Cloudinary y devuelve su URL pública.
    """
    if 'image_file' not in request.files:
        return jsonify({"error": "Falta el archivo de imagen en la petición (campo 'image_file')."}), 400
    
    image_file = request.files['image_file']
    title_text = request.form.get('title_text')
    # --- NUEVOS PARÁMETROS: template_name y font_name ---
    template_name = request.form.get('template_name')
    font_name = request.form.get('font_name')

    if not title_text or not template_name or not font_name:
        return jsonify({"error": "Faltan 'title_text', 'template_name' o 'font_name' en la petición."}), 400

    # Construir las rutas completas de los archivos de plantilla y fuente
    base_image_path_full = os.path.join(TEMPLATES_FOLDER, template_name)
    font_path_full = os.path.join(FONTS_FOLDER, font_name)

    # Validar que los archivos existen
    if not os.path.exists(base_image_path_full):
        return jsonify({"error": f"Plantilla base no encontrada: {template_name}"}), 404
    if not os.path.exists(font_path_full):
        return jsonify({"error": f"Fuente no encontrada: {font_name}"}), 404

    try:
        # 1. Cargar la plantilla base (ahora dinámica)
        base_image = Image.open(base_image_path_full).convert("RGBA")
        draw = ImageDraw.Draw(base_image)

        # 2. Cargar y procesar la imagen destacada
        featured_image = Image.open(image_file.stream).convert("RGBA")

        target_width_img = 1080
        target_height_img = 844
        target_position_x_img = 0
        target_position_y_img = 0

        original_aspect_ratio = featured_image.width / featured_image.height
        new_width_scaled = int(target_height_img * original_aspect_ratio)
        new_height_scaled = target_height_img

        scaled_featured_image = featured_image.resize((new_width_scaled, new_height_scaled), Image.Resampling.LANCZOS)

        if new_width_scaled < target_width_img:
            # Aquí es importante usar la base_image_path_full para el fondo desenfocado
            background_fill = Image.open(base_image_path_full).convert("RGBA")
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
        # --- CAMBIOS AQUÍ: Ajuste de posición y tamaño de la caja de texto ---
        # Los valores de Placid serán variables en la request, pero aquí se usan los de la última configuración general.
        # En la request de Make.com se deberán enviar los valores específicos para cada plantilla.
        text_area_width = 951 
        text_area_height = 331
        text_area_x = 62 
        text_area_y = 873 

        # Ajustes de posición y tamaño basados en la plantilla *actualmente cargada en app.py*
        # Para CN7: text_area_y -= 47
        # Para PL: text_area_y = 978 (posición Y directa)
        # Necesitamos que estos sean configurables si las plantillas tienen áreas de texto diferentes.
        # Por ahora, mantendré los últimos de CN7, pero lo ideal es pasarlos como parámetros también.
        text_area_y -= 47 
        reduction_factor = 0.10 
        reduced_height_amount = int(text_area_height * reduction_factor)
        text_area_height -= reduced_height_amount
        text_area_y += reduced_height_amount 


        text_color = (255, 255, 255, 255) 

        try:
            # --- CAMBIO AQUÍ: Fuente cargada dinámicamente ---
            if os.path.exists(font_path_full):
                font_size = 65 # Tamaño inicial de la fuente, ajustar si es necesario para cada fuente
                font = ImageFont.truetype(font_path_full, size=font_size)
            else:
                print(f"Advertencia: Fuente '{font_name}' no encontrada en '{FONTS_FOLDER}'. Usando fuente por defecto.")
                font = ImageFont.load_default()
        except IOError:
            print(f"Advertencia: No se pudo cargar la fuente '{font_name}'. Usando fuente por defecto.")
            font = ImageFont.load_default()

        # --- Lógica para texto multi-línea y ajuste de fuente ---
        lines = []
        words = title_text.split() 

        optimal_font_size = 80 # Empezar con un tamaño más grande para el texto, ajustar si es necesario
        max_lines = 4 

        while True:
            temp_font = ImageFont.truetype(font_path_full, size=optimal_font_size) if os.path.exists(font_path_full) else ImageFont.load_default()
            
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
            
            temp_font = ImageFont.truetype(font_path_full, size=optimal_font_size) if os.path.exists(font_path_full) else ImageFont.load_default()

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
        # Se genera un nombre único para la imagen
        public_id_base = f"make_image_{os.urandom(4).hex()}" 
        
        base_image.save(img_byte_arr, format='PNG') 
        img_byte_arr.seek(0) 

        cloudinary_image_url = None
        
        try:
            cloudinary_upload_stream = io.BytesIO(img_byte_arr.getvalue())
            cloudinary_upload_stream.seek(0)

            # Usar una carpeta de Cloudinary diferente según la plantilla para organización
            cloudinary_folder = "cn7_images" if "cn7" in template_name else "pl_images" 
            
            cloudinary_response = cloudinary.uploader.upload(cloudinary_upload_stream, 
                                                            folder=cloudinary_folder, 
                                                            public_id=public_id_base, 
                                                            resource_type="image",
                                                            format="jpg") 
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
