# Importar las librerías necesarias
from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter # Se añade ImageFilter para el desenfoque
import io # Para manejar streams de bytes (archivos en memoria)
import requests # Para descargar imágenes desde URLs
import os # Para operaciones con el sistema de archivos, como verificar la existencia de fuentes

app = Flask(__name__)

# Define la ruta a tu plantilla base. Asegúrate de que este archivo esté en la misma carpeta que app.py
BASE_IMAGE_PATH = 'plantilla_base.jpg'

# Define la ruta a tu fuente. Asegúrate de que este archivo .ttf esté en la misma carpeta.
# Si no usas esta fuente, el script intentará cargar una por defecto.
FONT_PATH = "Roboto-Bold.ttf"

# Factor de interlineado (ej. 0.2 = 20% de espacio adicional por línea)
# Ajusta este valor para controlar la separación entre líneas.
LINE_SPACING_FACTOR = 0.2

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

        # 2. Cargar y procesar la imagen destacada
        response = requests.get(image_url)
        featured_image = Image.open(io.BytesIO(response.content)).convert("RGBA")

        # Dimensiones del área donde la imagen destacada debe ir
        # De Placid (foto.jpg) y solicitud: 1080 W x 844 H
        target_width_img = 1080
        target_height_img = 844
        target_position_x_img = 0
        target_position_y_img = 0

        # Calcular nuevas dimensiones para ajustar la imagen al 100% de alto proporcionalmente
        original_aspect_ratio = featured_image.width / featured_image.height
        new_width_scaled = int(target_height_img * original_aspect_ratio)
        new_height_scaled = target_height_img

        scaled_featured_image = featured_image.resize((new_width_scaled, new_height_scaled), Image.Resampling.LANCZOS)

        # Verificar si la imagen escalada es más angosta que el ancho objetivo (1080px)
        if new_width_scaled < target_width_img:
            # Caso 1: La imagen es vertical y no cubre todo el ancho. Rellenar con fondo desenfocado.
            
            # Cargar la plantilla de fondo nuevamente para el desenfoque
            # Se usa la plantilla base como fondo para el desenfoque
            background_fill = Image.open(BASE_IMAGE_PATH).convert("RGBA")
            
            # Redimensionar el fondo para que cubra el área objetivo
            # Usar ImageOps.fit para asegurarse de que el fondo cubra el área sin distorsión
            background_fill = ImageOps.fit(background_fill, 
                                          (target_width_img, target_height_img), 
                                          method=Image.Resampling.LANCZOS, 
                                          centering=(0.5, 0.5))

            # Aplicar desenfoque al fondo (radio de 80, ajustable si es demasiado fuerte)
            background_fill = background_fill.filter(ImageFilter.GaussianBlur(radius=80))

            # Pegar el fondo desenfocado en la base_image en la posición correcta
            base_image.paste(background_fill, 
                             (target_position_x_img, target_position_y_img))

            # Calcular la posición para centrar la imagen destacada sobre el fondo desenfocado
            paste_x = target_position_x_img + (target_width_img - scaled_featured_image.width) // 2
            paste_y = target_position_y_img + (target_height_img - scaled_featured_image.height) // 2
            
            base_image.paste(scaled_featured_image, (paste_x, paste_y), scaled_featured_image)

        else:
            # Caso 2: La imagen es horizontal o cuadrada y cubre o excede el ancho objetivo.
            # Se recorta si es más ancha para encajar en el ancho objetivo (1080px).
            # Calcular recorte para centrar horizontalmente si la imagen es más ancha de lo necesario
            left_crop = (scaled_featured_image.width - target_width_img) // 2
            right_crop = left_crop + target_width_img
            cropped_image = scaled_featured_image.crop((left_crop, 0, right_crop, target_height_img))
            
            base_image.paste(cropped_image, 
                             (target_position_x_img, target_position_y_img)) 


        # 3. Añadir el título
        # Dimensiones del área de texto (de Placid: 951 W x 331 H)
        text_area_width = 951
        text_area_height = 331
        text_area_x = 62 # Posición X de la esquina superior izquierda del área
        text_area_y = 873 # Posición Y de la esquina superior izquierda del área

        # Ajuste para achicar levemente el alto de la caja de texto
        # Se reduce el alto en un 10% (ajustable) y se desplaza el inicio para mantener la alineación inferior relativa
        reduction_factor = 0.10 # 10% de reducción, ajusta este valor
        reduced_height_amount = int(text_area_height * reduction_factor)
        text_area_height -= reduced_height_amount
        text_area_y += reduced_height_amount # Desplaza Y hacia abajo para mantener la parte inferior


        text_color = (255, 255, 255, 255) # Blanco en formato RGBA
        shadow_color = (0, 0, 0, 150) # Negro con 60% de opacidad para la sombra (RGBA)
        shadow_offset_x = 4 # Desplazamiento de la sombra en X
        shadow_offset_y = 4 # Desplazamiento de la sombra en Y


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
        words = title_text.split() # Divide el título en palabras

        # Encuentra el tamaño de fuente óptimo para el texto en el área
        # Se inicia desde un tamaño grande y se reduce hasta que el texto quepa en las dimensiones.
        optimal_font_size = 100 # Empezar con un tamaño más grande para el texto
        max_lines = 4 # Límite máximo de líneas de texto

        while True:
            temp_font = ImageFont.truetype(FONT_PATH, size=optimal_font_size) if os.path.exists(FONT_PATH) else ImageFont.load_default()
            
            # Divide el texto en líneas que caben en el ancho del área
            test_lines = []
            test_current_line_words = []
            
            for word in words:
                potential_line = " ".join(test_current_line_words + [word])
                bbox = draw.textbbox((0,0), potential_line, font=temp_font)
                test_width = bbox[2] - bbox[0]
                
                if test_width <= text_area_width:
                    test_current_line_words.append(word)
                else:
                    if test_current_line_words: # Si hay palabras en la línea actual, guárdala
                        test_lines.append(" ".join(test_current_line_words))
                    test_current_line_words = [word] # Inicia nueva línea con la palabra actual
            
            if test_current_line_words: # Añade la última línea si hay palabras
                test_lines.append(" ".join(test_current_line_words))

            # Calcular la altura total del texto con estas líneas
            # La altura de una línea es aproximadamente la altura de la caja de texto para un carácter típico.
            # Pillow 9.0+ textbbox is (left, top, right, bottom), height = bottom - top
            # For older Pillow, use getsize or getmask.
            # Using 'Tg' as a typical character to estimate line height.
            try: # Use getbbox for Pillow 9.0+
                line_height_estimate = temp_font.getbbox("Tg")[3] - temp_font.getbbox("Tg")[1]
            except AttributeError: # Fallback for older Pillow versions
                line_height_estimate = temp_font.getsize("Tg")[1]

            total_text_height = (len(test_lines) * line_height_estimate) + (max(0, len(test_lines) - 1) * int(line_height_estimate * LINE_SPACING_FACTOR))
            
            # Verificar si el texto cabe dentro del área y el número de líneas es aceptable
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
            
            # Recargar la fuente con el nuevo tamaño
            temp_font = ImageFont.truetype(FONT_PATH, size=optimal_font_size) if os.path.exists(FONT_PATH) else ImageFont.load_default()

        # Dibujar las líneas de texto en la imagen
        y_offset = text_area_y # Punto de inicio para la primera línea

        try: # Use getbbox for Pillow 9.0+
            base_line_height = font.getbbox("Tg")[3] - font.getbbox("Tg")[1]
        except AttributeError: # Fallback for older Pillow versions
            base_line_height = font.getsize("Tg")[1]

        extra_spacing_per_line = int(base_line_height * LINE_SPACING_FACTOR)

        # Centrar el bloque completo de texto verticalmente si hay espacio
        total_text_block_height = (len(lines) * base_line_height) + (max(0, len(lines) - 1) * extra_spacing_per_line)
        if total_text_block_height < text_area_height:
            y_offset += (text_area_height - total_text_block_height) / 2

        for line in lines:
            # Centrar cada línea horizontalmente dentro del área
            bbox = draw.textbbox((0,0), line, font=font)
            line_width = bbox[2] - bbox[0]
            x_final = text_area_x + (text_area_width - line_width) / 2
            
            # Dibujar la sombra
            draw.text((x_final + shadow_offset_x, y_offset + shadow_offset_y), line, font=font, fill=shadow_color)
            # Dibujar el texto principal
            draw.text((x_final, y_offset), line, font=font, fill=text_color)
            y_offset += base_line_height + extra_spacing_per_line # Mover a la siguiente línea

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
