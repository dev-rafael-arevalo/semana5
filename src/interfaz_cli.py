"""Interfaz de línea de comandos interactiva (menús, filtros, paginación, detalle, exportación)."""
import csv
import json
import os
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .filtros import Filtros, aplicar
from .metricas import calcular_metricas
from .modelo import ESTADOS_VALIDOS, Transaccion
from .procesador import Resultado, procesar

POR_PAGINA = 10
CARPETA_SALIDA = Path(__file__).resolve().parent.parent / "salida"

# --------------------------------------------------------------- estilo
if os.name == "nt":
    os.system("")  # habilita colores ANSI en la consola de Windows
_COLOR = not os.environ.get("NO_COLOR")


def _c(texto: str, codigo: str) -> str:
    return f"\033[{codigo}m{texto}\033[0m" if _COLOR else texto


def verde(t): return _c(t, "32")
def rojo(t): return _c(t, "31")
def amarillo(t): return _c(t, "33")
def negrita(t): return _c(t, "1")
def tenue(t): return _c(t, "2")


def titulo(texto: str) -> None:
    print("\n" + negrita(texto))
    print("=" * len(texto))


def pausa() -> None:
    input(tenue("\nPresiona Enter para continuar..."))


def pedir(mensaje: str) -> str:
    return input(f"{mensaje}: ").strip()


def elegir(mensaje: str, opciones: list[str]) -> str | None:
    """Muestra opciones numeradas. Enter vacío = sin valor (quitar filtro)."""
    for i, op in enumerate(opciones, 1):
        print(f"  {i}. {op}")
    valor = pedir(f"{mensaje} (número, Enter = ninguno)")
    if not valor:
        return None
    if valor.isdigit() and 1 <= int(valor) <= len(opciones):
        return opciones[int(valor) - 1]
    print(rojo("Opción no válida, se deja sin valor."))
    return None


# --------------------------------------------------------------- tablas
COLUMNAS = [("ID", 12), ("Fuente", 13), ("Fecha", 16), ("Monto", 14), ("Mon", 4),
            ("Estado", 11), ("Cliente", 22)]


def _fila(tx: Transaccion) -> list[str]:
    return [
        tx.id or "—",
        tx.fuente,
        tx.fecha.strftime("%Y-%m-%d %H:%M") if tx.fecha else "—",
        f"{tx.monto:,.2f}" if tx.monto is not None else "—",
        tx.moneda or "—",
        tx.estado or "—",
        tx.cliente or "—",
    ]


def _recortar(texto: str, ancho: int) -> str:
    return texto if len(texto) <= ancho else texto[: ancho - 1] + "…"


def imprimir_tabla(transacciones: list[Transaccion], desde: int = 0) -> None:
    encabezado = "  #  " + " ".join(n.rjust(a) if n == "Monto" else n.ljust(a) for n, a in COLUMNAS)
    print(negrita(encabezado))
    print("-" * len(encabezado))
    for i, tx in enumerate(transacciones, desde + 1):
        celdas = []
        for (nombre, ancho), valor in zip(COLUMNAS, _fila(tx)):
            valor = _recortar(valor, ancho)
            celdas.append(valor.rjust(ancho) if nombre == "Monto" else valor.ljust(ancho))
        linea = f"{i:>3}  " + " ".join(celdas)
        print(linea if tx.valida else rojo(linea))
        if not tx.valida:
            print(rojo(f"       ↳ {', '.join(tx.errores)}"))


def paginar(transacciones: list[Transaccion], encabezado: str) -> None:
    if not transacciones:
        print(amarillo("\nNo hay transacciones para mostrar con los criterios actuales."))
        pausa()
        return
    pagina = 0
    paginas = (len(transacciones) - 1) // POR_PAGINA + 1
    while True:
        titulo(f"{encabezado} — {len(transacciones)} registros (página {pagina + 1}/{paginas})")
        inicio = pagina * POR_PAGINA
        imprimir_tabla(transacciones[inicio:inicio + POR_PAGINA], inicio)
        accion = pedir("\n[s]iguiente  [a]nterior  [d]etalle #  [v]olver").lower()
        if accion == "s" and pagina < paginas - 1:
            pagina += 1
        elif accion == "a" and pagina > 0:
            pagina -= 1
        elif accion.startswith("d"):
            numero = accion[1:].strip() or pedir("Número de fila")
            if numero.isdigit() and 1 <= int(numero) <= len(transacciones):
                mostrar_detalle(transacciones[int(numero) - 1])
            else:
                print(rojo("Número de fila no válido."))
        elif accion in ("v", "q", ""):
            return


# --------------------------------------------------------------- vistas
def mostrar_metricas(resultado: Resultado) -> None:
    m = calcular_metricas(resultado)
    titulo("Métricas generales")
    print(f"  Total procesadas : {m['total_procesadas']}")
    print(f"  Válidas          : {verde(str(m['validas']))} ({m['porcentaje_validas']:.1f} %)")
    print(f"  Inválidas        : {rojo(str(m['invalidas']))} (política: {resultado.politica})")

    titulo("Conteo por estado (válidas)")
    for estado in ESTADOS_VALIDOS:
        cantidad = m["por_estado"].get(estado, 0)
        print(f"  {estado:<12} {cantidad:>4}  {'█' * cantidad}")

    titulo("Totales por moneda (válidas)")
    print(negrita(f"  {'Mon':<5}{'Aprobada':>13}{'Pendiente':>13}{'Rechazada':>13}"
                  f"{'Reembolsada':>13}{'Neto*':>13}"))
    for moneda, datos in m["totales_por_moneda"].items():
        celdas = "".join(f"{datos['por_estado'].get(e, Decimal(0)):>13,.2f}" for e in ESTADOS_VALIDOS)
        print(f"  {moneda:<5}{celdas}{datos['neto']:>13,.2f}")
    print(tenue("  * Neto = aprobadas − reembolsadas"))

    titulo("Por fuente")
    for fuente, datos in m["por_fuente"].items():
        print(f"  {fuente:<14} válidas: {datos['validas']:>3}   inválidas: {datos['invalidas']:>3}")

    if m["errores_frecuentes"]:
        titulo("Motivos de invalidez")
        for error, cantidad in m["errores_frecuentes"].items():
            print(f"  {error:<26} {cantidad:>3}")
    pausa()


def mostrar_detalle(tx: Transaccion) -> None:
    titulo(f"Detalle de transacción {tx.id or '(sin id)'}")
    estado = verde("VÁLIDA") if tx.valida else rojo("INVÁLIDA")
    print(f"  Resultado: {estado}")
    if tx.errores:
        print(rojo(f"  Errores  : {', '.join(tx.errores)}"))
    if tx.notas:
        print(amarillo(f"  Notas    : {'; '.join(tx.notas)}"))
    print(negrita("\n  Registro original:"))
    print("  " + json.dumps(tx.original, ensure_ascii=False, indent=2).replace("\n", "\n  "))
    print(negrita("\n  Registro normalizado:"))
    normalizado = tx.a_dict()
    del normalizado["errores"]
    print("  " + json.dumps(normalizado, ensure_ascii=False, indent=2).replace("\n", "\n  "))
    pausa()


def buscar_por_id(resultado: Resultado) -> None:
    buscado = pedir("ID de la transacción")
    encontradas = [tx for tx in resultado.validas + resultado.invalidas
                   if tx.id and tx.id.lower() == buscado.lower()]
    if not encontradas:
        print(amarillo("No se encontró ninguna transacción con ese ID."))
        pausa()
    for tx in encontradas:
        mostrar_detalle(tx)


def _leer_fecha(mensaje: str) -> date | None:
    valor = pedir(f"{mensaje} (AAAA-MM-DD, Enter = ninguna)")
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        print(rojo("Fecha no válida, se deja sin valor."))
        return None


def _leer_monto(mensaje: str) -> Decimal | None:
    valor = pedir(f"{mensaje} (Enter = ninguno)")
    if not valor:
        return None
    try:
        return Decimal(valor.replace(",", ""))
    except InvalidOperation:
        print(rojo("Monto no válido, se deja sin valor."))
        return None


def menu_filtros(filtros: Filtros, resultado: Resultado, reglas: dict) -> None:
    todas = resultado.visibles
    while True:
        titulo("Configurar filtros")
        activos = filtros.activos()
        print("  Activos: " + (", ".join(f"{k}={v}" for k, v in activos.items()) or tenue("ninguno")))
        print(f"  Orden  : {filtros.ordenar_por} ({'desc' if filtros.descendente else 'asc'})")
        print(f"  Coinciden: {len(aplicar(todas, filtros))} de {len(todas)}\n")
        print("  1. Fuente        5. Rango de montos")
        print("  2. Estado        6. Buscar texto (id / cliente / descripción)")
        print("  3. Moneda        7. Ordenamiento")
        print("  4. Rango fechas  8. Limpiar todos")
        print("  0. Volver")
        op = pedir("\nOpción")
        if op == "1":
            filtros.fuente = elegir("Fuente", list(reglas["fuentes"]))
        elif op == "2":
            filtros.estado = elegir("Estado", list(ESTADOS_VALIDOS))
        elif op == "3":
            filtros.moneda = elegir("Moneda", reglas["monedas_soportadas"])
        elif op == "4":
            filtros.fecha_desde = _leer_fecha("Desde")
            filtros.fecha_hasta = _leer_fecha("Hasta")
        elif op == "5":
            filtros.monto_min = _leer_monto("Monto mínimo")
            filtros.monto_max = _leer_monto("Monto máximo")
        elif op == "6":
            filtros.texto = pedir("Texto a buscar (Enter = ninguno)") or None
        elif op == "7":
            filtros.ordenar_por = elegir("Ordenar por", ["fecha", "monto", "id"]) or "fecha"
            filtros.descendente = pedir("¿Descendente? (s/n)").lower() == "s"
        elif op == "8":
            filtros.__init__()
        elif op == "0":
            return


def exportar(resultado: Resultado) -> None:
    titulo("Exportar resultados")
    print("  1. JSON (válidas + inválidas + métricas)")
    print("  2. CSV  (una fila por transacción)")
    op = pedir("Formato")
    CARPETA_SALIDA.mkdir(exist_ok=True)
    todas = resultado.validas + resultado.invalidas
    if op == "1":
        ruta = CARPETA_SALIDA / "transacciones_normalizadas.json"
        datos = {
            "validas": [tx.a_dict() for tx in resultado.validas],
            "invalidas": [tx.a_dict(incluir_original=True) for tx in resultado.invalidas],
            "metricas": calcular_metricas(resultado),
        }
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
    elif op == "2":
        ruta = CARPETA_SALIDA / "transacciones_normalizadas.csv"
        with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
            columnas = list(todas[0].a_dict()) if todas else ["id"]
            escritor = csv.DictWriter(f, fieldnames=columnas)
            escritor.writeheader()
            for tx in todas:
                fila = tx.a_dict()
                fila["errores"] = "|".join(fila["errores"])
                escritor.writerow(fila)
    else:
        print(rojo("Formato no válido."))
        pausa()
        return
    print(verde(f"Archivo generado: {ruta}"))
    pausa()


def mostrar_reglas(reglas: dict) -> None:
    titulo("Reglas activas (config/reglas.json)")
    print(f"  Monedas soportadas : {', '.join(reglas['monedas_soportadas'])}")
    print(f"  Zona horaria       : {reglas['zona_horaria']['nombre']} "
          f"(UTC{reglas['zona_horaria']['offset_horas']:+d})")
    print(f"  Formatos de fecha  : {len(reglas['formatos_fecha'])} + epoch={reglas.get('aceptar_epoch')}")
    print(negrita("\n  Mapeo de estados:"))
    for estado, valores in reglas["mapeo_estados"].items():
        print(f"    {estado:<12} ← {', '.join(valores)}")
    print(negrita("\n  Fuentes:"))
    for nombre, d in reglas["fuentes"].items():
        print(f"    {nombre:<13} detecta por {d['detectar_por']}, monto en '{d['formato_monto']}'")
    v = reglas["validacion"]
    print(negrita("\n  Validación:"))
    print(f"    Obligatorios: {', '.join(v['campos_obligatorios'])}")
    print(f"    Monto entre {v['monto_minimo']} y {v['monto_maximo']}; "
          f"fecha ≥ {v['fecha_minima']}; futuras permitidas: {v['permitir_fecha_futura']}")
    print(f"    Política para inválidas: {reglas['politica_invalidas']['accion']}")
    pausa()


# --------------------------------------------------------------- bucle
def ejecutar(ruta_inicial: Path, reglas: dict) -> None:
    resultado = procesar(ruta_inicial, reglas)
    filtros = Filtros()

    while True:
        titulo("Explorador de transacciones multifuente")
        print(f"  Archivo : {resultado.archivo}")
        print(f"  Cargadas: {resultado.total_procesadas}  |  "
              f"{verde(str(len(resultado.validas)) + ' válidas')}  |  "
              f"{rojo(str(resultado.total_invalidas) + ' inválidas')}  |  política: {resultado.politica}")
        if filtros.activos():
            print(amarillo(f"  Filtros activos: {filtros.activos()}"))
        print("""
  1. Ver métricas
  2. Listar transacciones (con filtros)
  3. Ver transacciones inválidas y sus motivos
  4. Configurar filtros
  5. Buscar transacción por ID (original vs normalizada)
  6. Exportar resultados (JSON / CSV)
  7. Ver reglas activas
  8. Cargar otro archivo
  0. Salir""")
        op = pedir("\nOpción")
        if op == "1":
            mostrar_metricas(resultado)
        elif op == "2":
            paginar(aplicar(resultado.visibles, filtros), "Transacciones")
        elif op == "3":
            if resultado.politica == "descartar":
                print(amarillo(f"Política 'descartar': {resultado.total_invalidas} inválidas "
                               "fueron eliminadas (solo se cuentan en métricas)."))
                pausa()
            else:
                paginar(resultado.invalidas, "Transacciones inválidas")
        elif op == "4":
            menu_filtros(filtros, resultado, reglas)
        elif op == "5":
            buscar_por_id(resultado)
        elif op == "6":
            exportar(resultado)
        elif op == "7":
            mostrar_reglas(reglas)
        elif op == "8":
            ruta = pedir("Ruta del archivo JSON")
            try:
                resultado = procesar(Path(ruta), reglas)
                filtros = Filtros()
                print(verde("Archivo cargado."))
            except (OSError, ValueError) as e:
                print(rojo(f"No se pudo cargar: {e}"))
            pausa()
        elif op == "0":
            print("¡Hasta luego!")
            return
