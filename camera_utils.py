"""Utilidades compartidas para descubrir y configurar webcams con OpenCV."""

import os

import cv2


RESOLUCION_MAXIMA_SOLICITADA = (1920, 1080)


class CameraOpenError(RuntimeError):
    """No se pudo abrir el índice de cámara solicitado."""


def _backends(plataforma=None):
    plataforma = os.name if plataforma is None else plataforma
    if plataforma == "nt":
        return (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY)
    return (cv2.CAP_ANY,)


def _probar_indice(indice, capture_factory=None, plataforma=None):
    """Devuelve una captura abierta o None; libera siempre las aperturas fallidas."""
    capture_factory = cv2.VideoCapture if capture_factory is None else capture_factory
    for backend in _backends(plataforma):
        cap = None
        try:
            cap = capture_factory(indice, backend)
            if cap is not None and cap.isOpened():
                return cap
        except Exception:
            pass
        _liberar(cap)
    return None


def _liberar(cap):
    """Libera una captura sin dejar que un backend defectuoso interrumpa el fallback."""
    if cap is not None:
        try:
            cap.release()
        except Exception:
            pass


def detectar_camaras(max_indice=10, capture_factory=None, plataforma=None):
    """Detecta índices accesibles y libera cada dispositivo antes de continuar."""
    indices = []
    for indice in range(max_indice):
        cap = _probar_indice(indice, capture_factory, plataforma)
        if cap is not None:
            indices.append(indice)
            _liberar(cap)
    return indices


def abrir_camara(indice, resolucion, capture_factory=None, plataforma=None):
    """Abre una webcam y devuelve (captura, resolución que informa CAP_PROP).

    Los valores de CAP_PROP_FRAME_WIDTH/HEIGHT son una respuesta del backend y
    no necesariamente describen las dimensiones de los fotogramas entregados.
    Para confirmar la resolución efectiva, use ``resolucion_del_frame``.
    """
    cap = _probar_indice(indice, capture_factory, plataforma)
    if cap is None:
        raise CameraOpenError(
            f"No se pudo abrir la cámara {indice}. Compruebe que esté conectada, "
            "que no la esté usando otra aplicación y que el sistema permita el acceso."
        )

    try:
        ancho, alto = resolucion
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        ancho_real = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        alto_real = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        efectiva = None
        if ancho_real > 0 and alto_real > 0:
            efectiva = (round(ancho_real), round(alto_real))
        return cap, efectiva
    except Exception as exc:
        _liberar(cap)
        raise CameraOpenError(
            f"No se pudo configurar la resolución de la cámara {indice}: {exc}"
        ) from exc


def abrir_camara_maxima(indice, capture_factory=None, plataforma=None):
    """Abre una cámara y valida su stream, devolviendo (captura, frame, CAP_PROP).

    Se conserva el nombre por compatibilidad con los dos puntos de entrada del
    proyecto. Prueba primero la resolución máxima y, si el dispositivo no entrega
    frames en ese modo, reabre en 640x480 antes de pasar al backend siguiente.
    La resolución devuelta procede del frame, no de CAP_PROP.
    """
    capture_factory = cv2.VideoCapture if capture_factory is None else capture_factory
    hubo_captura_abierta = False
    intentos = []
    for backend in _backends(plataforma):
        for ancho, alto in (RESOLUCION_MAXIMA_SOLICITADA, (640, 480)):
            cap = None
            try:
                cap = capture_factory(indice, backend)
                if cap is None or not cap.isOpened():
                    intentos.append(f"backend {backend}: no abrió a {ancho}x{alto}")
                    _liberar(cap)
                    continue
                hubo_captura_abierta = True

                # Algunos drivers abren el dispositivo pero no entregan frames
                # con el modo máximo; se vuelve a probar en resolución estándar.
                for propiedad, valor in (
                    (cv2.CAP_PROP_FRAME_WIDTH, ancho),
                    (cv2.CAP_PROP_FRAME_HEIGHT, alto),
                    (cv2.CAP_PROP_BUFFERSIZE, 1),
                ):
                    try:
                        cap.set(propiedad, valor)
                    except Exception:
                        pass

                for _ in range(3):
                    ret, frame = cap.read()
                    if ret:
                        observada = resolucion_del_frame(frame)
                        if observada is not None:
                            try:
                                ancho_prop = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                                alto_prop = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                                informada = (
                                    (round(ancho_prop), round(alto_prop))
                                    if ancho_prop > 0 and alto_prop > 0 else None
                                )
                            except Exception:
                                informada = None
                            return cap, observada, informada
                intentos.append(
                    f"backend {backend}: sin fotogramas válidos a {ancho}x{alto}"
                )
            except Exception as exc:
                intentos.append(f"backend {backend} a {ancho}x{alto}: {exc}")
            _liberar(cap)

    detalle = "; ".join(intentos)
    if hubo_captura_abierta:
        causa = (
            f"La cámara {indice} se pudo abrir, pero no inició el stream ni "
            "entregó fotogramas válidos, incluso al reintentar en 640x480."
        )
    else:
        causa = f"No se pudo abrir la cámara {indice} con los backends disponibles."
    if detalle:
        causa += f" Intentos: {detalle}."
    causa += (
        " Compruebe que esté conectada, que ninguna otra aplicación la esté "
        "usando y que el sistema permita el acceso a la cámara."
    )
    raise CameraOpenError(causa)


def resolucion_del_frame(frame):
    """Devuelve (ancho, alto) observados en frame.shape, o None si no es válido."""
    forma = getattr(frame, "shape", None)
    try:
        if forma is None or len(forma) < 2:
            return None
        alto, ancho = int(forma[0]), int(forma[1])
    except (TypeError, ValueError, OverflowError, IndexError):
        return None
    if ancho <= 0 or alto <= 0:
        return None
    return ancho, alto
