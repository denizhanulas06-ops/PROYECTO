# -*- coding: utf-8 -*-
"""
Created on Mon Jan 26 18:17:18 2026

@author: julno
"""

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
import time
import csv
import pandas as pd

def buscar_empleo_completo(profesion, provincia):
    driver = webdriver.Chrome()
    driver.maximize_window() # Maximizar ayuda a que los elementos "hidden-md-down" sean visibles

    url = "https://www.tecnoempleo.com/"
    driver.get(url)
    time.sleep(2)

    search_box = driver.find_element(By.ID, "te")
    search_box.clear()
    search_box.send_keys(profesion)

    dropdown_elemento = driver.find_element(By.ID, "pr")
    select_provincias = Select(dropdown_elemento)

    select_provincias.select_by_visible_text(provincia)

    search_box.send_keys(Keys.ENTER)

    print(f"Buscando {profesion} en {provincia}...")
    time.sleep(5)


    datos_empleo = []
    hay_mas_paginas = True
    num_pagina = 1

    while hay_mas_paginas:
        print(f"--- Extrayendo datos de la página {num_pagina} ---")
        time.sleep(5) # Tiempo de carga para cada página nueva

        # Scroll inicial para asegurar que los elementos se carguen
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(1)

        ofertas = driver.find_elements(By.CSS_SELECTOR, "div.p-3.border.rounded")
        print(f"Encontradas {len(ofertas)} ofertas en esta página.")

        for oferta in ofertas:
            try:
                titulo = oferta.find_element(By.CSS_SELECTOR, "h3.fs-5").text

                try:
                    empresa = oferta.find_element(By.CLASS_NAME, "text-primary").text
                except:
                        empresa = "Empresa no encontrada"

                try:
                    bloque_der = oferta.find_element(By.CSS_SELECTOR, "div.text-right.hidden-md-down")
                    try:
                        ubicacion = bloque_der.find_element(By.TAG_NAME, "b").text.strip()
                    except:
                        ubicacion = "No especificada"

                    lineas = [l.strip() for l in bloque_der.text.split('\n') if l.strip()]

                    if len(lineas) >= 4:
                        sueldo = lineas[-1]
                    else:
                            sueldo = None #

                except Exception:
                    ubicacion = "Error en bloque"
                    sueldo = None

                datos_empleo.append({
                    "titulo": titulo,
                    "empresa": empresa,
                    "ubicacion": ubicacion,
                    "sueldo": sueldo
                    })

            except Exception as e:
                print(f"ERROR en una oferta: {e}")
                continue

        #Paginación
        try:
            boton_siguiente = driver.find_element(By.LINK_TEXT, "siguiente")

            # Hacemos scroll al boton siguiente
            driver.execute_script("arguments[0].scrollIntoView();", boton_siguiente)
            time.sleep(1)

            boton_siguiente.click()
            num_pagina += 1
            print("Cambiando a la siguiente página...")
        except:
            print("No hay más páginas o se ha alcanzado el final.")
            hay_mas_paginas = False

    return datos_empleo



def ipc_provincias():
    """
    Devuelve {provincia: indice} usando la tabla 24081 (IPC índice general por provincias).
    Coge el último dato disponible (último mes) para cada provincia.
    """
    url = "https://servicios.ine.es/wstempus/js/es/DATOS_TABLA/24081?tip=AM"
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    data = r.json()

    # Estructura típica: cada item tiene "Nombre" y "Data":[{"Valor":...,"Fecha":...}, ...]
    # El "Nombre" suele incluir la provincia.
    prov_last = {}  # provincia -> (fecha, valor)

    for item in data:
        nombre = item.get("Nombre", "")
        serie = item.get("Data", [])
        if not serie:
            continue

        # ultimo punto de la serie (último mes)
        last = serie[-1]
        valor = last.get("Valor", None)
        fecha = last.get("Fecha", None)
        if valor is None:
            continue

        # Extraer provincia: en esta tabla normalmente el nombre empieza por la provincia
        # Ej: "Madrid. Índice general"
        provincia = nombre.split(".")[0].strip()

        # Guardar el último (por si hubiera repetidos, nos quedamos con el más reciente)
        prev = prov_last.get(provincia)
        if (prev is None) or (fecha is not None and prev[0] is not None and fecha > prev[0]):
            prov_last[provincia] = (fecha, float(valor))

    # devolver solo provincia -> valor
    return {prov: val for prov, (f, val) in prov_last.items()}





#DATOS SALARIO MEDIO POR PROVINCIA
def renta_bruta_provincia():
    
    url = "https://servicios.ine.es/wstempus/js/es/DATOS_TABLA/53689?nult=1"
    response = requests.get(url)
    data = response.json()

    diccionario_completo = {}

    # Lista de lo que no queremos información
    no_provincias = [
        "Total Nacional", "Andalucía", "Aragón", "Asturias, Principado de",
        "Canarias", "Castilla y León",
        "Castilla - La Mancha", "Cataluña", "Comunitat Valenciana",
        "Extremadura", "Galicia", "Madrid, Comunidad de",
        "Murcia, Región de", "Navarra, Comunidad Foral de",
        "País Vasco", "Ceuta", "Melilla",
        "Fuerteventura", "Gomera, La", "Gran Canaria", "Hierro, El",
        "Lanzarote", "Palma, La", "Tenerife",
        "Ibiza y Formentera", "Mallorca", "Menorca"
        ]

    for serie in data:
        nombre = serie['Nombre']
        if "Renta bruta media por persona" in nombre:
            nombre_limpio = nombre.split('.')[0].strip()

            if serie.get('Data'):
                valor = serie['Data'][0].get('Valor')
                diccionario_completo[nombre_limpio] = valor

    #sólo provincias
    sueldo_bruto_provincia = {k: v for k, v in diccionario_completo.items() if k not in no_provincias or k in ["Ceuta", "Melilla"]}
    return sueldo_bruto_provincia

#DATOS EMPLEO ADZUNA
def obtener_ofertas_adzuna(oficio_a_buscar, provincia_a_buscar, max_paginas=8):
    APP_ID = 'f8c4c8a9'
    APP_KEY = '5bb3c13462fba337a481f2eaa2f66727'
    PAIS = 'es'

    lista_global_resultados = []

    pagina_actual = 1

    while pagina_actual <= max_paginas:

        url = f"http://api.adzuna.com/v1/api/jobs/{PAIS}/search/{pagina_actual}"

        params = {
            'app_id': APP_ID,
            'app_key': APP_KEY,
            'results_per_page': 20,
            'what': oficio_a_buscar,
            'where': provincia_a_buscar,
            'content-type': 'application/json'
        }

        try:
            response = requests.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                ofertas = data.get('results', [])

                if not ofertas:
                    break

                for oferta in ofertas:
                    s_min = oferta.get('salary_min')
                    s_max = oferta.get('salary_max')

                    if s_min:
                        sueldo_str = f"{s_min} - {s_max}"
                    else:
                        sueldo_str = "A convenir"

                    item = {
                        "titulo": oferta.get('title'),
                        "empresa": oferta.get('company', {}).get('display_name', 'Sin empresa'),
                        "ubicacion": oferta.get('location', {}).get('display_name'),
                        "sueldo": sueldo_str
                    }

                    lista_global_resultados.append(item)


                pagina_actual += 1
                time.sleep(1)

            else:
                break 

        except Exception as e:
            break

    return lista_global_resultados


oficio_a_buscar = "Programador Python"
provincia_a_buscar = "Barcelona"
datos_ipc = ipc_provincias()
datos_renta = renta_bruta_provincia()
datos_adzuna = obtener_ofertas_adzuna(oficio_a_buscar, provincia_a_buscar, max_paginas=5)
datos_tecnoempleo = buscar_empleo_completo(oficio_a_buscar, provincia_a_buscar)
todos_los_datos = datos_adzuna + datos_tecnoempleo
df = pd.DataFrame(todos_los_datos)
df.to_csv("ofertas_sucias_huesca.csv", index=False, sep=';', encoding="utf-8")
df2 = pd.DataFrame([datos_ipc])
df2.to_csv("ipc.csv", index=False, sep=';', encoding='utf-8-sig')
df3 = pd.DataFrame([datos_renta])
df3.to_csv("renta.csv", index=False, sep=';', encoding='utf-8-sig')
