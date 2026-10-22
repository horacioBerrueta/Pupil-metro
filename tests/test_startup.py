import subprocess
import sys
import unittest
from pathlib import Path


class StartupImportTests(unittest.TestCase):
    def test_importar_interfaz_no_carga_dependencias_de_analisis(self):
        raiz = Path(__file__).resolve().parents[1]
        codigo = (
            "import sys; import interface_pupilometro; "
            "assert 'pandas' not in sys.modules; "
            "assert 'matplotlib.pyplot' not in sys.modules; "
            "assert 'matplotlib.backends.backend_tkagg' not in sys.modules"
        )

        resultado = subprocess.run(
            [sys.executable, "-c", codigo],
            cwd=raiz,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(resultado.returncode, 0, resultado.stderr)


if __name__ == "__main__":
    unittest.main()
