# Importar las librerías necesarias
from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import io
import requests
import os
import json
import base64
from pydrive2.auth import GoogleAuth
# Importar ServiceAccountCredentials directamente si se usa el método from_json_keyfile_dict
from oauth2client.service_account import ServiceAccountCredentials 
from pydrive2.drive import GoogleDrive

app = Flask(__name__)

# Define la ruta a tu plantilla base. Asegúrate de que este archivo esté en la misma carpeta que app.py
BASE_IMAGE_PATH = 'plantilla_base.jpg'

# Define la ruta a tu fuente. Asegúrate de que este archivo .ttf esté en la misma carpeta.
FONT_PATH = "Roboto-Bold.ttf"

# Factor de interlineado (ej. 0.2 = 20% de espacio adicional por línea)
LINE_SPACING_FACTOR = 0.3 # Ampliado levemente de 0.2 a 0.3

# --- Configuración de Google Drive ---
# ID de la carpeta de Google Drive donde quieres guardar las imágenes.
# ¡IMPORTANTE! Reemplaza 'TU_CARPETA_ID_EN_GOOGLE_DRIVE' con el ID real de tu carpeta.
# Para obtener el ID, abre la carpeta en Google Drive y el ID estará en la URL (ej. drive.google.com/drive/folders/ID_DE_LA_CARPETA)
GOOGLE_DRIVE_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', 'TU_CARPETA_ID_EN_GOOGLE_DRIVE')

# Inicialización de Google Drive fuera de la ruta para que ocurra una sola vez
drive = None
try:
    # Decodificar las credenciales de la cuenta de servicio desde la variable de entorno
    credentials_json_base64 = os.environ.get('GOOGLE_CREDENTIALS_JSON_BASE64')
    if not credentials_json_base64:
        raise ValueError("La variable de entorno 'GOOGLE_CREDENTIALS_JSON_BASE64' no está configurada.")

    credentials_json_bytes = base64.b64decode(credentials_json_base64)
    credentials_info = json.loads(credentials_json_bytes.decode('utf-8'))

    # --- CAMBIO AQUÍ: Inicialización de GoogleAuth y Credenciales ---
    # Define los ámbitos (scopes) de acceso que necesitas para Google Drive
    # 'file' para acceso completo a archivos creados por la app, o 'drive' para acceso a todo el Drive.
    # 'https://www.googleapis.com/auth/drive' es el scope completo de Drive.
    # 'https://www.googleapis.com/auth/drive.file' para acceso a archivos creados o abiertos por la app.
    # Si vas a subir a una carpeta específica, 'drive.file' suele ser suficiente.
    scopes = ['https://www.googleapis.com/auth/drive.file'] # O 'https://www.googleapis.com/auth/drive'

    # Crea las credenciales de la cuenta de servicio directamente desde el diccionario
    gauth = GoogleAuth()
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scopes=scopes)
    
    drive = GoogleDrive(gauth)
    print("Conexión con Google Drive establecida correctamente.")

except Exception as e:
    print(f"Error al inicializar la conexión con Google Drive: {e}")
    drive = None # Asegurar que drive sea None si falla la inicialización

@app.route('/generate-image', methods=['POST'])
def generate_image():
    """
    Endpoint para generar una imagen combinando una plantilla, una imagen destacada y un título.
    Espera un JSON en el cuerpo de la petición con 'image_url' (URL de la imagen destacada)
    y 'title' (texto del título).
    Guarda la imagen generada en Google Drive y devuelve su URL pública.
    """
    if drive is None:
        return jsonify({"error": "El servicio de Google Drive no está disponible."}), 500

    data = request.json
    if not data:
        return jsonify({"error": "El cuerpo de la petición debe ser JSON"}), 400

    image_url = data.get('image_url')
    title_text = data.get('title')

    if not image_url or not title_text:
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

        # --- Subir la imagen generada a Google Drive ---
        img_byte_arr = io.BytesIO()
        image_filename = f"cn7_noticia_{os.urandom(4).hex()}.png" # Nombre único para el archivo PNG

        base_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0) # Mueve el puntero al inicio del stream para la subida

        # Crear un archivo de Google Drive
        file_metadata = {
            'title': image_filename,
            'parents': [{'id': GOOGLE_DRIVE_FOLDER_ID}],
            'mimeType': 'image/png'
        }
        file = drive.CreateFile(file_metadata)
        file.content = img_byte_arr # Asignar el contenido binario
        file.Upload() # Subir el archivo

        # Hacer el archivo público (para que pueda ser accesible por Instagram/N8N)
        file.InsertPermission({
            'type': 'anyone',
            'value': 'anyone',
            'role': 'reader'
        })

        # Obtener la URL web del archivo subido
        # La URL para ver en navegador es 'webContentLink', para usar en Instagram/Twitter es 'thumbnailLink' o 'webViewLink'
        # webViewLink es más robusto para redes sociales.
        image_public_url = file['webViewLink'] 
        print(f"Imagen subida a Google Drive: {image_public_url}")

        # Devolver la URL de la imagen generada a N8N
        return jsonify({"image_url": image_public_url}), 200

    except Exception as e:
        print(f"Error al generar o subir la imagen: {e}")
        return jsonify({"error": f"Error interno del servidor: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
