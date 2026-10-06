#!/usr/bin/env python3
"""Escenario "Después": tráfico ACTUAL en ambos sentidos, ida y vuelta (Google Routes API)."""

import csv
import os
import sys
from datetime import datetime

from rutas_google import DIAS, ROTONDA, SENTIDOS, ZONA_HORARIA, consultar_ruta

ARCHIVO_CSV = "datos_despues.csv"
COLUMNAS = ["fecha", "hora_medicion", "franja", "sentido", "dia_semana", "distancia_km",
            "tiempo_viaje_minutos", "tiempo_sin_trafico_minutos", "demora_trafico_minutos"]


def franja_actual(ahora):
    """
    GitHub puede retrasar las ejecuciones programadas, por eso se usan rangos:
    antes de 10:30 = manana (07:30), hasta 15:15 = valle (13:00), después = tarde (17:30).
    """
    h = ahora.hour + ahora.minute / 60
    if h < 10.5:
        return "manana"
    if h < 15.25:
        return "valle"
    return "tarde"


def main():
    if not ROTONDA:
        print("AVISO: ROTONDA no está definida en rutas_google.py; la ruta no se fuerza por la rotonda.")

    ahora = datetime.now(ZONA_HORARIA)
    filas = []
    for sentido in SENTIDOS:
        try:
            datos = consultar_ruta(sentido=sentido)  # sin hora de salida = tráfico en vivo
        except Exception as e:
            print(f"Error al consultar Google ({sentido}): {e}")
            continue
        filas.append({
            "fecha": ahora.date().isoformat(),
            "hora_medicion": ahora.strftime("%H:%M"),
            "franja": franja_actual(ahora),
            "sentido": sentido,
            "dia_semana": DIAS[ahora.weekday()],
            **datos,
            "demora_trafico_minutos": round(datos["tiempo_viaje_minutos"] - datos["tiempo_sin_trafico_minutos"], 2),
        })

    if not filas:
        sys.exit("No se pudo medir ningún sentido.")

    nuevo = not os.path.exists(ARCHIVO_CSV)
    with open(ARCHIVO_CSV, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            escritor.writeheader()
        escritor.writerows(filas)
    for fila in filas:
        print(f"Guardado: {fila}")


if __name__ == "__main__":
    main()
