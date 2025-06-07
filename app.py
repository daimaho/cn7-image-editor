# Importar las librerías necesarias
from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageOps # Se añade ImageOps para el modo Cover
import io # Para manejar streams de bytes (archivos en memoria)
import requests # Para descargar imágenes desde URLs
import os # Para operaciones con el sistema de archivos, como verificar la existencia de fuentes

app = Flask(__name__)

# Define la ruta a tu plantilla base. Asegúrate de que este archivo esté en la misma carpeta que app.py
BASE_IMAGE_PATH = 'plantilla_base.jpg'

# Define la ruta a tu fuente. Asegúrate de que este archivo .ttf esté en la misma carpeta.
FONT_PATH = "Roboto-Bold.ttf"

@app.route('/generate-image', methods=['POST'])
def generate_image():
    """
    Endpoint para generar una imagen combinando una plantilla, una imagen destacada y un título.
    Espera un JSON en el cuerpo de la petición con 'image_url' (URL de la imagen destacada)
    y 'title' (texto del título).
    Devuelve la imagen generada como un archivo PNG.
    """
    data = request.json
    if not data:
        # Si no se recibe un cuerpo JSON, devuelve un error 400
        return jsonify({"error": "El cuerpo de la petición debe ser JSON"}), 400

    image_url = data.get('image_url')
    title_text = data.get('title')

    if not image_url or not title_text:
        # Si faltan los parámetros esenciales, devuelve un error 400
        return jsonify({"error": "Faltan 'image_url' o 'title' en la petición"}), 400

    try:
        # 1. Cargar la plantilla base
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)

        # 2. Cargar y procesar la imagen destacada (modo "Cover" de Placid)
        response = requests.get(image_url)
        featured_image = Image.open(io.BytesIO(response.content)).convert("RGBA")

        # Dimensiones del área donde la imagen destacada debe ir (de Placid: 7080 W x 844 H)
        target_width_img = 7080
        target_height_img = 844
        target_position_x_img = 0
        target_position_y_img = 0

        # Implementación del modo "Cover"
        # 1. Calcular la relación de aspecto de la imagen destacada y del área objetivo
        img_aspect = featured_image.width / featured_image.height
        target_aspect = target_width_img / target_height_img

        if img_aspect > target_aspect:
            # La imagen es más ancha que el objetivo, escalar por altura y recortar ancho
            new_height = target_height_img
            new_width = int(new_height * img_aspect)
            resized_featured_image = featured_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            # Calcular recorte para centrar horizontalmente
            left = (new_width - target_width_img) / 2
            top = 0
            right = left + target_width_img
            bottom = target_height_img
            cropped_featured_image = resized_featured_image.crop((left, top, right, bottom))
        else:
            # La imagen es más alta que el objetivo, escalar por ancho y recortar altura
            new_width = target_width_img
            new_height = int(new_width / img_aspect)
            resized_featured_image = featured_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            # Calcular recorte para centrar verticalmente
            left = 0
            top = (new_height - target_height_img) / 2
            right = target_width_img
            bottom = top + target_height_img
            cropped_featured_image = resized_featured_image.crop((left, top, right, bottom))

        # Pegar la imagen recortada en la posición definida
        base_image.paste(cropped_featured_image, 
                         (target_position_x_img, target_position_y_img)) 


        # 3. Añadir el título
        # Dimensiones del área de texto (de Placid: 951 W x 331 H)
        text_area_width = 951
        text_area_height = 331
        text_area_x = 62 # Posición X de la esquina superior izquierda del área
        text_area_y = 873 # Posición Y de la esquina superior izquierda del área

        text_color = (255, 255, 255, 255) # Blanco en formato RGBA

        try:
            if os.path.exists(FONT_PATH):
                font_size = 80 # Tamaño inicial de la fuente, se ajustará
                font = ImageFont.truetype(FONT_PATH, size=font_size)
            else:
                print(f"Advertencia: Fuente '{FONT_PATH}' no encontrada. Usando fuente por defecto.")
                font = ImageFont.load_default()
        except IOError:
            print("Advertencia: No se pudo cargar la fuente. Usando fuente por defecto.")
            font = ImageFont.load_default()

        # Ajuste de tamaño de fuente para que el texto quepa en el área
        while True:
            # Calcula el tamaño del texto con el tamaño de fuente actual
            bbox = draw.textbbox((0,0), title_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Si el texto cabe en el área, salimos del bucle
            if text_width <= text_area_width and text_height <= text_area_height:
                break
            
            # Si no cabe, reduce el tamaño de la fuente
            font_size -= 1
            if font_size <= 10: # Límite inferior para evitar bucles infinitos
                print("Advertencia: El texto no cabe en el área con un tamaño de fuente razonable.")
                break # Salir si la fuente es demasiado pequeña
            
            if os.path.exists(FONT_PATH):
                font = ImageFont.truetype(FONT_PATH, size=font_size)
            else:
                font = ImageFont.load_default() # Usar por defecto si la fuente no está disponible


        # Calcular la posición para centrar el texto dentro de su área (951x331)
        text_bbox = draw.textbbox((0,0), title_text, font=font)
        text_width_final = text_bbox[2] - text_bbox[0]
        text_height_final = text_bbox[3] - text_bbox[1]

        # Posición final para el texto dentro del área definida por text_area_x, text_area_y
        # Centrado horizontalmente dentro del área
        text_x_final = text_area_x + (text_area_width - text_width_final) / 2
        # Centrado verticalmente dentro del área
        text_y_final = text_area_y + (text_area_height - text_height_final) / 2

        draw.text((text_x_final, text_y_final), title_text, font=font, fill=text_color)

        # --- SALIDA DE LA IMAGEN ---
        img_byte_arr = io.BytesIO()
        base_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        return send_file(img_byte_arr, mimetype='image/png')

    except Exception as e:
        print(f"Error al generar la imagen: {e}")
        return jsonify({"error": f"Error interno del servidor: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
