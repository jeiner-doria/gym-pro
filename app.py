import os
from datetime import datetime, date
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, abort)

import database as db
import validaciones as v

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cambia-esta-clave-en-produccion')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')

# Módulo -> (endpoint, roles permitidos)
MODULOS = [
    ('Inicio', 'inicio', ['Administrador', 'Empleado', 'Entrenador']),
    ('Clientes', 'clientes', ['Administrador', 'Empleado', 'Entrenador']),
    ('Empleados', 'empleados', ['Administrador']),
    ('Entrenadores', 'entrenadores', ['Administrador', 'Entrenador']),
    ('Membresías y pagos', 'membresias', ['Administrador', 'Empleado']),
    ('Accesos', 'accesos', ['Administrador', 'Empleado']),
    ('Máquinas', 'maquinas', ['Administrador', 'Empleado']),
    ('Rutinas', 'rutinas', ['Administrador', 'Empleado', 'Entrenador']),
    ('Clases', 'clases', ['Administrador', 'Empleado', 'Entrenador']),
    ('Reportes', 'reportes', ['Administrador']),
]
ROLES = {endpoint: roles for _, endpoint, roles in MODULOS}


# ------------------------------------------------------------------ utilidades
def requiere(endpoint):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **k):
            if 'tipo' not in session:
                return redirect(url_for('login'))
            if session['tipo'] not in ROLES[endpoint]:
                abort(403)
            return f(*a, **k)
        return wrapper
    return deco


def primer_error(*resultados):
    for ok, msg in resultados:
        if not ok:
            return msg
    return None


def avisar(ok, msg):
    flash(msg, 'ok' if ok else 'error')


@app.context_processor
def inyectar():
    menu = []
    if 'tipo' in session:
        menu = [(t, e) for t, e, r in MODULOS if session['tipo'] in r]
    return dict(menu=menu, usuario=session.get('usuario'), tipo=session.get('tipo'),
                planes=db.PLANES_MEMBRESIA, pago_clase=db.PAGO_POR_CLASE,
                hoy=date.today().isoformat(), roles_info=list(ROLES), mes_actual=date.today().strftime('%Y-%m'))


@app.template_filter('dinero')
def dinero(valor):
    try:
        return '${:,.0f}'.format(float(valor)).replace(',', '.')
    except (TypeError, ValueError):
        return valor


@app.errorhandler(403)
def prohibido(_):
    return render_template('error.html', codigo=403,
                           mensaje='Tu rol no tiene acceso a este módulo.'), 403


@app.errorhandler(404)
def no_encontrado(_):
    return render_template('error.html', codigo=404, mensaje='Página no encontrada.'), 404


@app.route('/salud')
def salud():
    return 'ok'


# ------------------------------------------------------------------ sesión (RF25)
@app.route('/', methods=['GET'])
def raiz():
    return redirect(url_for('inicio' if 'tipo' in session else 'login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        clave = request.form.get('contrasena', '').strip()
        if not usuario or not clave:
            flash('Escribe usuario y contraseña.', 'error')
        else:
            tipo = db.validar_usuario(usuario, clave)
            if tipo:
                session.clear()
                session['usuario'], session['tipo'] = usuario, tipo
                return redirect(url_for('inicio'))
            flash('Usuario o contraseña incorrectos.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/inicio')
@requiere('inicio')
def inicio():
    db.actualizar_estados_membresia()
    return render_template('inicio.html', r=db.reporte_general())


# ------------------------------------------------------------------ clientes RF01-04
@app.route('/clientes', methods=['GET', 'POST'])
@requiere('clientes')
def clientes():
    seccion = request.args.get('s', 'registrar')
    ci = request.values.get('ci', '').strip()
    form = request.form
    if request.method == 'POST':
        accion = form.get('accion')
        if accion == 'registrar':
            err = primer_error(
                v.texto(form.get('nombre', ''), 'Nombre'),
                v.numeros(form.get('identificacion', ''), 'Identificación'),
                v.numeros(form.get('telefono', ''), 'Teléfono'),
                v.correo(form.get('correo', '')),
                v.fecha(form.get('fecha', ''), 'Fecha de nacimiento'))
            if err:
                avisar(False, err)
            else:
                ok, msg = db.insertar_cliente(form['identificacion'].strip(), form['nombre'].strip(),
                                              form['telefono'].strip(), form['correo'].strip(),
                                              form['fecha'].strip())
                avisar(ok, msg)
                if ok:
                    return redirect(url_for('clientes', s='listado'))
        elif accion == 'modificar':
            seccion = 'buscar'
            err = primer_error(
                v.texto(form.get('nombre', ''), 'Nombre'),
                v.numeros(form.get('telefono', ''), 'Teléfono'),
                v.correo(form.get('correo', '')),
                v.fecha(form.get('fecha', ''), 'Fecha de nacimiento'))
            if err:
                avisar(False, err)
            else:
                ok, msg = db.actualizar_cliente(ci, form['nombre'].strip(), form['telefono'].strip(),
                                                form['correo'].strip(), form['fecha'].strip())
                avisar(ok, msg)
                return redirect(url_for('clientes', s='buscar', ci=ci))
        elif accion == 'eliminar':
            ok, msg = db.eliminar_cliente(ci)
            avisar(ok, msg)
            return redirect(url_for('clientes', s='buscar'))
    cliente = None
    if seccion == 'buscar' and ci:
        err = v.numeros(ci, 'Identificación')
        if not err[0]:
            avisar(False, err[1])
        else:
            cliente = db.buscar_cliente(ci)
            if not cliente:
                avisar(False, 'Cliente no encontrado.')
    return render_template('clientes.html', s=seccion, form=form, ci=ci, cliente=cliente,
                           lista=db.todos_clientes() if seccion == 'listado' else [])


# ------------------------------------------------------------------ empleados RF05-06
@app.route('/empleados', methods=['GET', 'POST'])
@requiere('empleados')
def empleados():
    seccion = request.args.get('s', 'registrar')
    ci = request.values.get('ci', '').strip()
    form = request.form
    if request.method == 'POST':
        accion = form.get('accion')
        if accion == 'registrar':
            err = primer_error(
                v.numeros(form.get('identificacion', ''), 'Identificación'),
                v.texto(form.get('nombre', ''), 'Nombre'),
                v.numeros(form.get('telefono', ''), 'Teléfono'),
                v.texto(form.get('cargo', ''), 'Cargo'))
            if err:
                avisar(False, err)
            else:
                ok, msg = db.insertar_empleado(form['identificacion'].strip(), form['nombre'].strip(),
                                               form['telefono'].strip(), form['cargo'].strip())
                avisar(ok, msg)
                if ok:
                    return redirect(url_for('empleados', s='listado'))
        elif accion == 'modificar':
            seccion = 'buscar'
            err = primer_error(v.texto(form.get('nombre', ''), 'Nombre'),
                               v.numeros(form.get('telefono', ''), 'Teléfono'),
                               v.texto(form.get('cargo', ''), 'Cargo'))
            if err:
                avisar(False, err)
            else:
                ok, msg = db.actualizar_empleado(ci, form['nombre'].strip(), form['telefono'].strip(),
                                                 form['cargo'].strip())
                avisar(ok, msg)
                return redirect(url_for('empleados', s='buscar', ci=ci))
        elif accion == 'eliminar':
            ok, msg = db.eliminar_empleado(ci)
            avisar(ok, msg)
            return redirect(url_for('empleados', s='buscar'))
    empleado = None
    if seccion == 'buscar' and ci:
        err = v.numeros(ci, 'Identificación')
        if not err[0]:
            avisar(False, err[1])
        else:
            empleado = db.buscar_empleado(ci)
            if not empleado:
                avisar(False, 'Empleado no encontrado.')
    return render_template('empleados.html', s=seccion, form=form, ci=ci, empleado=empleado,
                           lista=db.todos_empleados() if seccion == 'listado' else [])


# ------------------------------------------------------------------ entrenadores RF07, RF37
@app.route('/entrenadores', methods=['GET', 'POST'])
@requiere('entrenadores')
def entrenadores():
    seccion = request.args.get('s', 'registrar')
    ci = request.values.get('ci', '').strip()
    form = request.form
    if request.method == 'POST':
        accion = form.get('accion')
        if accion == 'registrar':
            err = primer_error(v.numeros(form.get('identificacion', ''), 'Identificación'),
                               v.texto(form.get('nombre', ''), 'Nombre'),
                               v.texto(form.get('especialidad', ''), 'Especialidad'))
            if err:
                avisar(False, err)
            else:
                ok, msg = db.insertar_entrenador(form['identificacion'].strip(), form['nombre'].strip(),
                                                 form['especialidad'].strip())
                avisar(ok, msg)
                if ok:
                    return redirect(url_for('entrenadores', s='listado'))
        elif accion == 'modificar':
            seccion = 'buscar'
            err = primer_error(v.texto(form.get('nombre', ''), 'Nombre'),
                               v.texto(form.get('especialidad', ''), 'Especialidad'))
            if err:
                avisar(False, err)
            else:
                ok, msg = db.actualizar_entrenador(ci, form['nombre'].strip(), form['especialidad'].strip())
                avisar(ok, msg)
                return redirect(url_for('entrenadores', s='buscar', ci=ci))
        elif accion == 'eliminar':
            ok, msg = db.eliminar_entrenador(ci)
            avisar(ok, msg)
            return redirect(url_for('entrenadores', s='buscar'))
    entrenador = None
    if seccion == 'buscar' and ci:
        err = v.numeros(ci, 'Identificación')
        if not err[0]:
            avisar(False, err[1])
        else:
            entrenador = db.buscar_entrenador(ci)
            if not entrenador:
                avisar(False, 'Entrenador no encontrado.')
    return render_template('entrenadores.html', s=seccion, form=form, ci=ci, entrenador=entrenador,
                           lista=db.todos_entrenadores() if seccion == 'listado' else [])


# ------------------------------------------------------------------ membresías y pagos RF08-13, RF26-30
@app.route('/membresias', methods=['GET', 'POST'])
@requiere('membresias')
def membresias():
    db.actualizar_estados_membresia()
    seccion = request.args.get('s', 'crear')
    ci = request.values.get('ci', '').strip()
    form = request.form
    if request.method == 'POST':
        accion = form.get('accion')
        if accion == 'crear':
            plan_nombre = form.get('plan', '')
            plan = db.PLANES_MEMBRESIA.get(plan_nombre)
            err = primer_error(v.texto(form.get('nombre', ''), 'Nombre'),
                               v.fecha(form.get('inicio', ''), 'Inicio'),
                               v.fecha(form.get('fin', ''), 'Fin'))
            if not err and not plan:
                err = 'Selecciona un plan válido (Normal, Gold o Platino).'
            if not err and form['fin'].strip() < form['inicio'].strip():
                err = 'La fecha final no puede ser anterior a la fecha inicial.'
            if err:
                avisar(False, err)
            else:
                ok, msg = db.crear_membresia(form['nombre'].strip(), plan_nombre, plan['precio'],
                                             plan['clases'], form['inicio'].strip(), form['fin'].strip())
                avisar(ok, msg)
                if ok:
                    return redirect(url_for('membresias', s='listado'))
        elif accion == 'asignar':
            seccion = 'asignar'
            err = primer_error(v.numeros(form.get('ci', ''), 'Identificación'),
                               v.numeros(form.get('membresia_id', ''), 'ID membresía'),
                               v.fecha(form.get('fecha_pago', ''), 'Fecha de pago'),
                               v.positivo(form.get('valor', ''), 'Valor'),
                               v.texto(form.get('concepto', ''), 'Concepto'))
            if err:
                avisar(False, err)
            else:
                ok, msg = db.asignar_membresia_y_pago(form['ci'].strip(), int(form['membresia_id']),
                                                      form['fecha_pago'].strip(), float(form['valor']),
                                                      form['concepto'].strip())
                avisar(ok, msg)
                if ok:
                    return redirect(url_for('membresias', s='asignar'))
    estado = pagos = None
    if seccion == 'consultar' and ci:
        err = v.numeros(ci, 'Identificación')
        if not err[0]:
            avisar(False, err[1])
        else:
            estado = db.estado_membresia(ci)
            if not estado:
                avisar(False, 'Cliente no encontrado o sin membresía asignada.')
            pagos = db.pagos_cliente(ci)
    return render_template('membresias.html', s=seccion, form=form, ci=ci, estado=estado, pagos=pagos,
                           lista=db.membresias() if seccion in ('listado', 'asignar') else [])


# ------------------------------------------------------------------ accesos RF14-16, RF23, RF49-50
@app.route('/accesos', methods=['GET', 'POST'])
@requiere('accesos')
def accesos():
    seccion = request.args.get('s', 'registro')
    ci = request.values.get('ci', '').strip()
    form = request.form
    if request.method == 'POST':
        accion = form.get('accion')
        err = v.numeros(ci, 'Identificación')
        if not err[0]:
            avisar(False, err[1])
        else:
            if accion in ('ingreso', 'salida'):
                seccion = 'registro'
                ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ok, msg = (db.registrar_ingreso(ci, ahora) if accion == 'ingreso'
                           else db.registrar_salida(ci, ahora))
                avisar(ok, msg)
            elif accion == 'desactivar':
                seccion = 'estado'
                avisar(*db.desactivar_cliente(ci))
            elif accion == 'activar':
                seccion = 'estado'
                avisar(*db.activar_cliente(ci))
            return redirect(url_for('accesos', s=seccion, ci=ci if seccion == 'estado' else None))
    asistencia = estado_cli = None
    if seccion == 'asistencia' and ci:
        err = v.numeros(ci, 'Identificación')
        if not err[0]:
            avisar(False, err[1])
        else:
            asistencia = db.asistencia_cliente(ci)
    if seccion == 'estado' and ci:
        err = v.numeros(ci, 'Identificación')
        if not err[0]:
            avisar(False, err[1])
        else:
            estado_cli = db.estado_cliente(ci)
            if not estado_cli:
                avisar(False, 'Cliente no encontrado.')
    return render_template('accesos.html', s=seccion, ci=ci, asistencia=asistencia, estado_cli=estado_cli,
                           lista=db.todos_clientes() if seccion == 'listado' else [])


# ------------------------------------------------------------------ máquinas RF17-19
@app.route('/maquinas', methods=['GET', 'POST'])
@requiere('maquinas')
def maquinas():
    seccion = request.args.get('s', 'registrar')
    form = request.form
    if request.method == 'POST':
        accion = form.get('accion')
        if accion == 'registrar':
            estado = form.get('estado', 'Disponible')
            err = primer_error(v.texto(form.get('nombre', ''), 'Nombre máquina'),
                               v.texto(form.get('marca', ''), 'Marca'))
            if not err and estado not in ('Disponible', 'Mantenimiento', 'Fuera de servicio'):
                err = 'Estado no válido.'
            if err:
                avisar(False, err)
            else:
                ok, msg = db.registrar_maquina(form['nombre'].strip(), form['marca'].strip(), estado)
                avisar(ok, msg)
                if ok:
                    return redirect(url_for('maquinas', s='mantenimiento'))
        elif accion == 'estado':
            nuevo = form.get('estado', '')
            if nuevo not in ('Disponible', 'Mantenimiento', 'Fuera de servicio'):
                avisar(False, 'Estado no válido.')
            else:
                avisar(*db.cambiar_estado_maquina(form.get('id', ''), nuevo))
            return redirect(url_for('maquinas', s='mantenimiento'))
    return render_template('maquinas.html', s=seccion, form=form, lista=db.maquinas())


# ------------------------------------------------------------------ rutinas RF20-22
@app.route('/rutinas', methods=['GET', 'POST'])
@requiere('rutinas')
def rutinas():
    seccion = request.args.get('s', 'registrar')
    ci = request.values.get('ci', '').strip()
    form = request.form
    if request.method == 'POST':
        accion = form.get('accion')
        if accion == 'registrar':
            err = primer_error(v.numeros(form.get('ci', ''), 'Identificación'),
                               v.texto(form.get('nombre', ''), 'Nombre rutina'),
                               v.texto(form.get('descripcion', ''), 'Descripción'),
                               v.fecha(form.get('fecha', ''), 'Fecha'))
            if err:
                avisar(False, err)
            else:
                ok, msg = db.registrar_rutina(form['ci'].strip(), form['nombre'].strip(),
                                              form['descripcion'].strip(), form['fecha'].strip())
                avisar(ok, msg)
                if ok:
                    return redirect(url_for('rutinas', s='listado'))
        elif accion == 'asignar':
            seccion = 'asignar'
            err = primer_error(v.numeros(form.get('ci', ''), 'Identificación cliente'),
                               v.numeros(form.get('entrenador_id', ''), 'ID entrenador'))
            if err:
                avisar(False, err)
            else:
                ok, msg = db.asignar_entrenador(form['ci'].strip(), int(form['entrenador_id']))
                avisar(ok, msg)
                if ok:
                    return redirect(url_for('rutinas', s='asignar'))
    mis = None
    if seccion == 'consultar' and ci:
        err = v.numeros(ci, 'Identificación')
        if not err[0]:
            avisar(False, err[1])
        else:
            mis = db.rutinas_cliente(ci)
            if not mis:
                avisar(False, 'El cliente no tiene rutinas registradas.')
    return render_template('rutinas.html', s=seccion, form=form, ci=ci, mis=mis,
                           entrenadores=db.todos_entrenadores() if seccion == 'asignar' else [],
                           lista=db.rutinas() if seccion == 'listado' else [])


# ------------------------------------------------------------------ clases RF29-36, RF39-43
@app.route('/clases', methods=['GET', 'POST'])
@requiere('clases')
def clases():
    seccion = request.args.get('s', 'registrar')
    ci = request.values.get('ci', '').strip()
    mes = request.values.get('mes', '').strip()
    form = request.form
    if request.method == 'POST' and form.get('accion') == 'registrar':
        err = primer_error(v.numeros(form.get('ci', ''), 'Identificación cliente'),
                           v.numeros(form.get('entrenador_id', ''), 'ID instructor'),
                           v.fecha(form.get('fecha', ''), 'Fecha'))
        if err:
            avisar(False, err)
        else:
            ok, msg = db.registrar_participacion_clase(form['ci'].strip(), int(form['entrenador_id']),
                                                       form['fecha'].strip())
            avisar(ok, msg)
            if ok:
                return redirect(url_for('clases', s='registrar'))
    disponibles = historial = pagos = None
    if seccion == 'consultar' and ci:
        err = v.numeros(ci, 'Identificación')
        if not err[0]:
            avisar(False, err[1])
        else:
            disponibles = db.clases_disponibles_cliente(ci)
            if disponibles is None:
                avisar(False, 'Cliente no encontrado.')
            else:
                historial = db.clases_realizadas_cliente(ci)
    if seccion == 'pagos' and mes:
        err = v.anio_mes(mes)
        if not err[0]:
            avisar(False, err[1])
        else:
            pagos = dict(filas=db.resumen_pagos_instructores(mes),
                         total_clases=db.total_clases_mes(mes),
                         total=db.total_pagar_instructores_mes(mes))
    return render_template('clases.html', s=seccion, form=form, ci=ci, mes=mes,
                           disponibles=disponibles, historial=historial, pagos=pagos,
                           entrenadores=db.todos_entrenadores() if seccion == 'registrar' else [],
                           lista=db.todas_clases_realizadas() if seccion == 'listado' else [])


# ------------------------------------------------------------------ reportes RF24, RF44-48
@app.route('/reportes')
@requiere('reportes')
def reportes():
    db.actualizar_estados_membresia()
    seccion = request.args.get('s', 'general')
    mes = request.args.get('mes', '').strip()
    resumen = None
    if seccion in ('pagos', 'mensual') and mes:
        err = v.anio_mes(mes)
        if not err[0]:
            avisar(False, err[1])
        else:
            resumen = db.resumen_mensual(mes)
    return render_template('reportes.html', s=seccion, mes=mes, resumen=resumen,
                           r=db.reporte_general() if seccion == 'general' else None)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
