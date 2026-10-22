import unittest
from types import SimpleNamespace

import cv2

from camera_utils import (
    CameraOpenError,
    RESOLUCION_MAXIMA_SOLICITADA,
    abrir_camara,
    abrir_camara_maxima,
    detectar_camaras,
    resolucion_del_frame,
)


class CapturaFalsa:
    def __init__(self, abierta=True, efectiva=(640, 480)):
        self.abierta = abierta
        self.efectiva = efectiva
        self.liberada = False
        self.valores = {}

    def isOpened(self):
        return self.abierta

    def release(self):
        self.liberada = True

    def set(self, propiedad, valor):
        self.valores[propiedad] = valor
        return True

    def get(self, propiedad):
        return {
            cv2.CAP_PROP_FRAME_WIDTH: self.efectiva[0],
            cv2.CAP_PROP_FRAME_HEIGHT: self.efectiva[1],
        }.get(propiedad, 0)


class CameraUtilsTests(unittest.TestCase):
    def test_deteccion_libera_todos_los_dispositivos_probados(self):
        capturas = []

        def factory(indice, backend):
            cap = CapturaFalsa(abierta=indice in (0, 2))
            capturas.append(cap)
            return cap

        self.assertEqual(detectar_camaras(max_indice=4, capture_factory=factory, plataforma="linux"), [0, 2])
        self.assertEqual(len(capturas), 4)
        self.assertTrue(all(cap.liberada for cap in capturas))

    def test_windows_reintenta_con_backend_generico_y_libera_la_prueba(self):
        capturas = []
        backends = []

        def factory(indice, backend):
            backends.append(backend)
            cap = CapturaFalsa(abierta=backend == cv2.CAP_ANY)
            capturas.append(cap)
            return cap

        self.assertEqual(detectar_camaras(max_indice=1, capture_factory=factory, plataforma="nt"), [0])
        self.assertEqual(backends, [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY])
        self.assertTrue(all(cap.liberada for cap in capturas))

    def test_configura_la_resolucion_antes_de_devolver_captura(self):
        cap = CapturaFalsa(efectiva=(800, 600))
        resultado, efectiva = abrir_camara(
            2,
            (800, 600),
            capture_factory=lambda indice, backend: cap,
            plataforma="linux",
        )

        self.assertIs(resultado, cap)
        self.assertEqual(efectiva, (800, 600))
        self.assertEqual(cap.valores[cv2.CAP_PROP_FRAME_WIDTH], 800)
        self.assertEqual(cap.valores[cv2.CAP_PROP_FRAME_HEIGHT], 600)
        self.assertEqual(cap.valores[cv2.CAP_PROP_BUFFERSIZE], 1)
        self.assertFalse(cap.liberada)

    def test_error_de_apertura_es_claro_y_libera_la_captura_fallida(self):
        capturas = []

        def factory(indice, backend):
            cap = CapturaFalsa(abierta=False)
            capturas.append(cap)
            return cap

        with self.assertRaisesRegex(CameraOpenError, "No se pudo abrir la cámara 4"):
            abrir_camara(4, (640, 480), capture_factory=factory, plataforma="linux")
        self.assertTrue(capturas[0].liberada)

    def test_frame_confirma_resolucion_aunque_cap_prop_repita_la_solicitada(self):
        cap = CapturaFalsa(efectiva=(1280, 720))
        resultado, informada = abrir_camara(
            0,
            (1280, 720),
            capture_factory=lambda indice, backend: cap,
            plataforma="linux",
        )

        class FrameFalso:
            shape = (480, 640, 3)

        # Simula el backend que devuelve la solicitud por CAP_PROP aunque emita 640×480.
        self.assertIs(resultado, cap)
        self.assertEqual(informada, (1280, 720))
        self.assertEqual(resolucion_del_frame(FrameFalso()), (640, 480))
        self.assertNotEqual(resolucion_del_frame(FrameFalso()), informada)

    def test_frame_sin_dimensiones_validas_no_confirma_resolucion(self):
        self.assertIsNone(resolucion_del_frame(None))

        class FrameInvalido:
            shape = (0, 640, 3)

        self.assertIsNone(resolucion_del_frame(FrameInvalido()))

    def test_abre_una_vez_y_reporta_la_resolucion_del_fotograma_real(self):
        capturas = []

        class CapturaConFrame(CapturaFalsa):
            def read(self):
                return True, SimpleNamespace(shape=(720, 1280, 3))

        def factory(indice, backend):
            cap = CapturaConFrame(efectiva=(1920, 1080))
            capturas.append(cap)
            return cap

        cap, resolucion_frame, informada = abrir_camara_maxima(
            0,
            capture_factory=factory,
            plataforma="nt",
        )

        self.assertEqual(resolucion_frame, (1280, 720))
        self.assertEqual(informada, (1920, 1080))
        self.assertEqual(len(capturas), 1)
        self.assertEqual(
            cap.valores[cv2.CAP_PROP_FRAME_WIDTH],
            RESOLUCION_MAXIMA_SOLICITADA[0],
        )
        self.assertEqual(
            cap.valores[cv2.CAP_PROP_FRAME_HEIGHT],
            RESOLUCION_MAXIMA_SOLICITADA[1],
        )
        self.assertFalse(cap.liberada)

    def test_fallback_a_otro_backend_si_el_primero_no_entrega_frames(self):
        capturas = []

        class CapturaSinFrames(CapturaFalsa):
            def read(self):
                return False, None

        class CapturaConFrame(CapturaFalsa):
            def read(self):
                return True, SimpleNamespace(shape=(480, 640, 3))

        def factory(indice, backend):
            cap = CapturaSinFrames() if backend == cv2.CAP_DSHOW else CapturaConFrame()
            capturas.append((backend, cap))
            return cap

        cap, real, _ = abrir_camara_maxima(
            0,
            capture_factory=factory,
            plataforma="nt",
        )
        self.assertEqual(real, (640, 480))
        self.assertIs(cap, capturas[2][1])
        self.assertTrue(capturas[0][1].liberada)
        self.assertTrue(capturas[1][1].liberada)
        self.assertFalse(capturas[2][1].liberada)

    def test_reintenta_en_640x480_si_el_modo_maximo_no_entrega_frames(self):
        capturas = []

        class CapturaPorResolucion(CapturaFalsa):
            def read(self):
                if self.valores.get(cv2.CAP_PROP_FRAME_WIDTH) == 640:
                    return True, SimpleNamespace(shape=(480, 640, 3))
                return False, None

        def factory(indice, backend):
            cap = CapturaPorResolucion()
            capturas.append(cap)
            return cap

        cap, real, _ = abrir_camara_maxima(
            0,
            capture_factory=factory,
            plataforma="linux",
        )

        self.assertIs(cap, capturas[1])
        self.assertEqual(real, (640, 480))
        self.assertEqual(
            capturas[0].valores[cv2.CAP_PROP_FRAME_WIDTH],
            RESOLUCION_MAXIMA_SOLICITADA[0],
        )
        self.assertEqual(capturas[1].valores[cv2.CAP_PROP_FRAME_WIDTH], 640)
        self.assertTrue(capturas[0].liberada)
        self.assertFalse(capturas[1].liberada)

    def test_cap_prop_no_disponible_no_impide_usar_un_stream_funcional(self):
        class CapturaSinPropiedades(CapturaFalsa):
            def set(self, propiedad, valor):
                raise RuntimeError("propiedad no soportada")

            def get(self, propiedad):
                raise RuntimeError("consulta no soportada")

            def read(self):
                return True, SimpleNamespace(shape=(480, 640, 3))

        cap = CapturaSinPropiedades()
        resultado, real, informada = abrir_camara_maxima(
            0,
            capture_factory=lambda indice, backend: cap,
            plataforma="linux",
        )
        self.assertIs(resultado, cap)
        self.assertEqual(real, (640, 480))
        self.assertIsNone(informada)
        self.assertFalse(cap.liberada)

    def test_error_si_ningun_backend_entrega_frames_y_libera_capturas(self):
        capturas = []

        class CapturaSinFrames(CapturaFalsa):
            def read(self):
                return False, None

        def factory(indice, backend):
            cap = CapturaSinFrames()
            capturas.append(cap)
            return cap

        with self.assertRaisesRegex(CameraOpenError, "no inició el stream"):
            abrir_camara_maxima(
                0,
                capture_factory=factory,
                plataforma="nt",
            )
        self.assertEqual(len(capturas), 6)
        self.assertTrue(all(cap.liberada for cap in capturas))
        with self.assertRaisesRegex(CameraOpenError, "Intentos:"):
            abrir_camara_maxima(
                0,
                capture_factory=factory,
                plataforma="linux",
            )


if __name__ == "__main__":
    unittest.main()
