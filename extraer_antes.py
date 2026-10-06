#!/usr/bin/env python3
"""Escenario "Antes" (TomTom Routing API) - San Pedro Carchá -> Cobán.

Genera consultas para todos los días hábiles de los meses de referencia y guarda los resultados
en historico_antes_tomtom.csv. Se puede relanzar: continúa donde se quedó.
"""

import csv
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

import requests

# ===================== CONFIGURACIÓN =====================
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "")

ORIGEN = "15.4855,-90.3015"    # San Pedro Carchá
DESTINO = "15.4694,-90.3792"   # Cobán
URL = f"https://api.tomtom.com/routing/1/calculateRoute/{ORIGEN}:{DESTINO}/json"

# Meses de referencia del "Antes" (rotonda aún no en uso): agosto y septiembre de 2026
MESES = [(2026, 8), (2026, 9)]
HORAS = [(7, 30, True), (13, 0, False), (17, 30, True)]  # (hora, minuto, es_pico)
ZONA_HORARIA = timezone(timedelta(hours=-6))  # Guatemala: UTC-6, sin horario de verano

# La API suele rechazar fechas pasadas. Con True se consultan las mismas fechas
# desplazadas a futuro en bloques de 7 días (mismo día de la semana y hora),
# y en el CSV se guarda la fecha original. El resultado es una PREDICCIÓN de
# TomTom basada en patrones típicos, no una medición real de ese mes.
PROYECTAR_A_FUTURO = True

ARCHIVO_CSV = "historico_antes_tomtom.csv"
COLUMNAS = ["fecha", "hora", "dia_semana", "es_hora_pico", "distancia_km", "tiempo_viaje_minutos"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
PAUSA_SEGUNDOS = 1
REINTENTOS = 2
# =========================================================


def dias_laborales(meses):
    """Devuelve los días de lunes a viernes de cada (año, mes) indicado."""
    for anio, mes in meses:
        dia = date(anio, mes, 1)
        while dia.month == mes:
            if dia.weekday() < 5:  # 0=lunes ... 4=viernes
                yield dia
            dia += timedelta(days=1)


def generar_muestras(meses):
    """
    Genera (fecha, hora, es_pico, timestamp ISO 8601).
    El timestamp se arma uniendo la fecha, la hora fija (07:30, 13:00, 17:30)
    y la zona horaria de Guatemala, p. ej. 2025-10-01T07:30:00-06:00.
    Con PROYECTAR_A_FUTURO se suma el MISMO número de semanas completas a todas
    las fechas (calculado desde el primer mes), así conservan el día de la semana
    y ninguna consulta cae en el pasado ni se repite.
    """
    desplazamiento = timedelta(0)
    if PROYECTAR_A_FUTURO:
        hoy = datetime.now(ZONA_HORARIA).date()
        primer_mes = min(meses)
        semanas = ((hoy - date(primer_mes[0], primer_mes[1], 1)).days // 7) + 2
        desplazamiento = timedelta(days=7 * semanas)

    for dia in dias_laborales(meses):
        for hora, minuto, es_pico in HORAS:
            original = datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=ZONA_HORARIA)
            consulta = original + desplazamiento
            yield dia, original.strftime("%H:%M"), es_pico, consulta.isoformat()


def consultar_tomtom(depart_at):
    """GET a TomTom; devuelve (distancia_km, minutos) o lanza RuntimeError."""
    params = {
        "key": TOMTOM_API_KEY,
        "departAt": depart_at,
        "traffic": "true",
        "travelMode": "car",
        "routeType": "fastest",
    }
    ultimo_error = None
    for intento in range(REINTENTOS + 1):
        try:
            r = requests.get(URL, params=params, timeout=30)
            if r.status_code == 429:  # límite de tasa: esperar y reintentar
                ultimo_error = "429 Too Many Requests"
                time.sleep(5 * (intento + 1))
                continue
            r.raise_for_status()
            resumen = r.json()["routes"][0]["summary"]
            return (
                round(resumen["lengthInMeters"] / 1000, 3),
                round(resumen["travelTimeInSeconds"] / 60, 2),
            )
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            detalle = ""
            if isinstance(e, requests.HTTPError) and e.response is not None:
                detalle = f" | {e.response.text[:200]}"
            # Nunca imprimir la URL completa: contiene la API key
            ultimo_error = f"{type(e).__name__}{detalle}"
            time.sleep(2)
    raise RuntimeError(ultimo_error)


def cargar_procesados():
    """Lee el CSV existente para no repetir consultas."""
    if not os.path.exists(ARCHIVO_CSV):
        return set()
    with open(ARCHIVO_CSV, newline="", encoding="utf-8") as f:
        return {(fila["fecha"], fila["hora"]) for fila in csv.DictReader(f)}


def main():
    if not TOMTOM_API_KEY:
        sys.exit("Falta la variable de entorno TOMTOM_API_KEY.")

    procesados = cargar_procesados()
    nuevo = not os.path.exists(ARCHIVO_CSV)
    muestras = list(generar_muestras(MESES))
    print(f"{len(muestras)} consultas planificadas, {len(procesados)} ya guardadas.")

    errores = 0
    with open(ARCHIVO_CSV, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            escritor.writeheader()

        for i, (dia, hora, es_pico, ts) in enumerate(muestras, 1):
            if (dia.isoformat(), hora) in procesados:
                continue
            try:
                km, minutos = consultar_tomtom(ts)
            except Exception as e:  # no detener el script: el progreso ya está guardado
                errores += 1
                print(f"[{i}/{len(muestras)}] ERROR {dia} {hora}: {e}")
                time.sleep(PAUSA_SEGUNDOS)
                continue

            escritor.writerow({
                "fecha": dia.isoformat(),
                "hora": hora,
                "dia_semana": DIAS[dia.weekday()],
                "es_hora_pico": es_pico,
                "distancia_km": km,
                "tiempo_viaje_minutos": minutos,
            })
            f.flush()
            print(f"[{i}/{len(muestras)}] {dia} {hora} -> {km} km, {minutos} min")
            time.sleep(PAUSA_SEGUNDOS)

    print(f"Listo. Errores: {errores}. Resultados en {ARCHIVO_CSV}")


if __name__ == "__main__":
    main()
