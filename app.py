from flask import Flask, jsonify, request
import requests
import json
import logging
import threading
import time
from datetime import datetime
import os
from apscheduler.schedulers.background import BackgroundScheduler

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Variable para rastrear el estado del servicio
service_status = {
    "last_health_check": None,
    "uptime_start": datetime.now().isoformat(),
    "health_checks_count": 0
}

# Ruta de estado para health checks
@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint ligero para verificar si el servicio está activo"""
    service_status["last_health_check"] = datetime.now().isoformat()
    service_status["health_checks_count"] += 1
    
    return jsonify({
        "status": "ok",
        "current_time": datetime.now().isoformat(),
        "uptime_since": service_status["uptime_start"],
        "checks_count": service_status["health_checks_count"]
    })

# Función para mantener el servicio activo con auto-pings
def keep_alive():
    """Realiza ping al propio endpoint health para mantener el servicio activo"""
    try:
        # Obtener la URL base del entorno o usar localhost para desarrollo
        base_url = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:5000')
        health_url = f"{base_url}/health"
        
        logger.info(f"Auto-ping a {health_url}")
        response = requests.get(health_url, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Auto-ping exitoso: {response.status_code}")
        else:
            logger.warning(f"Auto-ping con respuesta inesperada: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Error en auto-ping: {str(e)}")

# Configurar el programador para el auto-ping
scheduler = BackgroundScheduler()
scheduler.add_job(keep_alive, 'interval', minutes=13, id='keep_alive_job')
scheduler.start()

# Asegurar que el scheduler se apague correctamente al final
import atexit
atexit.register(lambda: scheduler.shutdown())

# Ruta para mostrar información sobre el estado del servicio
@app.route('/', methods=['GET'])
def index():
    current_time = datetime.now().isoformat()
    current_user = "muimui69"  # Obtenido de los datos proporcionados
    
    return jsonify({
        "service": "Cliente Consolidado API",
        "status": "running",
        "current_time": current_time,
        "current_user": current_user,
        "health_info": service_status,
        "available_endpoints": [
            "/health - Verificar estado del servicio",
            "/api/clientes/consolidado - Obtener datos consolidados de clientes"
        ]
    })

@app.route('/api/clientes/consolidado', methods=['GET'])
def get_clientes_consolidado():
    try:
        logger.info("Iniciando recopilación de datos de clientes consolidados")
        
        # Obtener datos de los endpoints de segmentación y clientes
        logger.info("Obteniendo datos del endpoint de segmentación...")
        segmentos_response = requests.get('https://backendpysegmentacion.onrender.com/api/segmentation/customers')
        
        logger.info("Obteniendo datos del endpoint de clientes...")
        clientes_response = requests.get('https://backendpysegmentacion.onrender.com/api/clientes')
        
        # Verificar si las respuestas de soporte son exitosas
        if not segmentos_response.ok:
            logger.error("Error en respuesta de segmentos: %s", segmentos_response.text[:200])
            return jsonify({"error": "Error en respuesta de segmentos"}), 500
            
        if not clientes_response.ok:
            logger.error("Error en respuesta de clientes: %s", clientes_response.text[:200])
            return jsonify({"error": "Error en respuesta de clientes"}), 500
        
        # Obtener datos de detalles - PRIMERA PÁGINA
        logger.info("Obteniendo datos del endpoint de detalles (página 1)...")
        detalles_p1_response = requests.get('https://backendpysegmentacion.onrender.com/api/clientes/detalles?page=1&limit=100')
        
        if not detalles_p1_response.ok:
            logger.error("Error en respuesta de detalles página 1: %s", detalles_p1_response.text[:200])
            return jsonify({"error": "Error en respuesta de detalles página 1"}), 500
            
        # Obtener datos de detalles - SEGUNDA PÁGINA
        logger.info("Obteniendo datos del endpoint de detalles (página 2)...")
        detalles_p2_response = requests.get('https://backendpysegmentacion.onrender.com/api/clientes/detalles?page=2&limit=100')
        
        if not detalles_p2_response.ok:
            logger.warning("Error en respuesta de detalles página 2: %s. Continuando solo con página 1.", detalles_p2_response.text[:200])
        
        # Imprimir las primeras partes de cada respuesta para diagnóstico
        logger.info("Respuesta de detalles p1 (primeros 100 caracteres): %s", detalles_p1_response.text[:100])
        logger.info("Respuesta de segmentos (primeros 100 caracteres): %s", segmentos_response.text[:100])
        logger.info("Respuesta de clientes (primeros 100 caracteres): %s", clientes_response.text[:100])
        
        # Convertir respuestas a JSON con manejo de errores
        try:
            detalles_p1_data = detalles_p1_response.json()
            logger.info("Tipo de detalles_p1_data: %s", type(detalles_p1_data).__name__)
            if isinstance(detalles_p1_data, str):
                logger.error("detalles_p1_data es una cadena, no un objeto JSON: %s", detalles_p1_data[:100])
                return jsonify({"error": "Formato inesperado en datos de detalles p1"}), 500
        except Exception as e:
            logger.error("Error al parsear JSON de detalles p1: %s", str(e))
            return jsonify({"error": f"Error al parsear datos de detalles p1: {str(e)}"}), 500
        
        # Procesar la segunda página si está disponible
        detalles_p2_data = None
        if detalles_p2_response.ok:
            try:
                detalles_p2_data = detalles_p2_response.json()
                logger.info("Tipo de detalles_p2_data: %s", type(detalles_p2_data).__name__)
                if isinstance(detalles_p2_data, str):
                    logger.error("detalles_p2_data es una cadena, no un objeto JSON: %s", detalles_p2_data[:100])
                    detalles_p2_data = None
            except Exception as e:
                logger.error("Error al parsear JSON de detalles p2: %s", str(e))
                detalles_p2_data = None
            
        try:
            segmentos_data = segmentos_response.json()
            # Verificar el tipo de segmentos_data
            logger.info("Tipo de segmentos_data: %s", type(segmentos_data).__name__)
            if isinstance(segmentos_data, str):
                logger.error("segmentos_data es una cadena, no un objeto JSON: %s", segmentos_data[:100])
                return jsonify({"error": "Formato inesperado en datos de segmentos"}), 500
        except Exception as e:
            logger.error("Error al parsear JSON de segmentos: %s", str(e))
            return jsonify({"error": f"Error al parsear datos de segmentos: {str(e)}"}), 500
            
        try:
            clientes_data = clientes_response.json()
            # Verificar el tipo de clientes_data
            logger.info("Tipo de clientes_data: %s", type(clientes_data).__name__)
            if isinstance(clientes_data, str):
                logger.error("clientes_data es una cadena, no un objeto JSON: %s", clientes_data[:100])
                return jsonify({"error": "Formato inesperado en datos de clientes"}), 500
        except Exception as e:
            logger.error("Error al parsear JSON de clientes: %s", str(e))
            return jsonify({"error": f"Error al parsear datos de clientes: {str(e)}"}), 500
        
        # Extraer las listas de datos de ambas páginas
        detalles_data = []
        
        # Procesar página 1
        if not isinstance(detalles_p1_data, list):
            logger.info("detalles_p1_data no es una lista: %s", type(detalles_p1_data).__name__)
            try:
                # Si es un diccionario, buscar dentro alguna clave que contenga la lista
                if isinstance(detalles_p1_data, dict):
                    for key in detalles_p1_data:
                        logger.info("Clave en detalles_p1_data: %s, Tipo: %s", key, type(detalles_p1_data[key]).__name__)
                        if isinstance(detalles_p1_data[key], list):
                            logger.info("Encontrada lista en clave %s", key)
                            detalles_data.extend(detalles_p1_data[key])
                            break
            except Exception as e:
                logger.error("Error al buscar lista en detalles_p1_data: %s", str(e))
                return jsonify({"error": "Formato inesperado en datos de detalles p1"}), 500
        else:
            detalles_data.extend(detalles_p1_data)
            
        # Procesar página 2 si existe
        if detalles_p2_data:
            if not isinstance(detalles_p2_data, list):
                logger.info("detalles_p2_data no es una lista: %s", type(detalles_p2_data).__name__)
                try:
                    # Si es un diccionario, buscar dentro alguna clave que contenga la lista
                    if isinstance(detalles_p2_data, dict):
                        for key in detalles_p2_data:
                            logger.info("Clave en detalles_p2_data: %s, Tipo: %s", key, type(detalles_p2_data[key]).__name__)
                            if isinstance(detalles_p2_data[key], list):
                                logger.info("Encontrada lista en clave %s (p2)", key)
                                detalles_data.extend(detalles_p2_data[key])
                                break
                except Exception as e:
                    logger.error("Error al buscar lista en detalles_p2_data: %s", str(e))
                    # Continuamos con los datos que tenemos
            else:
                detalles_data.extend(detalles_p2_data)
                
        if not isinstance(segmentos_data, list):
            logger.error("segmentos_data no es una lista: %s", type(segmentos_data).__name__)
            try:
                # Si es un diccionario, buscar dentro alguna clave que contenga la lista
                if isinstance(segmentos_data, dict):
                    for key in segmentos_data:
                        logger.info("Clave en segmentos_data: %s, Tipo: %s", key, type(segmentos_data[key]).__name__)
                        if isinstance(segmentos_data[key], list):
                            logger.info("Encontrada lista en clave %s", key)
                            segmentos_data = segmentos_data[key]
                            break
            except Exception as e:
                logger.error("Error al buscar lista en segmentos_data: %s", str(e))
                return jsonify({"error": "Formato inesperado en datos de segmentos"}), 500
                
        if not isinstance(clientes_data, list):
            logger.error("clientes_data no es una lista: %s", type(clientes_data).__name__)
            try:
                # Si es un diccionario, buscar dentro alguna clave que contenga la lista
                if isinstance(clientes_data, dict):
                    for key in clientes_data:
                        logger.info("Clave en clientes_data: %s, Tipo: %s", key, type(clientes_data[key]).__name__)
                        if isinstance(clientes_data[key], list):
                            logger.info("Encontrada lista en clave %s", key)
                            clientes_data = clientes_data[key]
                            break
            except Exception as e:
                logger.error("Error al buscar lista en clientes_data: %s", str(e))
                return jsonify({"error": "Formato inesperado en datos de clientes"}), 500

        # Registrar cantidad de registros en cada fuente
        logger.info("Registros obtenidos - Detalles: %d, Segmentos: %d, Clientes: %d", 
                   len(detalles_data), len(segmentos_data), len(clientes_data))
        
        # Mostrar una muestra de cada estructura de datos
        if detalles_data and len(detalles_data) > 0:
            logger.info("Ejemplo de registro de detalles: %s", json.dumps(detalles_data[0])[:200])
        if segmentos_data and len(segmentos_data) > 0:
            logger.info("Ejemplo de registro de segmentos: %s", json.dumps(segmentos_data[0])[:200])
        if clientes_data and len(clientes_data) > 0:
            logger.info("Ejemplo de registro de clientes: %s", json.dumps(clientes_data[0])[:200])
            
        # Crear diccionarios para búsqueda rápida por cliente_id con verificación de estructura
        segmentos_dict = {}
        for item in segmentos_data:
            try:
                # Verificar que sea un diccionario y tenga las claves necesarias
                if isinstance(item, dict) and 'cliente_id' in item and 'segmento' in item:
                    cliente_id = item['cliente_id']
                    segmento = item['segmento']
                    segmentos_dict[cliente_id] = segmento
                else:
                    logger.warning("Registro de segmento con formato inesperado: %s", json.dumps(item)[:100])
            except Exception as e:
                logger.error("Error al procesar registro de segmento: %s", str(e))
        
        clientes_dict = {}
        for item in clientes_data:
            try:
                # Verificar que sea un diccionario y tenga las claves necesarias
                if isinstance(item, dict) and 'cliente_id' in item and 'fullname' in item:
                    cliente_id = item['cliente_id']
                    fullname = item['fullname']
                    clientes_dict[cliente_id] = fullname
                else:
                    logger.warning("Registro de cliente con formato inesperado: %s", json.dumps(item)[:100])
            except Exception as e:
                logger.error("Error al procesar registro de cliente: %s", str(e))
        
        logger.info("Creados diccionarios de búsqueda - Segmentos: %d, Clientes: %d", 
                   len(segmentos_dict), len(clientes_dict))
        
        # Combinar todos los datos con manejo de errores detallado
        resultados = []
        errores_procesamiento = 0
        
        for i, detalle in enumerate(detalles_data):
            try:
                # Verificar que sea un diccionario y tenga la clave cliente_id
                if not isinstance(detalle, dict):
                    logger.warning("Detalle #%d no es un diccionario: %s", i, type(detalle).__name__)
                    continue
                    
                if 'cliente_id' not in detalle:
                    logger.warning("Detalle #%d no tiene cliente_id: %s", i, json.dumps(detalle)[:100])
                    continue
                    
                cliente_id = detalle['cliente_id']
                
                # Verificar si existen las claves requeridas, si no, usar valores por defecto
                cantidad_compras = detalle.get('cantidad_de_compras', 0)
                costo_compras = detalle.get('costo_de_compras', 0)
                ultima_compra = detalle.get('ultima_compra', '')
                
                # Obtener nombre y segmento
                nombre = clientes_dict.get(cliente_id, "Nombre no disponible")
                segmento = segmentos_dict.get(cliente_id, "Sin segmento")
                
                resultados.append({
                    "idcliente": cliente_id,
                    "nombre": nombre,
                    "segmento": segmento,
                    "cantidadcompra": cantidad_compras,
                    "costo": costo_compras,
                    "ultima_compra": ultima_compra
                })
            except Exception as e:
                errores_procesamiento += 1
                logger.error("Error al procesar detalle #%d: %s", i, str(e))
        
        logger.info("Consolidación completada - Total clientes procesados: %d, Errores: %d", 
                   len(resultados), errores_procesamiento)
        
        return jsonify(resultados)
    
    except Exception as e:
        logger.exception("Error inesperado al procesar la solicitud: %s", str(e))
        return jsonify({
            "error": f"Error al procesar la solicitud: {str(e)}"
        }), 500

if __name__ == '__main__':
    logger.info("Iniciando aplicación Flask")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)