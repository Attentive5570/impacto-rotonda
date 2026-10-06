#!/usr/bin/env python3
"""Escenario "Después": mide el tráfico ACTUAL Carchá -> Cobán y agrega una fila a datos_despues.csv."""

import csv
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "")
ORIGEN = "15.4855,-90.3015"    # San Pedro Carchá
DESTINO = "15.4694,-90.3792"   # Cobán
URL = f"https://api.tomtom.com/routing/1/calculateRoute/{ORIGEN}:{DESTINO}/json"

ZONA_HORARIA = timezone(timedelta(hours=-6))  # Guatemala (UTC-6)
ARCHIVO_CSV = "datos_despues.csv"
COLUMNAS = [
    "fecha", "hora_medicion", "franja", "dia_semana", "distancia_km",
    "tiempo_viaje_minutos", "tiempo_sin_trafico_minutos", "demora_trafico_minutos",
]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def franja_actual(ahora):
    """
    Clasifica la medición según la hora local. GitHub puede retrasar las
    ejecuciones programadas, por eso se usan rangos y no horas exactas:
    antes de 10:30 = manana (07:30), hasta 15:15 = valle (13:00), después = tarde (17:30).
    """
    h = ahora.hour + ahora.minute / 60
    if h < 10.5:
        return "manana"
    if h < 15.25:
        return "valle"
    return "tarde"


def consultar_actual():
    """Pide la ruta con tráfico en tiempo real (sin departAt = salir ahora)."""
    params = {"key": TOMTOM_API_KEY, "traffic": "true", "travelMode": "car", "routeType": "fastest"}
    ultimo_error = None
    for intento in range(3):
        try:
            r = requests.get(URL, params=params, timeout=30)
            r.raise_for_status()
            return r.json()["routes"][0]["summary"]
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            detalle = ""
            if isinstance(e, requests.HTTPError) and e.response is not None:
                detalle = f" | {e.response.text[:200]}"
            ultimo_error = f"{type(e).__name__}{detalle}"  # sin URL: contiene la key
            time.sleep(5 * (intento + 1))
    raise RuntimeError(ultimo_error)


def main():
    if not TOMTOM_API_KEY:
        sys.exit("Falta la variable de entorno TOMTOM_API_KEY.")

    ahora = datetime.now(ZONA_HORARIA)
    try:
        resumen = consultar_actual()
    except Exception as e:
        sys.exit(f"Error al consultar TomTom: {e}")

    con_trafico = resumen["travelTimeInSeconds"] / 60
    sin_trafico = resumen.get("noTrafficTravelTimeInSeconds")
    demora = resumen.get("trafficDelayInSeconds")

    fila = {
        "fecha": ahora.date().isoformat(),
        "hora_medicion": ahora.strftime("%H:%M"),
        "franja": franja_actual(ahora),
        "dia_semana": DIAS[ahora.weekday()],
        "distancia_km": round(resumen["lengthInMeters"] / 1000, 3),
        "tiempo_viaje_minutos": round(con_trafico, 2),
        "tiempo_sin_trafico_minutos": round(sin_trafico / 60, 2) if sin_trafico is not None else "",
        "demora_trafico_minutos": round(demora / 60, 2) if demora is not None else "",
    }

    nuevo = not os.path.exists(ARCHIVO_CSV)
    with open(ARCHIVO_CSV, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            escritor.writeheader()
        escritor.writerow(fila)
    print(f"Guardado: {fila}")


if __name__ == "__main__":
    main()
