"""Esquema normalizado de una transacción.

Todas las fuentes, sin importar su estructura original, terminan en este formato.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

ESTADOS_VALIDOS = ("APROBADA", "PENDIENTE", "RECHAZADA", "REEMBOLSADA")


@dataclass
class Transaccion:
    # Identificación
    id: Optional[str]
    fuente: str                       # pasarela_web | banco | pos_tienda | DESCONOCIDA

    # Datos de negocio normalizados (None = no se pudo interpretar el valor original)
    fecha: Optional[datetime]         # siempre con zona horaria (America/El_Salvador)
    monto: Optional[Decimal]          # unidades de la moneda, 2 decimales (nunca centavos)
    moneda: Optional[str]             # código ISO-4217 en mayúscula
    estado: Optional[str]             # uno de ESTADOS_VALIDOS
    cliente: Optional[str] = None
    descripcion: Optional[str] = None

    # Resultado de la validación
    valida: bool = True
    errores: list[str] = field(default_factory=list)

    # Trazabilidad: registro tal como llegó y advertencias del proceso de normalización
    original: dict[str, Any] = field(default_factory=dict)
    notas: list[str] = field(default_factory=list)

    def a_dict(self, incluir_original: bool = False) -> dict[str, Any]:
        datos = {
            "id": self.id,
            "fuente": self.fuente,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "monto": f"{self.monto:.2f}" if self.monto is not None else None,
            "moneda": self.moneda,
            "estado": self.estado,
            "cliente": self.cliente,
            "descripcion": self.descripcion,
            "valida": self.valida,
            "errores": list(self.errores),
        }
        if incluir_original:
            datos["original"] = self.original
            datos["notas"] = list(self.notas)
        return datos
