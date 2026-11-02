"""Interfaz web (opcional). Requiere Flask: pip install -r requirements.txt

Uso:
    python web.py                                  # abre http://127.0.0.1:5000
    python web.py data/datos_inconsistentes.json --puerto 8000
"""
import argparse
from pathlib import Path

from src.configuracion import RUTA_POR_DEFECTO, cargar_reglas
from src.interfaz_web import crear_app

BASE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Interfaz web del explorador de transacciones")
    parser.add_argument("archivo", nargs="?", default=BASE / "data" / "transacciones.json")
    parser.add_argument("--reglas", default=RUTA_POR_DEFECTO)
    parser.add_argument("--puerto", type=int, default=5000)
    args = parser.parse_args()

    app = crear_app(Path(args.archivo), cargar_reglas(args.reglas))
    print(f"Abre http://127.0.0.1:{args.puerto} en tu navegador (Ctrl+C para detener)")
    app.run(host="127.0.0.1", port=args.puerto, debug=False)


if __name__ == "__main__":
    main()
