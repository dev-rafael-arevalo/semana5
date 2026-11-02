"""Filtros y ordenamiento sobre transacciones normalizadas (sin lógica de interfaz)."""
from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal
from typing import Optional

from .modelo import Transaccion


@dataclass
class Filtros:
    fuente: Optional[str] = None
    estado: Optional[str] = None
    moneda: Optional[str] = None
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    monto_min: Optional[Decimal] = None
    monto_max: Optional[Decimal] = None
    texto: Optional[str] = None          # busca en id, cliente y descripción
    ordenar_por: str = "fecha"           # fecha | monto | id
    descendente: bool = False

    def activos(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)
                if f.name not in ("ordenar_por", "descendente") and getattr(self, f.name) is not None}

    def cumple(self, tx: Transaccion) -> bool:
        if self.fuente and tx.fuente != self.fuente:
            return False
        if self.estado and tx.estado != self.estado:
            return False
        if self.moneda and tx.moneda != self.moneda:
            return False
        if self.fecha_desde and (tx.fecha is None or tx.fecha.date() < self.fecha_desde):
            return False
        if self.fecha_hasta and (tx.fecha is None or tx.fecha.date() > self.fecha_hasta):
            return False
        if self.monto_min is not None and (tx.monto is None or tx.monto < self.monto_min):
            return False
        if self.monto_max is not None and (tx.monto is None or tx.monto > self.monto_max):
            return False
        if self.texto:
            buscado = self.texto.lower()
            campos = (tx.id, tx.cliente, tx.descripcion)
            if not any(c and buscado in c.lower() for c in campos):
                return False
        return True


def aplicar(transacciones: list[Transaccion], filtros: Filtros) -> list[Transaccion]:
    resultado = [tx for tx in transacciones if filtros.cumple(tx)]

    def clave(tx: Transaccion):
        valor = getattr(tx, filtros.ordenar_por)
        return (valor is None, valor if valor is not None else 0)  # None siempre al final

    try:
        resultado.sort(key=clave, reverse=filtros.descendente)
    except TypeError:
        pass  # ordenar_por inválido: se deja el orden original
    return resultado
