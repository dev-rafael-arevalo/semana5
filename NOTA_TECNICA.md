# Nota técnica — Normalización de transacciones multifuente

**Rafael Edgardo Arévalo** · AI for Developers Jr. · Kodigo El Salvador · Noviembre 2026

## 1. Decisiones de diseño

**Esquema normalizado.** Cada transacción queda con `id, fuente, fecha, monto, moneda, estado,
cliente, descripcion`, más `valida` y `errores`. Se conserva el registro `original` para que
cualquier transformación pueda auditarse desde la interfaz.

- **Monto:** `Decimal` con 2 decimales (redondeo *half-up*), siempre en unidades de la moneda,
  nunca en centavos. Se evita `float` para no tener errores de redondeo en sumas.
- **Fecha:** se convierte a la zona de El Salvador (UTC-6). Si una fecha llega sin zona, se asume
  hora local.
- **Estado:** cuatro estados de negocio (APROBADA, PENDIENTE, RECHAZADA, REEMBOLSADA) a los que
  se mapean los valores de cada fuente.
- **Moneda:** código ISO-4217; alias como `$`, `Dólares` o `Q` se traducen a su código.

**Reglas fuera del código.** Todas las reglas (mapeo de campos por fuente, monedas, alias,
estados, formatos de fecha y criterios de validez) están en `config/reglas.json`. Agregar una
fuente nueva o un estado nuevo no requiere modificar el código.

**Separación normalizar / validar.** El normalizador nunca descarta: si no puede interpretar un
valor, deja `None` y una nota. El validador decide la validez y diferencia entre un campo
*faltante* y uno *inválido* (por ejemplo, `MONTO_FALTANTE` y `MONTO_INVALIDO`).

**Criterios de validez.** Campos obligatorios presentes e interpretables, monto entre 0.01 y
50,000, moneda soportada, fecha no futura y posterior a 2020-01-01, y sin duplicados
(misma fuente + id: se conserva la primera aparición).

**Política para inválidas:** `separar` (configurable a `marcar` o `descartar`).

**Métricas.** Los totales por moneda solo suman transacciones válidas y se desglosan por estado,
porque sumar una venta aprobada con una rechazada daría una cifra engañosa. Se agrega un *neto*
(aprobadas − reembolsadas). No se convierte entre monedas para no inventar tipos de cambio.

**Interfaces.** La CLI (solo librería estándar) y la web (Flask) usan los mismos módulos de
normalización, validación, métricas y filtros; solo cambia la capa de presentación.

## 2. Uso de IA

Se usó Claude (asistente de código) para proponer la estructura de módulos, escribir la lógica
de parsing de montos y fechas, construir la CLI y la interfaz web en Flask, y generar los datos de
prueba y las pruebas unitarias. La IA también propuso una primera versión de las reglas en
`config/reglas.json`; el esquema, las reglas y los criterios de descarte finales los revisé y
aprobé yo (sección 3).

## 3. Ajustes y decisiones sobre las sugerencias de IA

**Ajustes de código detectados durante el desarrollo:**

- Las pruebas automáticas mostraron que un registro con `"amount_cents": null` se clasificaba
  como `FUENTE_DESCONOCIDA`, porque la detección exigía que el campo tuviera valor. Se cambió
  para que la detección dependa de que la *clave exista*, y así el error correcto es
  `MONTO_FALTANTE`.
- Los códigos de error se generaban automáticamente (`FECHA_INVALIDO`, con error de
  concordancia). Se reemplazaron por una tabla explícita de códigos por campo.
- Para la web se consideró Streamlit, pero se descartó porque depende de librerías compiladas que
  no garantizan soporte para Python 3.15. Se usó Flask, que es Python puro.
- Al revisar las capturas de pantalla se corrigió la alineación del encabezado "Monto" en la CLI.

**Decisiones sobre las reglas propuestas.** Revisé cada criterio y decidí mantenerlos:

- **Monto máximo de 50,000:** cubre con margen las operaciones normales de las tres fuentes. Un
  monto mayor es atípico y conviene revisarlo aparte antes de contarlo en los totales.
- **Rechazar BTC y colones (SVC):** el colón ya no circula desde la dolarización de 2001, y BTC
  tiene un valor muy volátil que obligaría a manejar tipos de cambio, algo que el sistema evita a
  propósito. Se reportan como `MONEDA_NO_SOPORTADA` en lugar de ignorarlas.
- **Política `separar`:** no se pierde información y las inválidas quedan disponibles, con su
  motivo, para corregirlas en la fuente.
- **Fechas futuras, fecha mínima 2020 y duplicados:** las mantuve. Una fecha futura o muy antigua
  indica casi siempre un error de captura, y conservar la primera aparición de un duplicado evita
  contar dos veces el mismo pago.
