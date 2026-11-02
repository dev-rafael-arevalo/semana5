"""Punto de entrada.

Uso:
    python main.py                                   # usa data/transacciones.json
    python main.py data/datos_inconsistentes.json
    python main.py --reglas config/reglas.json data/datos_validos.json
"""
import argparse
from pathlib import Path

from src.configuracion import RUTA_POR_DEFECTO, cargar_reglas
from src.interfaz_cli import ejecutar

BASE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalización y exploración de transacciones multifuente")
    parser.add_argument("archivo", nargs="?", default=BASE / "data" / "transacciones.json",
                        help="Archivo JSON con transacciones")
    parser.add_argument("--reglas", default=RUTA_POR_DEFECTO, help="Archivo de reglas JSON")
    args = parser.parse_args()

    try:
        ejecutar(Path(args.archivo), cargar_reglas(args.reglas))
    except (KeyboardInterrupt, EOFError):
        print("\nSesión terminada.")


if __name__ == "__main__":
    main()
