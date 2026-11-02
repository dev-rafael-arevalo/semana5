# Nota técnica — Normalización de transacciones multifuente

> ⚠️ BORRADOR: revisar y reescribir con tus propias palabras. Las secciones marcadas
> con **[COMPLETAR]** deben reflejar TUS decisiones y TUS ajustes reales.

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

**Política para inválidas:** `separar` (configurable a `marcar` o `descartar`). Se eligió separar
para no perder información: se pueden revisar con sus motivos y exportar.

**Métricas.** Los totales por moneda solo suman transacciones válidas y se desglosan por estado,
porque sumar una venta aprobada con una rechazada daría una cifra engañosa. Se agrega un *neto*
(aprobadas − reembolsadas). No se convierte entre monedas para no inventar tipos de cambio.

**Interfaces.** La CLI (solo librería estándar) y la web (Flask) usan los mismos módulos de
normalización, validación, métricas y filtros; solo cambia la capa de presentación. Se eligió Flask
en lugar de Streamlit porque es Python puro y no depende de librerías compiladas.

## 2. Uso de IA

Se usó Claude (asistente de código) para: proponer la estructura de módulos, escribir la lógica
de parsing de montos y fechas, construir la CLI (menús, paginación, tablas) y la interfaz web en Flask, y generar los datos
de prueba y las pruebas unitarias.

## 3. Ajustes realizados sobre las sugerencias de IA

- Las pruebas automáticas mostraron que un registro con `"amount_cents": null` se clasificaba
  como `FUENTE_DESCONOCIDA`, porque la detección exigía que el campo tuviera valor. Se cambió
  para que la detección dependa de que la *clave exista*, y así el error correcto es
  `MONTO_FALTANTE`.
- Los códigos de error se generaban automáticamente (`FECHA_INVALIDO`, con error de
  concordancia). Se reemplazaron por una tabla explícita de códigos por campo.
- **[COMPLETAR]** Ajustes propios: por ejemplo, cambiaste el monto máximo, agregaste o quitaste
  monedas, cambiaste la política de inválidas, rechazaste alguna sugerencia y por qué.
- **[COMPLETAR]** Decisiones que tomaste tú y que la IA no debía decidir (esquema, reglas y
  criterios de descarte): explica brevemente tu razonamiento.
