"""Consulta compartida a Google Routes API (usada por el escenario Antes y el Después)."""

import os
import time
from datetime import timedelta, timezone

import requests

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

ORIGEN = (15.4855, -90.3015)    # San Pedro Carchá
DESTINO = (15.4694, -90.3792)   # Cobán

# Punto por el que la ruta DEBE pasar: la rotonda. Escribe aquí (lat, lon) de un
# punto sobre la calzada de la rotonda, en el carril que va hacia Cobán
# (no en el centro de la isla). Ejemplo: ROTONDA = (15.4800, -90.3300)
ROTONDA = (15.477889, -90.354111)  # 15°28'40.4"N 90°21'14.8"W

# Punto de la rotonda para el sentido de VUELTA (Cobán -> Carchá). Si la vía está
# dividida, pon aquí un punto sobre el carril hacia Carchá; si no, deja el mismo.
ROTONDA_VUELTA = ROTONDA

# ida = Carchá -> rotonda -> Cobán ; vuelta = Cobán -> rotonda -> Carchá
SENTIDOS = ["ida", "vuelta"]

ZONA_HORARIA = timezone(timedelta(hours=-6))  # Guatemala (UTC-6)
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _punto(lat, lon):
    return {"location": {"latLng": {"latitude": lat, "longitude": lon}}}


def _segundos(valor):
    """Google devuelve duraciones como texto, p. ej. '845s'."""
    return float(str(valor).rstrip("s") or 0)


def consultar_ruta(salida=None, sentido="ida", reintentos=2):
    """
    Pide la ruta con tráfico en el sentido indicado ("ida" o "vuelta").
    salida = datetime con zona horaria para una salida futura (predicción de Google
    basada en su historial de tráfico), o None para salir ahora (tráfico en vivo).
    Devuelve un dict con distancia_km, tiempo_viaje_minutos y tiempo_sin_trafico_minutos.
    """
    if not API_KEY:
        raise RuntimeError("Falta la variable de entorno GOOGLE_MAPS_API_KEY.")

    if sentido == "ida":
        inicio, fin, paso = ORIGEN, DESTINO, ROTONDA
    elif sentido == "vuelta":
        inicio, fin, paso = DESTINO, ORIGEN, ROTONDA_VUELTA
    else:
        raise ValueError(f"Sentido desconocido: {sentido}")

    cuerpo = {
        "origin": _punto(*inicio),
        "destination": _punto(*fin),
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "trafficModel": "BEST_GUESS",
    }
    if paso:
        cuerpo["intermediates"] = [_punto(*paso)]
    if salida is not None:
        cuerpo["departureTime"] = salida.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    cabeceras = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "routes.duration,routes.staticDuration,routes.distanceMeters",
    }

    ultimo_error = None
    for intento in range(reintentos + 1):
        try:
            r = requests.post(URL, json=cuerpo, headers=cabeceras, timeout=30)
            if r.status_code == 429:  # cuota o límite de tasa: esperar y reintentar
                ultimo_error = f"429 límite de solicitudes | {r.text[:300]}"
                time.sleep(5 * (intento + 1))
                continue
            r.raise_for_status()
            ruta = r.json()["routes"][0]
            con_trafico = _segundos(ruta["duration"])
            sin_trafico = _segundos(ruta.get("staticDuration", "0s"))
            return {
                "distancia_km": round(ruta["distanceMeters"] / 1000, 3),
                "tiempo_viaje_minutos": round(con_trafico / 60, 2),
                "tiempo_sin_trafico_minutos": round(sin_trafico / 60, 2),
            }
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            detalle = ""
            if isinstance(e, requests.HTTPError) and e.response is not None:
                detalle = f" | {e.response.text[:300]}"
            ultimo_error = f"{type(e).__name__}{detalle}"  # nunca se imprime la key
            time.sleep(2)
    raise RuntimeError(ultimo_error)
