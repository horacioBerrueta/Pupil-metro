# pyrefly: ignore [missing-import]
import cv2
# pyrefly: ignore [missing-import]
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import csv
import time
from camera_utils import (
    CameraOpenError,
    RESOLUCION_MAXIMA_SOLICITADA,
    abrir_camara_maxima,
    detectar_camaras,
    resolucion_del_frame,
)

# ==============================
# CONFIGURACIÓN
# ==============================
iris_mm = 12.0  # diámetro promedio del iris en mm
archivo_datos = "mediciones_pupila.csv"
archivo_resumen = "resumen_fases.csv"

# Definir intervalos manualmente (segundos desde inicio)
intervalos = [
    (0, 10, "Fase 1 - Baseline"),
    (10, 80, "Fase 2 - Tarea Stroop"),
    (80, 90, "Fase 3 - Recuperación")
]

# ==============================
# CREAR CSV DE MEDICIONES
# ==============================
with open(archivo_datos, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["timestamp", "pupila_mm"])

# ==============================
# CAPTURA WEBCAM
# ==============================
indices_camara = detectar_camaras()
if not indices_camara:
    raise CameraOpenError(
        "No se detectaron webcams disponibles. Compruebe la conexión, los permisos "
        "y que otra aplicación no esté usando la cámara."
    )

print("Cámaras disponibles:")
for indice in indices_camara:
    print(f"  {indice}: Cámara {indice}")
while True:
    entrada = input(f"Índice de cámara [{indices_camara[0]}]: ").strip()
    indice_camara = indices_camara[0] if not entrada else None
    if entrada:
        try:
            indice_camara = int(entrada)
        except ValueError:
            indice_camara = None
    if indice_camara in indices_camara:
        break
    print("Índice no válido. Elija uno de los índices mostrados.")

print(
    "Solicitando el modo de alta resolución "
    f"({RESOLUCION_MAXIMA_SOLICITADA[0]} × {RESOLUCION_MAXIMA_SOLICITADA[1]}) "
    "y validando la transmisión..."
)
cap, resolucion_inicial, resolucion_informada = abrir_camara_maxima(indice_camara)
print(f"Cámara {indice_camara} abierta; resolución real del fotograma inicial: "
      f"{resolucion_inicial[0]} × {resolucion_inicial[1]}.")
if resolucion_informada is None:
    print("CAP_PROP no informó dimensiones; se usa la medida del fotograma real.")
else:
    print(f"CAP_PROP informa: {resolucion_informada[0]} × {resolucion_informada[1]}; "
          "la medida del fotograma es la referencia efectiva.")

print("Presiona 'q' para finalizar la captura.")

resolucion_frame_anterior = None
while True:
    ret, frame = cap.read()
    if not ret:
        break

    resolucion_frame = resolucion_del_frame(frame)
    if resolucion_frame is not None and resolucion_frame != resolucion_frame_anterior:
        resolucion_frame_anterior = resolucion_frame
        print(f"Dimensiones observadas en el fotograma: "
              f"{resolucion_frame[0]} × {resolucion_frame[1]}.")
        if resolucion_frame != resolucion_inicial:
            print("Aviso: la resolución del flujo cambió desde el fotograma inicial.")

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=50,
        param1=100,
        param2=30,
        minRadius=10,
        maxRadius=150
    )

    if circles is not None:
        circles = np.uint16(np.around(circles))
        sorted_circles = sorted(circles[0, :], key=lambda x: x[2])
        pupila = sorted_circles[0]
        iris = sorted_circles[-1]

        # Escala mm/px usando iris
        escala = iris_mm / (2 * iris[2])
        pupila_mm = (2 * pupila[2]) * escala

        # Dibujar círculos
        cv2.circle(frame, (pupila[0], pupila[1]), pupila[2], (0, 255, 0), 2)
        cv2.circle(frame, (iris[0], iris[1]), iris[2], (255, 0, 0), 2)
        cv2.circle(frame, (pupila[0], pupila[1]), 2, (0, 0, 255), 3)

        # Mostrar valor en pantalla
        cv2.putText(frame, f"Pupila: {pupila_mm:.2f} mm", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Guardar medición en CSV
        with open(archivo_datos, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([time.time(), pupila_mm])

    cv2.imshow("Medición Pupilar", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print(f"✅ Captura finalizada. Datos guardados en {archivo_datos}")

# ==============================
# ANÁLISIS POR FASES
# ==============================
df = pd.read_csv(archivo_datos)
df["tiempo_rel"] = df["timestamp"] - df["timestamp"].iloc[0]

resultados = []
for inicio, fin, nombre in intervalos:
    subset = df[(df["tiempo_rel"] >= inicio) & (df["tiempo_rel"] < fin)]
    if len(subset) > 0:
        media = subset["pupila_mm"].mean()
        desv = subset["pupila_mm"].std()
        min_val = subset["pupila_mm"].min()
        max_val = subset["pupila_mm"].max()
        resultados.append({
            "fase": nombre,
            "inicio_s": inicio,
            "fin_s": fin,
            "media_mm": media,
            "desv_mm": desv,
            "min_mm": min_val,
            "max_mm": max_val,
            "n_muestras": len(subset)
        })
    else:
        resultados.append({
            "fase": nombre,
            "inicio_s": inicio,
            "fin_s": fin,
            "media_mm": None,
            "desv_mm": None,
            "min_mm": None,
            "max_mm": None,
            "n_muestras": 0
        })

resumen = pd.DataFrame(resultados)
resumen.to_csv(archivo_resumen, index=False)
print(f"✅ Resumen por fases exportado a {archivo_resumen}")
print(resumen)

# ==============================
# GRAFICAR SEÑAL + FASES + BARRAS DE ERROR
# ==============================
plt.figure(figsize=(10, 5))
plt.plot(df["tiempo_rel"], df["pupila_mm"], color="gray", alpha=0.5, label="Señal original")

colors = ["lightblue", "lightgreen", "lightcoral", "khaki", "plum"]
centros = []
medias_barras = []
desv_barras = []

for i, (inicio, fin, nombre) in enumerate(intervalos):
    plt.axvspan(inicio, fin, color=colors[i % len(colors)], alpha=0.3)
    subset = df[(df["tiempo_rel"] >= inicio) & (df["tiempo_rel"] < fin)]
    if len(subset) > 0:
        centro = (inicio + fin)/2
        centros.append(centro)
        medias_barras.append(subset["pupila_mm"].mean())
        desv_barras.append(subset["pupila_mm"].std())

plt.errorbar(centros, medias_barras, yerr=desv_barras, fmt='o', color='blue', ecolor='black',
             elinewidth=2, capsize=5, label="Media ± 1 SD")

plt.title("Variación pupilar por fases experimentales")
plt.xlabel("Tiempo (segundos desde inicio)")
plt.ylabel("Diámetro pupilar (mm)")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()