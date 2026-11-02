"""Interfaz web (Flask). Reutiliza los mismos módulos que la CLI:
normalizador, validador, procesador, métricas y filtros. Aquí solo hay presentación."""
import csv
import io
import json
import os
import tempfile
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for

from .filtros import Filtros, aplicar
from .metricas import calcular_metricas
from .modelo import ESTADOS_VALIDOS
from .procesador import procesar

POR_PAGINA = 15


def _fecha(valor: str | None) -> date | None:
    try:
        return date.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def _monto(valor: str | None) -> Decimal | None:
    try:
        return Decimal(valor.replace(",", "")) if valor else None
    except InvalidOperation:
        return None


def filtros_desde_request(args) -> Filtros:
    return Filtros(
        fuente=args.get("fuente") or None,
        estado=args.get("estado") or None,
        moneda=args.get("moneda") or None,
        fecha_desde=_fecha(args.get("fecha_desde")),
        fecha_hasta=_fecha(args.get("fecha_hasta")),
        monto_min=_monto(args.get("monto_min")),
        monto_max=_monto(args.get("monto_max")),
        texto=args.get("texto") or None,
        ordenar_por=args.get("ordenar_por") if args.get("ordenar_por") in ("fecha", "monto", "id") else "fecha",
        descendente=args.get("orden") == "desc",
    )


def crear_app(ruta_inicial: Path, reglas: dict) -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = os.urandom(24)  # solo firma los mensajes flash; se regenera en cada arranque
    # Estado de la sesión: es una app local de un solo usuario
    estado = {"resultado": procesar(ruta_inicial, reglas), "nombre": ruta_inicial.name}

    @app.context_processor
    def globales():
        r = estado["resultado"]
        return {"resultado": r, "nombre_archivo": estado["nombre"], "reglas": reglas,
                "estados": ESTADOS_VALIDOS}

    @app.template_filter("dinero")
    def dinero(valor):
        return "—" if valor is None else f"{valor:,.2f}"

    @app.route("/")
    def inicio():
        m = calcular_metricas(estado["resultado"])
        maximo_estado = max(m["por_estado"].values(), default=1)
        return render_template("metricas.html", m=m, maximo_estado=maximo_estado)

    def _pagina_listado(transacciones, titulo, plantilla_vacia):
        filtros = filtros_desde_request(request.args)
        filtradas = aplicar(transacciones, filtros)
        total_paginas = max(1, (len(filtradas) - 1) // POR_PAGINA + 1)
        pagina = min(max(request.args.get("pagina", 1, type=int), 1), total_paginas)
        inicio_idx = (pagina - 1) * POR_PAGINA
        args_sin_pagina = {k: v for k, v in request.args.items() if k != "pagina"}
        r = estado["resultado"]
        indice_de = {id(tx): i for i, tx in enumerate(r.validas + r.invalidas)}
        return render_template(
            "listado.html", titulo=titulo,
            filas=[(indice_de[id(tx)], tx) for tx in filtradas[inicio_idx:inicio_idx + POR_PAGINA]],
            total=len(filtradas), total_sin_filtro=len(transacciones), filtros=filtros,
            pagina=pagina, total_paginas=total_paginas, args=args_sin_pagina,
            vacio=plantilla_vacia, endpoint=request.endpoint)

    @app.route("/transacciones")
    def transacciones():
        return _pagina_listado(estado["resultado"].visibles, "Transacciones",
                               "No hay transacciones que coincidan con los filtros.")

    @app.route("/invalidas")
    def invalidas():
        r = estado["resultado"]
        if r.politica == "descartar":
            flash(f"Política 'descartar': {r.total_invalidas} inválidas fueron eliminadas "
                  "(solo se cuentan en las métricas).")
        return _pagina_listado(r.invalidas, "Transacciones inválidas", "No hay transacciones inválidas.")

    @app.route("/transaccion/<int:indice>")
    def detalle(indice: int):
        r = estado["resultado"]
        todas = r.validas + r.invalidas
        if not 0 <= indice < len(todas):
            abort(404)
        tx = todas[indice]
        normalizado = tx.a_dict()
        normalizado.pop("errores")
        return render_template(
            "detalle.html", tx=tx,
            original=json.dumps(tx.original, ensure_ascii=False, indent=2),
            normalizado=json.dumps(normalizado, ensure_ascii=False, indent=2))

    @app.route("/buscar")
    def buscar():
        buscado = request.args.get("id", "").strip().lower()
        r = estado["resultado"]
        for i, tx in enumerate(r.validas + r.invalidas):
            if tx.id and tx.id.lower() == buscado:
                return redirect(url_for("detalle", indice=i))
        flash(f"No se encontró ninguna transacción con ID '{request.args.get('id', '')}'.")
        return redirect(request.referrer or url_for("inicio"))

    @app.route("/reglas")
    def ver_reglas():
        return render_template("reglas.html")

    @app.route("/cargar", methods=["POST"])
    def cargar():
        archivo = request.files.get("archivo")
        if not archivo or not archivo.filename:
            flash("Selecciona un archivo JSON.")
            return redirect(url_for("inicio"))
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "subido.json"
            archivo.save(ruta)
            try:
                estado["resultado"] = procesar(ruta, reglas)
                estado["nombre"] = archivo.filename
                flash(f"Archivo '{archivo.filename}' cargado.")
            except (OSError, ValueError) as e:  # json.JSONDecodeError es ValueError
                flash(f"No se pudo cargar '{archivo.filename}': {e}")
        return redirect(url_for("inicio"))

    @app.route("/exportar/<formato>")
    def exportar(formato: str):
        r = estado["resultado"]
        if formato == "json":
            datos = {
                "validas": [tx.a_dict() for tx in r.validas],
                "invalidas": [tx.a_dict(incluir_original=True) for tx in r.invalidas],
                "metricas": calcular_metricas(r),
            }
            contenido = json.dumps(datos, ensure_ascii=False, indent=2, default=str)
            tipo = "application/json"
        elif formato == "csv":
            salida = io.StringIO()
            filas = [tx.a_dict() for tx in r.validas + r.invalidas]
            escritor = csv.DictWriter(salida, fieldnames=list(filas[0]) if filas else ["id"])
            escritor.writeheader()
            for fila in filas:
                fila["errores"] = "|".join(fila["errores"])
                escritor.writerow(fila)
            contenido = "﻿" + salida.getvalue()  # BOM para que Excel respete los acentos
            tipo = "text/csv; charset=utf-8"
        else:
            abort(404)
        return Response(contenido, mimetype=tipo, headers={
            "Content-Disposition": f"attachment; filename=transacciones_normalizadas.{formato}"})

    return app
