"""Carga del archivo de reglas (config/reglas.json)."""
import json
from pathlib import Path
from typing import Any

RUTA_POR_DEFECTO = Path(__file__).resolve().parent.parent / "config" / "reglas.json"


def _sin_comentarios(valor: Any) -> Any:
    """Elimina las claves '_comentario' usadas para documentar el JSON."""
    if isinstance(valor, dict):
        return {k: _sin_comentarios(v) for k, v in valor.items() if not k.startswith("_")}
    if isinstance(valor, list):
        return [_sin_comentarios(v) for v in valor]
    return valor


def cargar_reglas(ruta: Path | str = RUTA_POR_DEFECTO) -> dict[str, Any]:
    with open(ruta, encoding="utf-8") as f:
        reglas = _sin_comentarios(json.load(f))

    # Índice inverso de estados: "approved" -> "APROBADA"
    reglas["_estado_por_valor"] = {
        valor.lower(): normalizado
        for normalizado, valores in reglas["mapeo_estados"].items()
        for valor in valores
    }
    return reglas
