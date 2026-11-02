"""Normalización: detecta la fuente de cada registro y lo convierte al esquema común.

Este módulo NO decide si una transacción es válida. Si un valor no se puede
interpretar, el campo queda en None y se deja una nota; el validador decide.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional

from .modelo import Transaccion

FUENTE_DESCONOCIDA = "DESCONOCIDA"
DOS_DECIMALES = Decimal("0.01")


# ---------------------------------------------------------------- utilidades
def obtener_campo(registro: dict, ruta: str) -> Any:
    """Lee un campo, soportando rutas anidadas como 'customer.email'."""
    actual: Any = registro
    for parte in ruta.split("."):
        if not isinstance(actual, dict) or parte not in actual:
            return None
        actual = actual[parte]
    return actual


def tiene_campo(registro: dict, ruta: str) -> bool:
    """True si la clave existe (aunque su valor sea null o vacío)."""
    *padres, ultimo = ruta.split(".")
    contenedor = obtener_campo(registro, ".".join(padres)) if padres else registro
    return isinstance(contenedor, dict) and ultimo in contenedor


def es_vacio(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


# ---------------------------------------------------------- detección fuente
def detectar_fuente(registro: dict, reglas: dict) -> str:
    """1) Si el registro declara 'fuente' conocida, se respeta.
    2) Si no, se busca la fuente cuyos campos 'detectar_por' estén todos presentes."""
    declarada = registro.get("fuente")
    if isinstance(declarada, str) and declarada in reglas["fuentes"]:
        return declarada
    for nombre, definicion in reglas["fuentes"].items():
        if all(tiene_campo(registro, c) for c in definicion["detectar_por"]):
            return nombre
    return FUENTE_DESCONOCIDA


# ----------------------------------------------------------------- montos
def normalizar_monto(valor: Any, definicion: dict, notas: list[str]) -> Optional[Decimal]:
    if es_vacio(valor):
        return None
    formato = definicion["formato_monto"]
    try:
        if isinstance(valor, bool):
            raise TypeError("booleano no es un monto")
        if formato == "centavos":
            if isinstance(valor, float) and not valor.is_integer():
                notas.append(f"monto en centavos con decimales: {valor!r}")
                return None
            monto = Decimal(str(int(valor))) / 100
        elif formato == "decimal":
            monto = Decimal(str(valor))
        elif formato == "texto":
            texto = str(valor).strip()
            for simbolo in ("$", "€", "Q", "US", " "):
                texto = texto.replace(simbolo, "")
            texto = texto.replace(definicion.get("separador_miles", ","), "")
            texto = texto.replace(definicion.get("separador_decimal", "."), ".")
            monto = Decimal(texto)
        else:
            notas.append(f"formato_monto desconocido en reglas: {formato}")
            return None
    except (InvalidOperation, ValueError, TypeError):
        notas.append(f"monto no interpretable: {valor!r}")
        return None
    if not monto.is_finite():
        notas.append(f"monto no finito: {valor!r}")
        return None
    return monto.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


# ----------------------------------------------------------------- moneda
def normalizar_moneda(valor: Any, reglas: dict, notas: list[str]) -> Optional[str]:
    if es_vacio(valor):
        return None
    clave = str(valor).strip().lower()
    if clave in reglas["alias_moneda"]:
        return reglas["alias_moneda"][clave]
    # Sin alias: se conserva el código en mayúscula para que el validador lo evalúe
    notas.append(f"moneda sin alias definido: {valor!r}")
    return str(valor).strip().upper()


# ----------------------------------------------------------------- estado
def normalizar_estado(valor: Any, reglas: dict, notas: list[str]) -> Optional[str]:
    if es_vacio(valor):
        return None
    clave = str(valor).strip().lower()
    estado = reglas["_estado_por_valor"].get(clave)
    if estado is None:
        notas.append(f"estado sin mapeo: {valor!r}")
    return estado


# ------------------------------------------------------------------ fecha
def zona_horaria(reglas: dict) -> timezone:
    zh = reglas["zona_horaria"]
    return timezone(timedelta(hours=zh["offset_horas"]), zh["nombre"])


def normalizar_fecha(valor: Any, reglas: dict, notas: list[str]) -> Optional[datetime]:
    if es_vacio(valor):
        return None
    tz = zona_horaria(reglas)

    # Epoch (segundos) como número o texto numérico
    if reglas.get("aceptar_epoch") and not isinstance(valor, bool):
        try:
            segundos = float(valor)
            return datetime.fromtimestamp(segundos, tz=timezone.utc).astimezone(tz)
        except (ValueError, TypeError, OverflowError, OSError):
            pass

    texto = str(valor).strip()
    if texto.endswith("Z"):  # 'Z' = UTC
        texto = texto[:-1] + "+0000"
    for formato in reglas["formatos_fecha"]:
        try:
            fecha = datetime.strptime(texto, formato)
        except ValueError:
            continue
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=tz)  # sin zona -> se asume hora local
        return fecha.astimezone(tz)
    notas.append(f"fecha con formato no soportado: {valor!r}")
    return None


# ------------------------------------------------------------- principal
def _texto(valor: Any) -> Optional[str]:
    return None if es_vacio(valor) else str(valor).strip()


def normalizar_registro(registro: Any, reglas: dict) -> Transaccion:
    if not isinstance(registro, dict):
        return Transaccion(id=None, fuente=FUENTE_DESCONOCIDA, fecha=None, monto=None,
                           moneda=None, estado=None, original={"valor": registro},
                           notas=["el registro no es un objeto JSON"])

    fuente = detectar_fuente(registro, reglas)
    if fuente == FUENTE_DESCONOCIDA:
        return Transaccion(id=_texto(registro.get("id")), fuente=fuente, fecha=None,
                           monto=None, moneda=None, estado=None, original=registro,
                           notas=["no coincide con ninguna fuente definida en reglas"])

    definicion = reglas["fuentes"][fuente]
    campos = definicion["campos"]
    notas: list[str] = []

    def leer(campo: str) -> Any:
        return obtener_campo(registro, campos[campo]) if campo in campos else None

    return Transaccion(
        id=_texto(leer("id")),
        fuente=fuente,
        fecha=normalizar_fecha(leer("fecha"), reglas, notas),
        monto=normalizar_monto(leer("monto"), definicion, notas),
        moneda=normalizar_moneda(leer("moneda"), reglas, notas),
        estado=normalizar_estado(leer("estado"), reglas, notas),
        cliente=_texto(leer("cliente")),
        descripcion=_texto(leer("descripcion")),
        original=registro,
        notas=notas,
    )
