"""Métricas sobre el resultado del procesamiento.

Decisión: los totales por moneda se calculan SOLO con transacciones válidas
(sumar montos inválidos no tiene sentido) y se desglosan por estado, porque
sumar una venta aprobada con una rechazada daría una cifra engañosa.
"""
from collections import Counter, defaultdict
from decimal import Decimal

from .modelo import Transaccion
from .procesador import Resultado


def calcular_metricas(resultado: Resultado) -> dict:
    validas = resultado.validas

    por_moneda_estado: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for tx in validas:
        por_moneda_estado[tx.moneda][tx.estado] += tx.monto

    totales_moneda = {
        moneda: {
            "total": sum(estados.values(), Decimal("0")),
            # Neto = lo que efectivamente entró: aprobadas menos reembolsos
            "neto": estados.get("APROBADA", Decimal("0")) - estados.get("REEMBOLSADA", Decimal("0")),
            "por_estado": dict(estados),
        }
        for moneda, estados in sorted(por_moneda_estado.items())
    }

    return {
        "total_procesadas": resultado.total_procesadas,
        "validas": len(validas),
        "invalidas": resultado.total_invalidas,
        "porcentaje_validas": (len(validas) / resultado.total_procesadas * 100)
                              if resultado.total_procesadas else 0.0,
        "por_estado": dict(Counter(tx.estado for tx in validas).most_common()),
        "por_fuente": _por_fuente(validas, resultado.invalidas_por_fuente),
        "totales_por_moneda": totales_moneda,
        "errores_frecuentes": dict(resultado.errores_por_tipo.most_common()),
    }


def _por_fuente(validas: list[Transaccion], invalidas_por_fuente: Counter) -> dict:
    conteo: dict[str, dict[str, int]] = defaultdict(lambda: {"validas": 0, "invalidas": 0})
    for tx in validas:
        conteo[tx.fuente]["validas"] += 1
    for fuente, cantidad in invalidas_por_fuente.items():
        conteo[fuente]["invalidas"] = cantidad
    return dict(sorted(conteo.items()))
