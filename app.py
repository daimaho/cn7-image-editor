# Importar las librerías necesarias
from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont # Pillow para manipulación de imágenes
import io # Para manejar streams de bytes (archivos en memoria)
import requests # Para descargar imágenes desde URLs
import os # Para operaciones con el sistema de archivos, como verificar la existencia de fuentes

app = Flask(__name__)

# Define la ruta a tu plantilla base. Asegúrate de que este archivo esté en la misma carpeta que app.py
BASE_IMAGE_PATH = 'plantilla_base.jpg'

# Define la ruta a tu fuente. Asegúrate de que este archivo .ttf esté en la misma carpeta.
# Si no usas esta fuente, el script intentará cargar una por defecto.
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
        # Se convierte a "RGBA" para asegurar soporte de transparencia si la imagen original lo tiene.
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)

        # 2. Cargar la imagen destacada desde la URL
        response = requests.get(image_url)
        # Se convierte a "RGBA" para manejar la transparencia de la imagen destacada.
        featured_image = Image.open(io.BytesIO(response.content)).convert("RGBA")

        # --- AJUSTES DE TAMAÑO Y POSICIÓN DE LA IMAGEN DESTACADA ---
        # Estos valores deben ser ajustados según el diseño de tu plantilla.
        # Basado en la captura de Placid (foto.jpg) que muestra un tamaño de 7080 W x 844 H
        # y una posición de 0,0 para la imagen destacada.
        featured_image_width = 7080
        featured_image_height = 844
        featured_image_position_x = 0
        featured_image_position_y = 0

        featured_image = featured_image.resize((featured_image_width, featured_image_height))
        
        # Pegar la imagen destacada sobre la plantilla base
        base_image.paste(featured_image, 
                         (featured_image_position_x, featured_image_position_y), 
                         featured_image) # featured_image como máscara para transparencia

        # 3. Añadir el título
        # --- AJUSTES DE FUENTE, COLOR Y POSICIÓN DEL TÍTULO ---
        # Basado en la captura de Placid (texto.jpg): Posición 62x873, tamaño 951x331 (aprox)
        # Fuente: Roboto Bold, Color: #FFFFFF (Blanco)
        try:
            # Cargar la fuente. Asegúrate de que FONT_PATH es correcto.
            if os.path.exists(FONT_PATH):
                # El tamaño de la fuente (80) es un valor inicial, ajusta según sea necesario para tu diseño
                font = ImageFont.truetype(FONT_PATH, size=80) 
            else:
                print(f"Advertencia: Fuente '{FONT_PATH}' no encontrada. Usando fuente por defecto.")
                font = ImageFont.load_default()
        except IOError:
            print("Advertencia: No se pudo cargar la fuente. Usando fuente por defecto.")
            font = ImageFont.load_default()

        text_color = (255, 255, 255, 255) # Blanco en formato RGBA

        # Posición inicial del texto del título.
        # Estos valores (text_x, text_y) definen la esquina superior izquierda del texto.
        text_x = 62 
        text_y = 873 

        # Puedes ajustar la posición del texto para centrarlo o alinearlo según tu diseño.
        # Por ejemplo, para centrar horizontalmente en un área específica (ej. un ancho de 951):
        # text_bbox = draw.textbbox((0,0), title_text, font=font) # bbox devuelve (left, top, right, bottom)
        # text_width = text_bbox[2] - text_bbox[0]
        # target_area_width = 951 # Ancho aproximado del área de texto en tu diseño
        # center_x_in_area = (target_area_width - text_width) / 2
        # text_x = 62 + center_x_in_area # Si el área comienza en 62

        draw.text((text_x, text_y), title_text, font=font, fill=text_color)

        # --- SALIDA DE LA IMAGEN ---
        # Guardar la imagen en un buffer de bytes para enviarla.
        # Se guarda como PNG, que soporta transparencia (RGBA), resolviendo el error anterior.
        img_byte_arr = io.BytesIO()
        base_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0) # Mueve el puntero al inicio del stream

        # Enviar la imagen como respuesta HTTP
        return send_file(img_byte_arr, mimetype='image/png')

    except Exception as e:
        # Captura cualquier error durante el proceso y devuelve una respuesta de error 500
        print(f"Error al generar la imagen: {e}")
        return jsonify({"error": f"Error interno del servidor: {str(e)}"}), 500

if __name__ == '__main__':
    # Cuando se ejecuta localmente o en un entorno como Railway, se usa el puerto
    # definido por la variable de entorno 'PORT', o el puerto 8000 por defecto.
    # El host '0.0.0.0' hace que la aplicación sea accesible desde cualquier IP.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
