#!/usr/bin/env python3
"""Escenario "Antes" con Google Routes API, en ambos sentidos (ida y vuelta).

Google no entrega datos de fechas pasadas. Por eso cada día hábil de agosto y
septiembre de 2026 se consulta en una fecha FUTURA con el mismo día de la semana
y la misma hora; Google responde con su predicción basada en el historial de
tráfico de la vía. Se guarda la fecha original.

DATOS CONGELADOS: el script nunca modifica ni borra filas ya guardadas; solo
agrega las que falten. Cuando el archivo está completo, termina sin tocarlo.
Cada fila registra la fecha en que se extrajo, como evidencia para el informe.
"""

import csv
import os
import sys
import time
from datetime import date, datetime, timedelta

from rutas_google import DIAS, ROTONDA, SENTIDOS, ZONA_HORARIA, consultar_ruta

# Meses de referencia del "Antes" (rotonda aún no en uso)
MESES = [(2026, 8), (2026, 9)]
HORAS = [(7, 30, True), (13, 0, False), (17, 30, True)]  # (hora, minuto, es_pico)

ARCHIVO_CSV = "historico_antes.csv"
COLUMNAS = ["fecha", "hora", "sentido", "dia_semana", "es_hora_pico", "distancia_km",
            "tiempo_viaje_minutos", "tiempo_sin_trafico_minutos", "fecha_extraccion"]
PAUSA_SEGUNDOS = 1


def dias_laborales(meses):
    """Días de lunes a viernes de cada (año, mes)."""
    for anio, mes in meses:
        dia = date(anio, mes, 1)
        while dia.month == mes:
            if dia.weekday() < 5:  # 0=lunes ... 4=viernes
                yield dia
            dia += timedelta(days=1)


def generar_muestras(meses):
    """
    Devuelve (fecha original, hora, es_pico, fecha de consulta, sentido).
    La fecha original se arma con la hora fija y la zona de Guatemala
    (p. ej. 2026-08-03 07:30 -06:00). A todas se les suma el MISMO número de
    semanas completas para que caigan en el futuro sin cambiar el día de la semana.
    """
    hoy = datetime.now(ZONA_HORARIA).date()
    primer = min(meses)
    semanas = ((hoy - date(primer[0], primer[1], 1)).days // 7) + 2
    desplazamiento = timedelta(days=7 * semanas)

    for dia in dias_laborales(meses):
        for hora, minuto, es_pico in HORAS:
            original = datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=ZONA_HORARIA)
            for sentido in SENTIDOS:
                yield dia, original.strftime("%H:%M"), es_pico, original + desplazamiento, sentido


def cargar_procesados():
    if not os.path.exists(ARCHIVO_CSV):
        return set()
    with open(ARCHIVO_CSV, newline="", encoding="utf-8") as f:
        # Filas sin columna "sentido" se consideran de ida
        return {(fila["fecha"], fila["hora"], fila.get("sentido") or "ida") for fila in csv.DictReader(f)}


def main():
    if not ROTONDA:
        print("AVISO: ROTONDA no está definida en rutas_google.py; la ruta no se fuerza por la rotonda.")

    procesados = cargar_procesados()
    nuevo = not os.path.exists(ARCHIVO_CSV)
    muestras = list(generar_muestras(MESES))
    pendientes = [m for m in muestras if (m[0].isoformat(), m[1], m[4]) not in procesados]
    print(f"{len(muestras)} consultas planificadas, {len(procesados)} ya guardadas.")

    if not pendientes:
        print("El escenario Antes ya está completo y congelado. No se modifica nada.")
        return

    hoy = datetime.now(ZONA_HORARIA).date().isoformat()

    errores = 0
    with open(ARCHIVO_CSV, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            escritor.writeheader()

        for i, (dia, hora, es_pico, salida, sentido) in enumerate(muestras, 1):
            if (dia.isoformat(), hora, sentido) in procesados:  # nunca se reescribe lo guardado
                continue
            try:
                datos = consultar_ruta(salida, sentido)
            except Exception as e:  # no detener: lo guardado se conserva
                errores += 1
                print(f"[{i}/{len(muestras)}] ERROR {dia} {hora} {sentido}: {e}")
                if "GOOGLE_MAPS_API_KEY" in str(e):
                    sys.exit(1)
                time.sleep(PAUSA_SEGUNDOS)
                continue

            escritor.writerow({"fecha": dia.isoformat(), "hora": hora, "sentido": sentido,
                               "dia_semana": DIAS[dia.weekday()], "es_hora_pico": es_pico, **datos,
                               "fecha_extraccion": hoy})
            f.flush()
            print(f"[{i}/{len(muestras)}] {dia} {hora} {sentido} -> {datos}")
            time.sleep(PAUSA_SEGUNDOS)

    print(f"Listo. Errores: {errores}. Resultados en {ARCHIVO_CSV}")


if __name__ == "__main__":
    main()
