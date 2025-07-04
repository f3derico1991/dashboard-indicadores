# formatear_secretos.py
import json

# Asegúrate de que el nombre del archivo coincida con el que descargaste
nombre_archivo_json = "nueva-clave.json"

with open(nombre_archivo_json, "r") as f:
    data = json.load(f)

# Imprimimos el encabezado que Streamlit necesita
print("[google_credentials]")

# Iteramos sobre el contenido del JSON y lo formateamos para TOML
for key, value in data.items():
    # La clave privada necesita un tratamiento especial con comillas triples
    if key == "private_key":
        print(f'private_key = """{value}"""')
    else:
        # El resto de los valores van con comillas dobles normales
        print(f'{key} = "{value}"')