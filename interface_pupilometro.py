import cv2
import numpy as np
import csv
import time
import os
import sys
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from PIL import Image
from camera_utils import (
    CameraOpenError,
    abrir_camara_maxima,
    detectar_camaras,
)

# Configuración inicial del tema de CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class PupilometroApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        # Configuración de la ventana principal
        self.title("Pupilómetro - Medición y Análisis Pupilar")
        self.geometry("1150x790")
        self.minsize(1000, 740)

        # Variables de estado
        self.is_running = False
        self.is_calibrating = False
        self.cap = None
        self.start_time = None
        self.current_pupil_mm = 0.0
        self.iris_mm = 12.0
        self.data_buffer = []  # Buffer en memoria para evitar I/O continuo a disco
        self.archivo_datos = "mediciones_pupila.csv"
        self.archivo_resumen = "resumen_fases.csv"
        self.ctk_img = None  # Reutilización estática del objeto de imagen Tkinter
        self._frame_after_id = None

        # Intervalos experimentales predeterminados (segundos)
        self.intervalos = [
            (0, 10, "Fase 1 - Baseline"),
            (10, 80, "Fase 2 - Tarea Stroop"),
            (80, 90, "Fase 3 - Recuperación")
        ]

        # Estructura de distribución estática (panel de control fijo de 330px)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=330)
        self.grid_rowconfigure(0, weight=1)

        self._crear_panel_video()
        self._crear_panel_control()

        # Protocolo al cerrar la ventana
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _crear_panel_video(self):
        # Panel izquierdo para la vista previa de cámara
        self.frame_video = ctk.CTkFrame(self, corner_radius=15)
        self.frame_video.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")

        # Título de sección
        self.lbl_video_title = ctk.CTkLabel(
            self.frame_video,
            text="📹 Vista Previa en Tiempo Real",
            font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_video_title.pack(pady=(15, 5))

        # Contenedor estático del fotograma
        self.video_container = ctk.CTkFrame(self.frame_video, fg_color="#1E1E1E", corner_radius=10)
        self.video_container.pack(expand=True, fill="both", padx=15, pady=10)

        self.lbl_camara = ctk.CTkLabel(
            self.video_container,
            text="Cámara inactiva\nHaga clic en 'Iniciar Medición' o 'Calibrar'",
            font=ctk.CTkFont(size=14),
            fg_color="transparent")
        self.lbl_camara.pack(expand=True)

        # Barra de información inferior en el panel de video
        self.frame_info = ctk.CTkFrame(self.frame_video, fg_color="transparent")
        self.frame_info.pack(fill="x", padx=15, pady=(5, 15))

        self.lbl_medicion = ctk.CTkLabel(
            self.frame_info,
            text="Pupila: -- mm",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#2ECC71")
        self.lbl_medicion.pack(side="left", padx=10)

        self.lbl_tiempo = ctk.CTkLabel(
            self.frame_info,
            text="Tiempo: 0.0 s",
            font=ctk.CTkFont(size=14))
        self.lbl_tiempo.pack(side="right", padx=10)

        self.lbl_fase = ctk.CTkLabel(
            self.frame_info,
            text="Fase: Inactiva",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#F39C12")
        self.lbl_fase.pack(side="right", padx=20)

    def _crear_panel_control(self):
        # Panel derecho de controles y parámetros (Ancho estático de 330px)
        self.frame_control = ctk.CTkScrollableFrame(self, width=330, corner_radius=15)
        self.frame_control.grid(row=0, column=1, padx=(0, 15), pady=15, sticky="nsew")

        # Título
        self.lbl_ctrl_title = ctk.CTkLabel(
            self.frame_control,
            text="🎛️ Panel de Control",
            font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_ctrl_title.pack(pady=(15, 15))

        # --- SECCIÓN: ACCIONES ---
        self.btn_iniciar = ctk.CTkButton(
            self.frame_control,
            text="▶ Iniciar Medición (Grabar)",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#27AE60",
            hover_color="#1E8449",
            height=45,
            command=self.iniciar_medicion)
        self.btn_iniciar.pack(fill="x", padx=15, pady=6)

        self.btn_detener = ctk.CTkButton(
            self.frame_control,
            text="⏹ Detener y Guardar",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#E74C3C",
            hover_color="#C0392B",
            height=45,
            state="disabled",
            command=self.detener_medicion)
        self.btn_detener.pack(fill="x", padx=15, pady=6)

        # Separador
        ctk.CTkFrame(self.frame_control, height=2, fg_color="#333333").pack(fill="x", padx=15, pady=10)

        # --- SECCIÓN: CÁMARA ---
        self.lbl_camera_title = ctk.CTkLabel(
            self.frame_control,
            text="📷 Cámara",
            font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_camera_title.pack(anchor="w", padx=15, pady=(0, 4))

        self.camera_var = tk.StringVar(value="Buscando cámaras...")
        self.camera_menu = ctk.CTkOptionMenu(
            self.frame_control,
            variable=self.camera_var,
            values=["Buscando cámaras..."])
        self.camera_menu.pack(fill="x", padx=15, pady=(2, 4))

        self.btn_refrescar_camaras = ctk.CTkButton(
            self.frame_control,
            text="↻ Detectar cámaras",
            height=30,
            command=self._actualizar_camaras)
        self.btn_refrescar_camaras.pack(fill="x", padx=15, pady=(0, 5))

        ctk.CTkFrame(self.frame_control, height=2, fg_color="#333333").pack(fill="x", padx=15, pady=8)

        # --- SECCIÓN: CALIBRACIÓN ---
        self.lbl_calib_title = ctk.CTkLabel(
            self.frame_control,
            text="⚙️ Calibración de Cámara",
            font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_calib_title.pack(anchor="w", padx=15, pady=(0, 4))

        self.lbl_iris = ctk.CTkLabel(self.frame_control, text="Diámetro Iris Referencia (mm):")
        self.lbl_iris.pack(anchor="w", padx=15)

        self.entry_iris = ctk.CTkEntry(self.frame_control)
        self.entry_iris.insert(0, "12.0")
        self.entry_iris.pack(fill="x", padx=15, pady=(2, 6))

        # Botón de modo Calibración / Previsualización sin grabar
        self.btn_calibrar = ctk.CTkButton(
            self.frame_control,
            text="🔍 Vista Previa / Calibrar",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#F39C12",
            hover_color="#D68910",
            height=38,
            command=self.toggle_calibracion)
        self.btn_calibrar.pack(fill="x", padx=15, pady=(2, 6))

        # Separador
        ctk.CTkFrame(self.frame_control, height=2, fg_color="#333333").pack(fill="x", padx=15, pady=10)

        # --- SECCIÓN: RESULTADOS ---
        self.lbl_res_title = ctk.CTkLabel(
            self.frame_control,
            text="📊 Resultados",
            font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_res_title.pack(anchor="w", padx=15, pady=(0, 4))

        self.btn_grafico = ctk.CTkButton(
            self.frame_control,
            text="📈 Generar Gráfica y Resumen",
            font=ctk.CTkFont(size=13),
            fg_color="#2980B9",
            hover_color="#1F618D",
            height=38,
            command=self.analizar_y_graficar)
        self.btn_grafico.pack(fill="x", padx=15, pady=6)

        self.btn_abrir_carpeta = ctk.CTkButton(
            self.frame_control,
            text="📁 Abrir Carpeta de Datos",
            font=ctk.CTkFont(size=13),
            fg_color="#7F8C8D",
            hover_color="#626567",
            height=38,
            command=self.abrir_carpeta)
        self.btn_abrir_carpeta.pack(fill="x", padx=15, pady=6)

        self._actualizar_camaras(mostrar_error=False)

    def _actualizar_camaras(self, mostrar_error=True):
        try:
            indices = detectar_camaras()
        except Exception as exc:
            if mostrar_error:
                messagebox.showerror("Error al detectar cámaras", f"No se pudieron consultar las webcams.\n\n{exc}")
            return

        seleccion_actual = self.camera_indices.get(self.camera_var.get()) if hasattr(self, "camera_indices") else None
        self.camera_indices = {f"Cámara {indice}": indice for indice in indices}
        opciones = list(self.camera_indices)
        if opciones:
            etiqueta = next(
                (nombre for nombre, indice in self.camera_indices.items() if indice == seleccion_actual),
                next((nombre for nombre, indice in self.camera_indices.items() if indice == 0), opciones[0])
            )
            self.camera_menu.configure(values=opciones, state="normal")
            self.camera_var.set(etiqueta)
        else:
            self.camera_menu.configure(values=["Sin cámaras detectadas"], state="disabled")
            self.camera_var.set("Sin cámaras detectadas")
            if mostrar_error:
                messagebox.showerror(
                    "No se encontraron cámaras",
                    "No se detectó ninguna webcam disponible. Compruebe la conexión, los permisos "
                    "y que otra aplicación no esté usando la cámara.")

    def _abrir_camara_seleccionada(self):
        indice = self.camera_indices.get(self.camera_var.get())
        if indice is None:
            raise CameraOpenError("No hay una cámara seleccionada. Pulse «Detectar cámaras» y elija una webcam.")
        self.update_idletasks()
        cap, _, _ = abrir_camara_maxima(indice)
        return cap

    def _configurar_controles_camara(self, habilitados):
        tiene_camara = bool(getattr(self, "camera_indices", {}))
        estado = "normal" if habilitados else "disabled"
        self.camera_menu.configure(state=estado if tiene_camara else "disabled")
        self.btn_refrescar_camaras.configure(state=estado)

    def _cancelar_actualizacion_pendiente(self):
        after_id = getattr(self, "_frame_after_id", None)
        self._frame_after_id = None
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass

    def _liberar_captura(self):
        cap, self.cap = self.cap, None
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass

    def _restablecer_controles_captura(self):
        self.is_running = False
        self.is_calibrating = False
        self.start_time = None
        self.ctk_img = None
        self.btn_calibrar.configure(
            text="🔍 Vista Previa / Calibrar", fg_color="#F39C12", hover_color="#D68910",
            state="normal")
        self.btn_iniciar.configure(state="normal")
        self.btn_detener.configure(state="disabled")
        self.entry_iris.configure(state="normal")
        self._configurar_controles_camara(True)
        self.lbl_camara.configure(
            image="", text="Cámara inactiva\nHaga clic en 'Iniciar Medición' o 'Calibrar'")
        self.lbl_tiempo.configure(text="Tiempo: 0.0 s")
        self.lbl_fase.configure(text="Fase: Inactiva", text_color="#F39C12")

    def toggle_calibracion(self):
        if not self.is_calibrating:
            self.iniciar_calibracion()
        else:
            self.detener_calibracion()

    def iniciar_calibracion(self):
        try:
            val = float(self.entry_iris.get())
            if val <= 0:
                raise ValueError
            self.iris_mm = val
        except ValueError:
            messagebox.showerror(
                "Error de Calibración",
                "Por favor ingrese un número válido mayor a 0 para el diámetro del iris.")
            return

        try:
            self.cap = self._abrir_camara_seleccionada()
        except CameraOpenError as exc:
            messagebox.showerror(
                "Error de Cámara",
                str(exc)
            )
            return

        self.ctk_img = None
        self.is_calibrating = True
        self._configurar_controles_camara(False)
        self.btn_calibrar.configure(text="⏹ Detener Calibración", fg_color="#D35400", hover_color="#A04000")
        self.btn_iniciar.configure(state="disabled")
        self.btn_detener.configure(state="disabled")
        self.entry_iris.configure(state="disabled")

        self.actualizar_fotograma()

    def detener_calibracion(self):
        self._cancelar_actualizacion_pendiente()
        self._liberar_captura()
        self._restablecer_controles_captura()
        self.lbl_medicion.configure(text="Pupila: -- mm")

    def iniciar_medicion(self):
        if self.is_calibrating:
            self.detener_calibracion()

        try:
            val = float(self.entry_iris.get())
            if val <= 0:
                raise ValueError
            self.iris_mm = val
        except ValueError:
            messagebox.showerror(
                "Error de Calibración",
                "Por favor ingrese un número válido mayor a 0 para el diámetro del iris.")
            return

        self._cancelar_actualizacion_pendiente()
        try:
            cap = self._abrir_camara_seleccionada()
        except CameraOpenError as exc:
            self._liberar_captura()
            self._restablecer_controles_captura()
            messagebox.showerror(
                "Error de Cámara",
                str(exc)
            )
            return

        # La captura ya fue validada por el mismo patrón que usa calibración.
        # Si no se puede preparar el CSV, no dejar el dispositivo abierto ni la
        # interfaz en un estado que parezca estar grabando.
        try:
            with open(self.archivo_datos, mode="w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["timestamp", "pupila_mm"])
        except OSError as exc:
            try:
                cap.release()
            except Exception:
                pass
            self._liberar_captura()
            self._restablecer_controles_captura()
            messagebox.showerror(
                "Error al iniciar la grabación",
                f"No se pudo crear o escribir {self.archivo_datos} en el "
                f"directorio de trabajo {os.getcwd()}.\n\n{exc}")
            return

        self.cap = cap
        self.data_buffer = []
        self.ctk_img = None
        self.is_running = True
        self.start_time = time.time()

        self.btn_iniciar.configure(state="disabled")
        self.btn_detener.configure(state="normal")
        self.btn_calibrar.configure(state="disabled")
        self._configurar_controles_camara(False)
        self.entry_iris.configure(state="disabled")

        # Iniciar bucle de actualización
        self.actualizar_fotograma()

    def actualizar_fotograma(self):
        # El callback ya venció; al detener se cancela cualquier callback que
        # quede en cola para que no lea desde una captura de una sesión nueva.
        self._frame_after_id = None
        if (not self.is_running and not self.is_calibrating) or self.cap is None:
            return

        try:
            ret, frame = self.cap.read()
        except Exception as exc:
            self._detener_por_error_de_captura(str(exc))
            return
        if not ret:
            self._detener_por_error_de_captura("La transmisión de la cámara se interrumpió.")
            return

        tiempo_actual = time.time() - self.start_time if self.is_running else 0.0

        # Procesamiento de imagen
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

        detectado = False
        if circles is not None:
            circles = np.uint16(np.around(circles))
            sorted_circles = sorted(circles[0, :], key=lambda x: x[2])
            pupila = sorted_circles[0]
            iris = sorted_circles[-1]

            if iris[2] > 0:
                detectado = True
                escala = self.iris_mm / (2 * iris[2])
                pupila_mm = (2 * pupila[2]) * escala
                self.current_pupil_mm = pupila_mm

                # Dibujar guías en frame
                cv2.circle(frame, (pupila[0], pupila[1]), pupila[2], (0, 255, 0), 2)
                cv2.circle(frame, (iris[0], iris[1]), iris[2], (255, 0, 0), 2)
                cv2.circle(frame, (pupila[0], pupila[1]), 2, (0, 0, 255), 3)

                if self.is_calibrating:
                    cv2.putText(frame, "MODO CALIBRACION (SIN GRABAR)", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    cv2.putText(frame, f"Pupila: {pupila_mm:.2f} mm | Iris: {iris[2]*2}px", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                else:
                    # Guardar en buffer solo durante medición activa
                    self.data_buffer.append([time.time(), pupila_mm])

                self.lbl_medicion.configure(text=f"Pupila: {pupila_mm:.2f} mm")

        if self.is_calibrating:
            self.lbl_tiempo.configure(text="Tiempo: --")
            if detectado:
                self.lbl_fase.configure(text="Fase: Calibración (Pupila OK)", text_color="#2ECC71")
            else:
                self.lbl_fase.configure(text="Fase: Calibración (Buscando...)", text_color="#E67E22")
                self.lbl_medicion.configure(text="Pupila: Buscando...")
        else:
            # Determinar fase actual
            fase_actual = "Fase desconocida"
            for inicio, fin, nombre in self.intervalos:
                if inicio <= tiempo_actual < fin:
                    fase_actual = nombre
                    break
                elif tiempo_actual >= 90:
                    fase_actual = "Finalizado (> 90s)"

            self.lbl_tiempo.configure(text=f"Tiempo: {tiempo_actual:.1f} s")
            self.lbl_fase.configure(text=f"Fase: {fase_actual}", text_color="#F39C12")

        # Convertir imagen BGR de OpenCV a Tkinter
        cv2_im = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(cv2_im)

        # Reutilización dinámica de CTkImage (evita fuga de memoria y error pyimageXX)
        cw = self.video_container.winfo_width()
        ch = self.video_container.winfo_height()

        if cw > 50 and ch > 50:
            fh, fw = frame.shape[:2]
            scale = min(cw / fw, ch / fh)
            target_w = max(10, int(fw * scale))
            target_h = max(10, int(fh * scale))

            if self.ctk_img is None:
                self.ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(target_w, target_h))
                self.lbl_camara.configure(image=self.ctk_img, text="")
            else:
                self.ctk_img.configure(light_image=img, dark_image=img, size=(target_w, target_h))

        # Programar siguiente fotograma (aprox. 30 FPS)
        self._frame_after_id = self.after(30, self.actualizar_fotograma)

    def _detener_por_error_de_captura(self, detalle):
        if self.is_calibrating:
            self.detener_calibracion()
        else:
            self.detener_medicion(mostrar_resultados=False)
        messagebox.showerror("Error de Cámara", detalle)

    def detener_medicion(self, mostrar_resultados=True):
        self._cancelar_actualizacion_pendiente()
        self.is_running = False
        self._liberar_captura()

        # Escribir en disco todo el buffer acumulado
        error_guardado = None
        if self.data_buffer:
            try:
                with open(self.archivo_datos, mode="a", newline="") as file:
                    writer = csv.writer(file)
                    writer.writerows(self.data_buffer)
                self.data_buffer = []
            except OSError as exc:
                error_guardado = exc

        self._restablecer_controles_captura()
        if error_guardado is not None:
            messagebox.showerror(
                "Error al guardar la medición",
                f"No se pudo guardar el buffer en {self.archivo_datos}.\n\n{error_guardado}")
            return

        if not mostrar_resultados:
            return

        messagebox.showinfo(
            "Medición Finalizada",
            f"✅ Se han guardado las mediciones correctamente en {self.archivo_datos}."
        )

        # Generar análisis automáticamente al detener
        self.analizar_y_graficar()

    def analizar_y_graficar(self):
        if not os.path.exists(self.archivo_datos):
            messagebox.showwarning("Sin datos", "No existe archivo de mediciones aún.")
            return

        try:
            # Son dependencias pesadas y solo se necesitan al solicitar análisis.
            import pandas as pd
            import matplotlib.pyplot as plt

            df = pd.read_csv(self.archivo_datos)
            if df.empty or len(df) == 0:
                messagebox.showwarning("Archivo Vacío", "No hay datos grabados para generar análisis.")
                return

            df["tiempo_rel"] = df["timestamp"] - df["timestamp"].iloc[0]

            resultados = []
            for inicio, fin, nombre in self.intervalos:
                subset = df[(df["tiempo_rel"] >= inicio) & (df["tiempo_rel"] < fin)]
                if len(subset) > 0:
                    resultados.append({
                        "fase": nombre,
                        "inicio_s": inicio,
                        "fin_s": fin,
                        "media_mm": subset["pupila_mm"].mean(),
                        "desv_mm": subset["pupila_mm"].std(),
                        "min_mm": subset["pupila_mm"].min(),
                        "max_mm": subset["pupila_mm"].max(),
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
            resumen.to_csv(self.archivo_resumen, index=False)

            # Generar gráfico con Matplotlib
            fig, ax = plt.subplots(figsize=(9, 4.5), dpi=100)
            ax.plot(df["tiempo_rel"], df["pupila_mm"], color="gray", alpha=0.5, label="Señal original")

            colors = ["lightblue", "lightgreen", "lightcoral", "khaki", "plum"]
            centros = []
            medias_barras = []
            desv_barras = []

            for i, (inicio, fin, nombre) in enumerate(self.intervalos):
                ax.axvspan(inicio, fin, color=colors[i % len(colors)], alpha=0.3)
                subset = df[(df["tiempo_rel"] >= inicio) & (df["tiempo_rel"] < fin)]
                if len(subset) > 0:
                    centro = (inicio + fin) / 2
                    centros.append(centro)
                    medias_barras.append(subset["pupila_mm"].mean())
                    desv_barras.append(subset["pupila_mm"].std())

            if centros:
                ax.errorbar(
                    centros,
                    medias_barras,
                    yerr=desv_barras,
                    fmt='o',
                    color='blue',
                    ecolor='black',
                    elinewidth=2,
                    capsize=5,
                    label="Media ± 1 SD"
                )

            ax.set_title("Variación pupilar por fases experimentales")
            ax.set_xlabel("Tiempo (segundos desde inicio)")
            ax.set_ylabel("Diámetro pupilar (mm)")
            ax.grid(True)
            ax.legend()
            fig.tight_layout()

            # Desplegar gráfico integrado sin bloquear la app
            self._mostrar_ventana_grafico(fig)

        except Exception as e:
            messagebox.showerror("Error al procesar", str(e))

    def _mostrar_ventana_grafico(self, fig):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        top = ctk.CTkToplevel(self)
        top.title("Análisis Pupilar - Gráfico de Resultados")
        top.geometry("900x550")
        top.minsize(700, 400)

        # Hacer foco en la nueva ventana emergente
        top.after(100, top.lift)
        top.after(100, top.focus_force)

        canvas = FigureCanvasTkAgg(fig, master=top)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=15, pady=15)

        def _cerrar():
            plt.close(fig)
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", _cerrar)

    def abrir_carpeta(self):
        os.startfile(os.getcwd())

    def on_closing(self):
        if self.is_calibrating:
            self.detener_calibracion()
        if self.is_running:
            self.detener_medicion()
        # No inicializar Matplotlib al cerrar una app que nunca abrió el análisis.
        if "matplotlib.pyplot" in sys.modules:
            sys.modules["matplotlib.pyplot"].close("all")
        self.destroy()


if __name__ == "__main__":
    app = PupilometroApp()
    app.mainloop()
