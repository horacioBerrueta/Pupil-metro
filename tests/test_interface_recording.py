import tempfile
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

from interface_pupilometro import PupilometroApp


def crear_app_falsa():
    app = SimpleNamespace(
        is_running=False,
        is_calibrating=False,
        cap=None,
        start_time=None,
        iris_mm=12.0,
        data_buffer=[],
        ctk_img=None,
        _frame_after_id=None,
        archivo_datos="mediciones_pupila.csv",
        entry_iris=Mock(),
        btn_calibrar=Mock(),
        btn_iniciar=Mock(),
        btn_detener=Mock(),
        lbl_camara=Mock(),
        lbl_medicion=Mock(),
        lbl_tiempo=Mock(),
        lbl_fase=Mock(),
        _cancelar_actualizacion_pendiente=Mock(),
        _configurar_controles_camara=Mock(),
        _abrir_camara_seleccionada=Mock(),
        actualizar_fotograma=Mock(),
    )
    app.entry_iris.get.return_value = "12.0"
    app._liberar_captura = MethodType(PupilometroApp._liberar_captura, app)
    app._restablecer_controles_captura = MethodType(
        PupilometroApp._restablecer_controles_captura, app)
    return app


class RecordingFlowTests(unittest.TestCase):
    def test_cancelar_timer_limpia_el_id_antes_de_otra_sesion(self):
        app = SimpleNamespace(
            _frame_after_id="after#1",
            after_cancel=Mock(),
        )

        PupilometroApp._cancelar_actualizacion_pendiente(app)

        app.after_cancel.assert_called_once_with("after#1")
        self.assertIsNone(app._frame_after_id)

    def test_iniciar_grabacion_conserva_la_captura_abierta_y_arranca_bucle(self):
        app = crear_app_falsa()
        cap = Mock()
        app._abrir_camara_seleccionada.return_value = cap

        with tempfile.TemporaryDirectory() as directorio:
            app.archivo_datos = str(Path(directorio) / "mediciones.csv")
            PupilometroApp.iniciar_medicion(app)

            self.assertIs(app.cap, cap)
            self.assertFalse(cap.release.called)
            self.assertTrue(app.is_running)
            self.assertIsNotNone(app.start_time)
            app.actualizar_fotograma.assert_called_once_with()
            self.assertEqual(
                Path(app.archivo_datos).read_text(encoding="utf-8").strip(),
                "timestamp,pupila_mm",
            )

    @patch("interface_pupilometro.messagebox.showerror")
    def test_error_al_crear_csv_libera_captura_y_restaura_estado(self, mostrar_error):
        app = crear_app_falsa()
        cap = Mock()
        app._abrir_camara_seleccionada.return_value = cap

        with patch("builtins.open", side_effect=PermissionError("acceso denegado")):
            PupilometroApp.iniciar_medicion(app)

        cap.release.assert_called_once_with()
        self.assertIsNone(app.cap)
        self.assertFalse(app.is_running)
        self.assertIsNone(app.start_time)
        app.actualizar_fotograma.assert_not_called()
        app.btn_iniciar.configure.assert_called_with(state="normal")
        app.btn_detener.configure.assert_called_with(state="disabled")
        mostrar_error.assert_called_once()
        self.assertIn("directorio de trabajo", mostrar_error.call_args.args[1])

    @patch("interface_pupilometro.messagebox.showerror")
    def test_excepcion_de_read_detiene_y_libera_la_captura(self, mostrar_error):
        app = crear_app_falsa()
        cap = Mock()
        cap.read.side_effect = RuntimeError("driver desconectado")
        app.cap = cap
        app.is_running = True
        app.start_time = 123.0
        app._detener_por_error_de_captura = MethodType(
            PupilometroApp._detener_por_error_de_captura, app)
        app.detener_medicion = MethodType(PupilometroApp.detener_medicion, app)

        PupilometroApp.actualizar_fotograma(app)

        cap.release.assert_called_once_with()
        self.assertIsNone(app.cap)
        self.assertFalse(app.is_running)
        self.assertIsNone(app.start_time)
        mostrar_error.assert_called_once_with(
            "Error de Cámara", "driver desconectado")


if __name__ == "__main__":
    unittest.main()
