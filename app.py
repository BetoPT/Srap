from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
import time
import json
import datetime
import os
import logging
from werkzeug.exceptions import BadRequest

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_chrome_options():
    """Configuración de Chrome para entorno cloud/headless"""
    options = Options()
    
    # OBLIGATORIO para entornos cloud
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,720")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Para Railway/Render
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    
    return options

def buscar_patente_sipi(numero_expediente, timeout=45):
    """
    Busca una patente en SIPI - Optimizado para API webhook
    
    Args:
        numero_expediente (str): Número de expediente
        timeout (int): Timeout en segundos
    
    Returns:
        dict: Resultado de la búsqueda
    """
    driver = None
    resultado = {
        "exito": False,
        "numero_buscado": numero_expediente,
        "fecha_busqueda": datetime.datetime.now().isoformat(),
        "url_final": "",
        "titulo_final": "",
        "tiene_resultados": False,
        "datos_encontrados": {},
        "html_length": 0,
        "html_completo": "",  # ← HTML COMPLETO INICIALIZADO
        "error": "",
        "tiempo_ejecucion": 0
    }
    
    inicio = time.time()
    
    try:
        logger.info(f"Iniciando búsqueda para: {numero_expediente}")
        
        # Configurar Chrome
        options = get_chrome_options()
        
        # Crear driver (sin webdriver-manager para mayor confiabilidad)
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(timeout)
        driver.implicitly_wait(10)
        
        # 1. Navegar a SIPI
        logger.info("Navegando a SIPI...")
        driver.get("https://sipi.sic.gov.co/")
        
        # 2. Click en Patentes
        logger.info("Buscando botón de patentes...")
        search_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.ID, "MainContent_lnkPTSearch"))
        )
        
        driver.execute_script("arguments[0].scrollIntoView(true);", search_button)
        time.sleep(1)
        search_button.click()
        
        # 3. Llenar formulario
        logger.info("Llenando formulario...")
        time.sleep(3)
        
        campo_numero = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "MainContent_ctrlPTSearch_txtAppNr"))
        )
        
        campo_numero.clear()
        time.sleep(0.5)
        campo_numero.send_keys(numero_expediente)
        time.sleep(1)
        
        # 4. Ejecutar búsqueda
        logger.info("Ejecutando búsqueda...")
        campo_numero.send_keys(Keys.RETURN)
        time.sleep(5)  # Esperar resultados
        
        # 5. Analizar resultados
        url_final = driver.current_url
        titulo_final = driver.title
        html_final = driver.page_source
        
        logger.info(f"URL final: {url_final}")
        logger.info(f"HTML length: {len(html_final)}")
        
        # Detectar si hay resultados
        es_homepage = "SIPI-INICIO" in titulo_final
        
        # Buscar datos específicos en el HTML
        datos_encontrados = extraer_datos_patente(html_final)
        
        if es_homepage:
            tiene_resultados = False
            logger.info("Regresó a homepage - número no encontrado")
        else:
            # Verificar indicadores de resultado
            indicadores_resultado = [
                "resultado" in html_final.lower(),
                "expediente" in html_final.lower(), 
                "solicitud" in html_final.lower(),
                len(datos_encontrados) > 0
            ]
            tiene_resultados = any(indicadores_resultado)
            
            # Verificar mensajes de "no encontrado"
            no_encontrado = any([
                "no se encontraron" in html_final.lower(),
                "sin resultados" in html_final.lower(),
                "no found" in html_final.lower()
            ])
            
            if no_encontrado:
                tiene_resultados = False
        
        # Completar resultado
        tiempo_total = time.time() - inicio
        
        resultado.update({
            "exito": True,
            "url_final": url_final,
            "titulo_final": titulo_final,
            "tiene_resultados": tiene_resultados,
            "datos_encontrados": datos_encontrados,
            "html_length": len(html_final),
            "html_completo": html_final,  # ← HTML COMPLETO AGREGADO
            "tiempo_ejecucion": round(tiempo_total, 2)
        })
        
        logger.info(f"Búsqueda completada en {tiempo_total:.2f}s - Resultados: {tiene_resultados}")
        return resultado
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error en búsqueda: {error_msg}")
        
        tiempo_total = time.time() - inicio
        resultado.update({
            "exito": False,
            "error": error_msg,
            "tiempo_ejecucion": round(tiempo_total, 2)
        })
        
        return resultado
        
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def extraer_datos_patente(html):
    """Extrae datos específicos del HTML de resultados"""
    datos = {}
    
    # Buscar patrones comunes en el HTML
    html_lower = html.lower()
    
    # Detectar si hay información de patente
    if "expediente" in html_lower or "solicitud" in html_lower:
        datos["tiene_informacion"] = True
        
        # Aquí puedes agregar más lógica para extraer datos específicos
        # como fechas, estado, título de la patente, etc.
        
        if "concedida" in html_lower:
            datos["estado_posible"] = "concedida"
        elif "pendiente" in html_lower:
            datos["estado_posible"] = "pendiente"
        elif "rechazada" in html_lower:
            datos["estado_posible"] = "rechazada"
    
    return datos

# === ENDPOINTS DE LA API ===

@app.route('/', methods=['GET'])
def health_check():
    """Endpoint de verificación de salud"""
    return jsonify({
        "status": "ok",
        "service": "SIPI Patent Scraper API",
        "version": "1.0",
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/buscar-patente', methods=['POST'])
def buscar_patente_endpoint():
    """
    Endpoint principal para buscar patentes
    
    Ejemplo de uso desde n8n:
    POST /buscar-patente
    {
        "numero_expediente": "15017263",
        "timeout": 45
    }
    """
    try:
        # Validar request
        if not request.is_json:
            return jsonify({"error": "Content-Type debe ser application/json"}), 400
        
        data = request.get_json()
        
        if not data or "numero_expediente" not in data:
            return jsonify({"error": "Campo 'numero_expediente' es requerido"}), 400
        
        numero_expediente = str(data["numero_expediente"]).strip()
        timeout = int(data.get("timeout", 45))
        
        if not numero_expediente:
            return jsonify({"error": "numero_expediente no puede estar vacío"}), 400
        
        if timeout < 10 or timeout > 120:
            return jsonify({"error": "timeout debe estar entre 10 y 120 segundos"}), 400
        
        logger.info(f"API: Búsqueda solicitada para {numero_expediente}")
        
        # Ejecutar búsqueda
        resultado = buscar_patente_sipi(numero_expediente, timeout)
        
        # Log del resultado
        logger.info(f"API: Resultado - Éxito: {resultado['exito']}, Resultados: {resultado['tiene_resultados']}")
        
        return jsonify(resultado), 200
        
    except Exception as e:
        logger.error(f"Error en endpoint: {str(e)}")
        return jsonify({
            "error": f"Error interno del servidor: {str(e)}",
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route('/buscar-patente', methods=['GET'])
def buscar_patente_get():
    """
    Endpoint GET para búsquedas simples (alternativo para n8n)
    
    Uso: GET /buscar-patente?numero=15017263&timeout=45
    """
    try:
        numero_expediente = request.args.get('numero', '').strip()
        timeout = int(request.args.get('timeout', 45))
        
        if not numero_expediente:
            return jsonify({"error": "Parámetro 'numero' es requerido"}), 400
        
        logger.info(f"API GET: Búsqueda para {numero_expediente}")
        
        resultado = buscar_patente_sipi(numero_expediente, timeout)
        return jsonify(resultado), 200
        
    except Exception as e:
        logger.error(f"Error en GET endpoint: {str(e)}")
        return jsonify({
            "error": f"Error interno: {str(e)}",
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route('/buscar-multiples', methods=['POST'])
def buscar_multiples_endpoint():
    """
    Endpoint para buscar múltiples patentes
    
    POST /buscar-multiples
    {
        "numeros": ["15017263", "20200001234"],
        "timeout": 45
    }
    """
    try:
        data = request.get_json()
        
        if not data or "numeros" not in data:
            return jsonify({"error": "Campo 'numeros' es requerido"}), 400
        
        numeros = data["numeros"]
        timeout = int(data.get("timeout", 45))
        
        if not isinstance(numeros, list) or len(numeros) == 0:
            return jsonify({"error": "numeros debe ser una lista no vacía"}), 400
        
        if len(numeros) > 10:
            return jsonify({"error": "Máximo 10 números por request"}), 400
        
        logger.info(f"API: Búsqueda múltiple para {len(numeros)} números")
        
        resultados = []
        for numero in numeros:
            resultado = buscar_patente_sipi(str(numero).strip(), timeout)
            resultados.append(resultado)
            time.sleep(2)  # Pausa entre búsquedas
        
        return jsonify({
            "total_buscados": len(numeros),
            "resultados": resultados,
            "timestamp": datetime.datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error en búsqueda múltiple: {str(e)}")
        return jsonify({
            "error": f"Error interno: {str(e)}",
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

# Configuración para producción (optimizada para Render)
if __name__ == '__main__':
    # Render usa PORT=10000 por defecto
    port = int(os.environ.get('PORT', 10000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Iniciando servidor en puerto {port}, debug={debug}")
    logger.info("Servidor optimizado para Render.com")
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)
