from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont
import io
import requests
import os

app = Flask(__name__)

# Define la ruta a tu plantilla base
BASE_IMAGE_PATH = 'plantilla_base.jpg'

@app.route('/generate-image', methods=['POST'])
def generate_image():
    data = request.json
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    image_url = data.get('image_url')
    title_text = data.get('title')
    logo_url = data.get('logo_url', None) # Opcional: URL de tu logo si lo quieres pegar

    if not image_url or not title_text:
        return jsonify({"error": "Missing 'image_url' or 'title' in request"}), 400

    try:
        # Cargar la plantilla base
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)

        # Cargar la imagen destacada desde la URL
        response = requests.get(image_url)
        featured_image = Image.open(io.BytesIO(response.content)).convert("RGBA")

        # Redimensionar la imagen destacada (ajusta estos valores según sea necesario)
        # Ejemplo: 7080x844 según tu captura de Placid (foto.jpg)
        featured_image = featured_image.resize((7080, 844)) 

        # Pegar la imagen destacada en la posición (ajusta estos valores según sea necesario)
        # Ejemplo: Posición X=0, Y=0 según tu captura de Placid (foto.jpg)
        base_image.paste(featured_image, (0, 0), featured_image)

        # Añadir el título
        # Ejemplo: Título en posición 62x873 con tamaño 903x331, fuente Roboto Bold, blanco
        # Necesitarás descargar la fuente o usar una fuente por defecto si no tienes una.
        # Puedes usar una fuente genérica si no tienes Roboto Bold instalada en el entorno.
        try:
            font_path = "Roboto-Bold.ttf" # Asegúrate de que esta fuente esté en tu directorio o usa una por defecto
            if not os.path.exists(font_path):
                 # Puedes añadir un paso para descargar la fuente si no está disponible,
                 # o usar la fuente por defecto de PIL si no se especifica
                print(f"Warning: Font '{font_path}' not found. Using default font.")
                font = ImageFont.load_default()
            else:
                font = ImageFont.truetype(font_path, size=80) # Ajusta el tamaño de la fuente
        except IOError:
            print("Warning: Could not load font. Using default font.")
            font = ImageFont.load_default()

        text_color = (255, 255, 255, 255) # Blanco (RGBA)

        # Calcular la posición del texto para centrarlo o posicionarlo
        # (Ejemplo simplificado, ajustar X, Y según tu diseño)
        text_x = 62 # Posición X desde tu captura de texto.jpg
        text_y = 873 # Posición Y desde tu captura de texto.jpg

        # Opcional: ajustar posición para centrar el texto horizontalmente en un área
        # text_width, text_height = draw.textsize(title_text, font=font)
        # image_width, image_height = base_image.size
        # text_x = (image_width - text_width) / 2 # Para centrar horizontalmente

        draw.text((text_x, text_y), title_text, font=font, fill=text_color)

        # Opcional: Pegar el logo (si se proporciona una URL de logo)
        if logo_url:
            response = requests.get(logo_url)
            logo_image = Image.open(io.BytesIO(response.content)).convert("RGBA")
            # Redimensiona el logo y pégalo en la posición deseada
            # logo_image = logo_image.resize((LOGO_WIDTH, LOGO_HEIGHT)) 
            # base_image.paste(logo_image, (LOGO_X, LOGO_Y), logo_image)


        # Guardar la imagen en un buffer de bytes
        img_byte_arr = io.BytesIO()
        base_image.save(img_byte_arr, format='JPEG') # Puedes cambiar el formato a PNG si lo prefieres
        img_byte_arr.seek(0)

        # Enviar la imagen como respuesta
        return send_file(img_byte_arr, mimetype='image/jpeg')

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # El puerto 8000 es comúnmente usado en Railway para aplicaciones web
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 8000))