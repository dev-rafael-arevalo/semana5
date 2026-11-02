"""Validación: aplica los criterios de config/reglas.json -> 'validacion'.

Cada regla agrega un código de error legible. Una transacción con al menos un
error se considera inválida. Qué se hace con ella lo decide 'politica_invalidas'.
"""
from datetime import datetime
from decimal import Decimal

from .modelo import ESTADOS_VALIDOS, Transaccion
from .normalizador import FUENTE_DESCONOCIDA, es_vacio, obtener_campo, zona_horaria

POLITICAS = ("separar", "marcar", "descartar")

# Código de error por campo obligatorio: (no venía en el registro, venía pero no se pudo interpretar)
CODIGOS_CAMPO = {
    "id":     ("ID_FALTANTE", "ID_INVALIDO"),
    "fecha":  ("FECHA_FALTANTE", "FECHA_INVALIDA"),
    "monto":  ("MONTO_FALTANTE", "MONTO_INVALIDO"),
    "moneda": ("MONEDA_FALTANTE", "MONEDA_INVALIDA"),
    "estado": ("ESTADO_FALTANTE", "ESTADO_INVALIDO"),
}


def validar(tx: Transaccion, reglas: dict, ahora: datetime | None = None) -> Transaccion:
    criterios = reglas["validacion"]
    errores: list[str] = []

    if tx.fuente == FUENTE_DESCONOCIDA:
        errores.append("FUENTE_DESCONOCIDA")
    else:
        for campo in criterios["campos_obligatorios"]:
            if getattr(tx, campo) is None:
                # Distinguimos "no venía" de "venía pero no se pudo interpretar"
                ruta = reglas["fuentes"][tx.fuente]["campos"].get(campo, campo)
                venia = not es_vacio(obtener_campo(tx.original, ruta))
                faltante, invalido = CODIGOS_CAMPO.get(campo, (f"{campo.upper()}_FALTANTE",) * 2)
                errores.append(invalido if venia else faltante)

    if tx.monto is not None:
        minimo = Decimal(str(criterios["monto_minimo"]))
        maximo = Decimal(str(criterios["monto_maximo"]))
        if tx.monto < minimo:
            errores.append("MONTO_MENOR_AL_MINIMO")
        elif tx.monto > maximo:
            errores.append("MONTO_MAYOR_AL_MAXIMO")

    if tx.moneda is not None and tx.moneda not in reglas["monedas_soportadas"]:
        errores.append("MONEDA_NO_SOPORTADA")

    if tx.estado is not None and tx.estado not in ESTADOS_VALIDOS:
        errores.append("ESTADO_NO_RECONOCIDO")

    if tx.fecha is not None:
        tz = zona_horaria(reglas)
        ahora = ahora or datetime.now(tz)
        if not criterios["permitir_fecha_futura"] and tx.fecha > ahora:
            errores.append("FECHA_FUTURA")
        minima = datetime.fromisoformat(criterios["fecha_minima"]).replace(tzinfo=tz)
        if tx.fecha < minima:
            errores.append("FECHA_ANTERIOR_A_MINIMA")

    tx.errores = errores
    tx.valida = not errores
    return tx


def marcar_duplicados(transacciones: list[Transaccion]) -> None:
    """Un duplicado es la misma (fuente, id) repetida. La primera aparición se
    conserva; las siguientes se marcan inválidas con DUPLICADO."""
    vistos: set[tuple[str, str]] = set()
    for tx in transacciones:
        if tx.id is None:
            continue
        clave = (tx.fuente, tx.id)
        if clave in vistos:
            tx.errores.append("DUPLICADO")
            tx.valida = False
        else:
            vistos.add(clave)
