"""Orquesta el flujo: leer JSON -> normalizar -> validar -> aplicar política."""
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .modelo import Transaccion
from .normalizador import normalizar_registro
from .validador import POLITICAS, marcar_duplicados, validar


@dataclass
class Resultado:
    archivo: str
    politica: str
    validas: list[Transaccion] = field(default_factory=list)
    invalidas: list[Transaccion] = field(default_factory=list)  # vacía si politica = descartar
    total_procesadas: int = 0
    total_invalidas: int = 0
    # Se cuentan siempre, incluso si las inválidas se descartan
    errores_por_tipo: Counter = field(default_factory=Counter)
    invalidas_por_fuente: Counter = field(default_factory=Counter)

    @property
    def visibles(self) -> list[Transaccion]:
        """Lo que la interfaz muestra como 'lista principal' según la política."""
        if self.politica == "marcar":
            return self.validas + self.invalidas
        return self.validas


def leer_registros(ruta: Path | str) -> list:
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    # Se acepta una lista directa o un objeto {"transacciones": [...]}
    if isinstance(datos, dict) and isinstance(datos.get("transacciones"), list):
        return datos["transacciones"]
    if isinstance(datos, list):
        return datos
    raise ValueError("El JSON debe ser una lista o un objeto con la clave 'transacciones'.")


def procesar(ruta: Path | str, reglas: dict) -> Resultado:
    politica = reglas["politica_invalidas"]["accion"]
    if politica not in POLITICAS:
        raise ValueError(f"politica_invalidas.accion debe ser una de {POLITICAS}")

    transacciones = [validar(normalizar_registro(r, reglas), reglas) for r in leer_registros(ruta)]
    if reglas["validacion"].get("detectar_duplicados", True):
        marcar_duplicados(transacciones)

    resultado = Resultado(archivo=str(ruta), politica=politica,
                          total_procesadas=len(transacciones))
    for tx in transacciones:
        if tx.valida:
            resultado.validas.append(tx)
        else:
            resultado.total_invalidas += 1
            resultado.errores_por_tipo.update(tx.errores)
            resultado.invalidas_por_fuente[tx.fuente] += 1
            if politica != "descartar":
                resultado.invalidas.append(tx)
    return resultado
