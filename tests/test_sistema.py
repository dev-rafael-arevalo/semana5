"""Pruebas: python -m unittest discover -s tests -v"""
import json
import unittest
from decimal import Decimal
from pathlib import Path

from src.configuracion import cargar_reglas
from src.metricas import calcular_metricas
from src.normalizador import detectar_fuente, normalizar_registro
from src.procesador import procesar

BASE = Path(__file__).resolve().parent.parent
REGLAS = cargar_reglas()


class TestNormalizacion(unittest.TestCase):
    def test_detecta_fuentes(self):
        self.assertEqual(detectar_fuente({"txn_id": "x", "amount_cents": 1}, REGLAS), "pasarela_web")
        self.assertEqual(detectar_fuente({"referencia": "x", "monto": "1"}, REGLAS), "banco")
        self.assertEqual(detectar_fuente({"ticket": "x", "total": 1}, REGLAS), "pos_tienda")
        self.assertEqual(detectar_fuente({"otro": 1}, REGLAS), "DESCONOCIDA")

    def test_centavos_a_unidades(self):
        tx = normalizar_registro({"txn_id": "a", "amount_cents": 2599, "currency": "usd",
                                  "status": "succeeded", "created_at": "2026-10-02T14:30:00Z"}, REGLAS)
        self.assertEqual(tx.monto, Decimal("25.99"))
        self.assertEqual(tx.moneda, "USD")
        self.assertEqual(tx.estado, "APROBADA")
        self.assertEqual(tx.fecha.isoformat(), "2026-10-02T08:30:00-06:00")  # UTC -> El Salvador

    def test_monto_texto_formato_local(self):
        tx = normalizar_registro({"referencia": "b", "monto": "Q 2.100,50", "divisa": "quetzales",
                                  "estado": "Aprobado", "fecha_operacion": "18-10-2026"}, REGLAS)
        self.assertEqual(tx.monto, Decimal("2100.50"))
        self.assertEqual(tx.moneda, "GTQ")

    def test_epoch_y_codigo_estado(self):
        tx = normalizar_registro({"ticket": "c", "total": "45.90", "moneda": "$",
                                  "codigo_respuesta": "05", "timestamp": "1791488400"}, REGLAS)
        self.assertEqual(tx.estado, "RECHAZADA")
        self.assertEqual(tx.fecha.strftime("%Y-%m-%d %H:%M"), "2026-10-08 13:40")


class TestValidacion(unittest.TestCase):
    def test_archivo_valido_sin_errores(self):
        r = procesar(BASE / "data" / "datos_validos.json", REGLAS)
        self.assertEqual(r.total_invalidas, 0, [t.errores for t in r.invalidas])

    def test_cada_caso_inconsistente_detecta_su_error(self):
        r = procesar(BASE / "data" / "datos_inconsistentes.json", REGLAS)
        for tx in r.invalidas:
            caso = tx.original.get("caso", "") if isinstance(tx.original, dict) else ""
            esperado = caso.split(" ")[0]
            if esperado:
                self.assertIn(esperado, tx.errores, f"{caso} -> {tx.errores}")
        # Solo el registro 'original válido' debe pasar
        self.assertEqual([t.id for t in r.validas], ["POS-7010"])

    def test_metricas(self):
        r = procesar(BASE / "data" / "datos_validos.json", REGLAS)
        m = calcular_metricas(r)
        self.assertEqual(m["total_procesadas"], 12)
        self.assertEqual(m["totales_por_moneda"]["USD"]["por_estado"]["APROBADA"],
                         Decimal("25.99") + Decimal("1250.75") + Decimal("12.50")
                         + Decimal("45.90") + Decimal("8.75"))


if __name__ == "__main__":
    unittest.main()
