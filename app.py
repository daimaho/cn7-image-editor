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

        # Implementación del modo "Cover" mejorado
        # Se redimensiona y recorta la imagen para que encaje perfectamente en el área.
        # Esto previene que la imagen se "agrande" más de lo necesario o se distorsione.
        cropped_featured_image = ImageOps.fit(featured_image, 
                                              (target_width_img, target_height_img), 
                                              method=Image.Resampling.LANCZOS, 
                                              bleed=0.0, 
                                              centering=(0.5, 0.5)) # Centrar el recorte


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
                font_size = 80 # Tamaño inicial de la fuente
                font = ImageFont.truetype(FONT_PATH, size=font_size)
            else:
                print(f"Advertencia: Fuente '{FONT_PATH}' no encontrada. Usando fuente por defecto.")
                font = ImageFont.load_default()
        except IOError:
            print("Advertencia: No se pudo cargar la fuente. Usando fuente por defecto.")
            font = ImageFont.load_default()

        # --- Lógica para texto multi-línea y ajuste de fuente ---
        lines = []
        current_line = []
        words = title_text.split() # Divide el título en palabras

        # Ajuste inicial de la fuente para que el texto sea legible
        # Comenzamos con un tamaño de fuente que es un buen compromiso
        # y reducimos si el texto completo no cabe en el área.
        optimal_font_size = 80 
        temp_font = ImageFont.truetype(FONT_PATH, size=optimal_font_size) if os.path.exists(FONT_PATH) else ImageFont.load_default()

        # Primero, ajustamos el tamaño de la fuente para que el texto quepa en el ancho de la caja
        # Si el texto es muy largo, lo dividimos en líneas
        max_lines = 4 # Límite máximo de líneas
        
        while True:
            test_lines = []
            test_current_line = []
            
            for word in words:
                test_potential_line = " ".join(test_current_line + [word])
                bbox = draw.textbbox((0,0), test_potential_line, font=temp_font)
                test_width = bbox[2] - bbox[0]
                
                if test_width <= text_area_width:
                    test_current_line.append(word)
                else:
                    test_lines.append(" ".join(test_current_line))
                    test_current_line = [word]
            
            if test_current_line:
                test_lines.append(" ".join(test_current_line))
            
            total_text_height = len(test_lines) * temp_font.getbbox("Tg")[3] # Aproximación de la altura total
            
            if total_text_height <= text_area_height and len(test_lines) <= max_lines:
                lines = test_lines # Si cabe, esta es la solución
                font = temp_font # Y esta es la fuente
                break
            
            # Si no cabe, reducimos el tamaño de la fuente y reintentamos
            optimal_font_size -= 1
            if optimal_font_size <= 10: # Límite inferior para evitar bucles infinitos
                print("Advertencia: El texto no cabe en el área con un tamaño de fuente razonable.")
                lines = test_lines # Usar lo que se pudo generar
                font = temp_font
                break
            
            temp_font = ImageFont.truetype(FONT_PATH, size=optimal_font_size) if os.path.exists(FONT_PATH) else ImageFont.load_default()

        # Dibujar las líneas de texto
        y_offset = text_area_y # Punto de inicio para la primera línea
        line_height = font.getbbox("Tg")[3] # Altura aproximada de una línea de texto

        # Centrar el bloque completo de texto verticalmente si hay espacio
        total_text_block_height = len(lines) * line_height
        if total_text_block_height < text_area_height:
            y_offset += (text_area_height - total_text_block_height) / 2

        for line in lines:
            # Centrar cada línea horizontalmente dentro del área
            bbox = draw.textbbox((0,0), line, font=font)
            line_width = bbox[2] - bbox[0]
            x_final = text_area_x + (text_area_width - line_width) / 2
            
            draw.text((x_final, y_offset), line, font=font, fill=text_color)
            y_offset += line_height # Mover a la siguiente línea

        # --- SALIDA DE LA IMAGEN ---
        img_byte_arr = io.BytesIO()
        base_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

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
