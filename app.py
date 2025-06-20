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

# Cargar URL base desde variable de entorno
BASE_URL = os.environ.get('API_BASE_URL', 'https://hammerhead-app-4vfrt.ondigitalocean.app')

# Variable para rastrear el estado del servicio
service_status = {
    "last_health_check": None,
    "uptime_start": datetime.now().isoformat(),
    "health_checks_count": 0
}

@app.route('/health', methods=['GET'])
def health_check():
    service_status["last_health_check"] = datetime.now().isoformat()
    service_status["health_checks_count"] += 1
    
    return jsonify({
        "status": "ok",
        "current_time": datetime.now().isoformat(),
        "uptime_since": service_status["uptime_start"],
        "checks_count": service_status["health_checks_count"]
    })

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "service": "Cliente Consolidado API",
        "status": "running",
        "current_time": datetime.now().isoformat(),
        "current_user": "muimui69",
        "health_info": service_status,
        "available_endpoints": [
            "/health",
            "/api/clientes/consolidado"
        ]
    })

@app.route('/api/clientes/consolidado', methods=['GET'])
def get_clientes_consolidado():
    try:
        logger.info("Iniciando recopilación de datos de clientes consolidados")

        # Peticiones a los endpoints
        segmentos = requests.get(f'{BASE_URL}/api/segmentation/customers')
        clientes = requests.get(f'{BASE_URL}/api/clientes')
        detalles_p1 = requests.get(f'{BASE_URL}/api/clientes/detalles?page=1&limit=100')
        detalles_p2 = requests.get(f'{BASE_URL}/api/clientes/detalles?page=2&limit=100')

        # Validación de respuestas
        if not all([segmentos.ok, clientes.ok, detalles_p1.ok]):
            return jsonify({"error": "Error al obtener datos de uno o más endpoints"}), 500

        # Carga de datos
        segmentos_data = segmentos.json().get('clientes', [])
        clientes_data = clientes.json().get('clientes', [])
        detalles_data = detalles_p1.json().get('clientes_info', [])

        if detalles_p2.ok:
            detalles_data += detalles_p2.json().get('clientes_info', [])

        # Indexación por cliente_id
        segmentos_dict = {item['cliente_id']: item['segmento'] for item in segmentos_data if isinstance(item, dict)}
        clientes_dict = {item['cliente_id']: item['fullname'] for item in clientes_data if isinstance(item, dict)}

        resultados = []
        for detalle in detalles_data:
            cliente_id = detalle.get('cliente_id')
            if not cliente_id:
                continue
            resultados.append({
                "idcliente": cliente_id,
                "nombre": clientes_dict.get(cliente_id, "Nombre no disponible"),
                "segmento": segmentos_dict.get(cliente_id, "Sin segmento"),
                "cantidadcompra": detalle.get("cantidad_de_compras", 0),
                "costo": detalle.get("costo_de_compras", 0),
                "ultima_compra": detalle.get("ultima_compra", "")
            })

        return jsonify(resultados)

    except Exception as e:
        logger.exception("Error al consolidar datos")
        return jsonify({"error": str(e)}), 500

# Auto-ping al /health para mantener activo
def keep_alive():
    try:
        ping_url = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:5000') + "/health"
        logger.info(f"Haciendo auto-ping a {ping_url}")
        requests.get(ping_url, timeout=10)
    except Exception as e:
        logger.warning(f"Fallo en keep_alive: {str(e)}")

# Programador automático
scheduler = BackgroundScheduler()
scheduler.add_job(keep_alive, 'interval', minutes=13, id='keep_alive_job')
scheduler.start()

import atexit
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    logger.info("Iniciando aplicación Flask")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
