# core/capture.py — captura de vídeo
# Webcam: thread separada elimina buffer acumulado (câmera não para de capturar)
# Vídeo arquivo: leitura direta — threading não ajuda e adiciona overhead
import threading
import time
from sys import platform

import cv2


class VideoCapture:
    def __init__(self, source, width=None, height=None, fps=None):
        self._is_webcam = isinstance(source, int)
        self._cap = self._open_capture(source)

        if not self._cap.isOpened():
            raise RuntimeError(f"Não foi possível abrir: {source}")

        if self._is_webcam:
            if width:
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            if height:
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            if fps:
                self._cap.set(cv2.CAP_PROP_FPS, fps)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            # thread só para webcam
            self._frame = None
            self._ok = False
            self._lock = threading.Lock()
            self._stop = threading.Event()
            self._thread = threading.Thread(target=self._reader, daemon=True)
            self._thread.start()
            # Algumas webcams do Windows demoram alguns segundos para entregar
            # o primeiro frame. Aguarda a inicializacao sem considerar a
            # primeira leitura vazia como falha definitiva.
            deadline = time.monotonic() + 5.0
            while self._frame is None and time.monotonic() < deadline:
                time.sleep(0.05)

    def _open_capture(self, source):
        if not isinstance(source, int):
            return cv2.VideoCapture(source)

        backends = [cv2.CAP_ANY]
        if platform.startswith("win"):
            backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]

        for backend in backends:
            cap = cv2.VideoCapture(source, backend)
            if cap.isOpened():
                return cap
            cap.release()

        return cv2.VideoCapture(source)

    def _reader(self):
        """Thread só usada na webcam."""
        while not self._stop.is_set():
            ok, frame = self._cap.read()
            with self._lock:
                if ok and frame is not None:
                    self._frame = frame
                self._ok = ok
            if not ok:
                time.sleep(0.05)

    def read(self):
        if self._is_webcam:
            with self._lock:
                if self._frame is None:
                    return False, None
                return self._ok, self._frame.copy()
        # vídeo arquivo — leitura direta
        return self._cap.read()

    # --- metadados ---
    @property
    def is_webcam(self):
        return self._is_webcam

    @property
    def fps(self):
        v = self._cap.get(cv2.CAP_PROP_FPS)
        return v if v > 0 else 30

    @property
    def width(self):
        return int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    @property
    def height(self):
        return int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def release(self):
        if self._is_webcam:
            self._stop.set()
            self._thread.join(timeout=2)
        self._cap.release()
