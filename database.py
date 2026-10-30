import os
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

# En Render se recomienda apuntar DB_PATH a un disco persistente (ej. /var/data/gimnasio.db)
DB = Path(os.environ.get('DB_PATH', str(Path(__file__).with_name('gimnasio.db'))))
DB.parent.mkdir(parents=True, exist_ok=True)

                                                                       
PLANES_MEMBRESIA = {
    'Normal': {'precio': 50000, 'clases': 2},
    'Gold': {'precio': 70000, 'clases': 4},
    'Platino': {'precio': 100000, 'clases': 6},
}

                                                            
PAGO_POR_CLASE = 10000


def obtener_conexion():
    con = sqlite3.connect(DB, timeout=15)
    con.execute('PRAGMA foreign_keys = ON')
    return con


def crear_tablas():
    con = obtener_conexion(); cur = con.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS clientes(
      id INTEGER PRIMARY KEY AUTOINCREMENT, identificacion TEXT UNIQUE NOT NULL,
      nombre TEXT NOT NULL, telefono TEXT NOT NULL, correo TEXT NOT NULL,
      fecha_nacimiento TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'Activo',
      entrenador_id INTEGER, membresia_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS empleados(
      id INTEGER PRIMARY KEY AUTOINCREMENT, identificacion TEXT UNIQUE NOT NULL,
      nombre TEXT NOT NULL, telefono TEXT NOT NULL, cargo TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS entrenadores(
      id INTEGER PRIMARY KEY AUTOINCREMENT, identificacion TEXT UNIQUE NOT NULL,
      nombre TEXT NOT NULL, especialidad TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS membresias(
      id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, tipo TEXT NOT NULL,
      precio REAL NOT NULL, fecha_inicio TEXT NOT NULL, fecha_fin TEXT NOT NULL,
      estado TEXT NOT NULL DEFAULT 'Activa'
    );
    CREATE TABLE IF NOT EXISTS pagos(
      id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER NOT NULL,
      fecha TEXT NOT NULL, valor REAL NOT NULL, concepto TEXT NOT NULL,
      FOREIGN KEY(cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS ingresos(
      id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER NOT NULL,
      fecha_hora TEXT NOT NULL, FOREIGN KEY(cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS salidas(
      id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER NOT NULL,
      fecha_hora TEXT NOT NULL, FOREIGN KEY(cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS maquinas(
      id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
      marca TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'Disponible'
    );
    CREATE TABLE IF NOT EXISTS rutinas(
      id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER NOT NULL,
      nombre TEXT NOT NULL, descripcion TEXT NOT NULL, fecha TEXT NOT NULL,
      FOREIGN KEY(cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS usuarios(
      id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT UNIQUE NOT NULL,
      contrasena TEXT NOT NULL, tipo TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS clases_realizadas(
      id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER NOT NULL,
      entrenador_id INTEGER NOT NULL, fecha TEXT NOT NULL,
      FOREIGN KEY(cliente_id) REFERENCES clientes(id) ON DELETE CASCADE,
      FOREIGN KEY(entrenador_id) REFERENCES entrenadores(id) ON DELETE CASCADE
    );
    ''')

    for sql in [
        "ALTER TABLE clientes ADD COLUMN estado TEXT NOT NULL DEFAULT 'Activo'",
        "ALTER TABLE clientes ADD COLUMN entrenador_id INTEGER",
        "ALTER TABLE clientes ADD COLUMN membresia_id INTEGER",
        "ALTER TABLE membresias ADD COLUMN clases_incluidas INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE pagos ADD COLUMN membresia_id INTEGER",
    ]:
        try: cur.execute(sql)
        except sqlite3.OperationalError: pass

                                                                                     
                                                                                      
    try:
        cur.execute("ALTER TABLE clientes ADD COLUMN clases_disponibles INTEGER NOT NULL DEFAULT 0")
        cur.execute("""UPDATE clientes SET clases_disponibles = COALESCE(
            (SELECT m.clases_incluidas FROM membresias m WHERE m.id = clientes.membresia_id), 0)
            WHERE membresia_id IS NOT NULL""")
    except sqlite3.OperationalError:
        pass
    con.commit(); con.close()


def _sembrar_usuarios():
                                                                      
    ok, rows = _execute('SELECT COUNT(*) FROM usuarios', fetch=True)
    if ok and rows and rows[0][0] == 0:
        _execute('INSERT INTO usuarios(usuario,contrasena,tipo) VALUES(?,?,?)', ('admin', generate_password_hash('admin123'), 'Administrador'))
        _execute('INSERT INTO usuarios(usuario,contrasena,tipo) VALUES(?,?,?)', ('empleado', generate_password_hash('empleado123'), 'Empleado'))
        _execute('INSERT INTO usuarios(usuario,contrasena,tipo) VALUES(?,?,?)', ('entrenador', generate_password_hash('entrenador123'), 'Entrenador'))


def _execute(sql, params=(), fetch=False, many=False):
    con = None
    try:
        con = obtener_conexion(); cur = con.cursor()
        if many: cur.executemany(sql, params)
        else: cur.execute(sql, params)
        data = cur.fetchall() if fetch else cur.rowcount
        con.commit(); con.close(); return True, data
    except sqlite3.IntegrityError as e:
        if con is not None:
            try: con.close()
            except Exception: pass
        return False, str(e)
    except Exception as e:
        if con is not None:
            try: con.close()
            except Exception: pass
        return False, str(e)


                                                          
def validar_usuario(usuario, contrasena):
    ok, rows = _execute('SELECT contrasena,tipo FROM usuarios WHERE usuario=?', (usuario,), True)
    if ok and rows:
        guardada, tipo = rows[0]
        if guardada.startswith(('pbkdf2:', 'scrypt:')):
            return tipo if check_password_hash(guardada, contrasena) else None
        return tipo if guardada == contrasena else None  # compatibilidad con bases antiguas
    return None


                                                                     
def insertar_cliente(identificacion, nombre, telefono, correo, fecha):
    ok, _ = _execute('INSERT INTO clientes(identificacion,nombre,telefono,correo,fecha_nacimiento) VALUES(?,?,?,?,?)', (identificacion, nombre, telefono, correo, fecha))
    return ok, 'Cliente registrado correctamente.' if ok else 'Ya existe un cliente con esa identificación.'


def buscar_cliente(identificacion):
    ok, rows = _execute('SELECT id,identificacion,nombre,telefono,correo,fecha_nacimiento,estado,entrenador_id,membresia_id FROM clientes WHERE identificacion=?', (identificacion,), True)
    return rows[0] if ok and rows else None


def todos_clientes():
    return _execute('SELECT id,identificacion,nombre,telefono,correo,fecha_nacimiento,estado FROM clientes ORDER BY nombre', fetch=True)[1]


def actualizar_cliente(identificacion, nombre, telefono, correo, fecha):
    ok, n = _execute('UPDATE clientes SET nombre=?,telefono=?,correo=?,fecha_nacimiento=? WHERE identificacion=?', (nombre, telefono, correo, fecha, identificacion))
    return ok and n > 0, 'Cliente actualizado correctamente.' if ok and n > 0 else 'Cliente no encontrado.'


def eliminar_cliente(identificacion):
    ok, n = _execute('DELETE FROM clientes WHERE identificacion=?', (identificacion,))
    return ok and n > 0, 'Cliente eliminado correctamente.' if ok and n > 0 else 'Cliente no encontrado.'


def desactivar_cliente(identificacion):
    ok, n = _execute("UPDATE clientes SET estado='Desactivado' WHERE identificacion=?", (identificacion,))
    return ok and n > 0, 'Cliente desactivado.' if ok and n > 0 else 'Cliente no encontrado.'


def activar_cliente(identificacion):
    ok, n = _execute("UPDATE clientes SET estado='Activo' WHERE identificacion=?", (identificacion,))
    return ok and n > 0, 'Cliente activado.' if ok and n > 0 else 'Cliente no encontrado.'


                                                                       
def insertar_empleado(i, n, t, c):
    ok, _ = _execute('INSERT INTO empleados(identificacion,nombre,telefono,cargo) VALUES(?,?,?,?)', (i, n, t, c))
    return ok, 'Empleado registrado correctamente.' if ok else 'Ya existe esa identificación.'


def todos_empleados():
    return _execute('SELECT identificacion,nombre,telefono,cargo FROM empleados ORDER BY nombre', fetch=True)[1]


def buscar_empleado(identificacion):
    ok, rows = _execute('SELECT identificacion,nombre,telefono,cargo FROM empleados WHERE identificacion=?', (identificacion,), True)
    return rows[0] if ok and rows else None


def actualizar_empleado(identificacion, nombre, telefono, cargo):
    ok, n = _execute('UPDATE empleados SET nombre=?,telefono=?,cargo=? WHERE identificacion=?', (nombre, telefono, cargo, identificacion))
    return ok and n > 0, 'Empleado actualizado correctamente.' if ok and n > 0 else 'Empleado no encontrado.'


def eliminar_empleado(identificacion):
    ok, n = _execute('DELETE FROM empleados WHERE identificacion=?', (identificacion,))
    return ok and n > 0, 'Empleado eliminado correctamente.' if ok and n > 0 else 'Empleado no encontrado.'


                                                                          
def insertar_entrenador(i, n, e):
    ok, _ = _execute('INSERT INTO entrenadores(identificacion,nombre,especialidad) VALUES(?,?,?)', (i, n, e))
    return ok, 'Entrenador registrado correctamente.' if ok else 'Ya existe esa identificación.'


def todos_entrenadores():
    return _execute('SELECT id,identificacion,nombre,especialidad FROM entrenadores ORDER BY nombre', fetch=True)[1]


def buscar_entrenador(identificacion):
    ok, rows = _execute('SELECT id,identificacion,nombre,especialidad FROM entrenadores WHERE identificacion=?', (identificacion,), True)
    return rows[0] if ok and rows else None


def actualizar_entrenador(identificacion, nombre, especialidad):
    ok, n = _execute('UPDATE entrenadores SET nombre=?,especialidad=? WHERE identificacion=?', (nombre, especialidad, identificacion))
    return ok and n > 0, 'Entrenador actualizado correctamente.' if ok and n > 0 else 'Entrenador no encontrado.'


def eliminar_entrenador(identificacion):
    ok_sel, filas = _execute('SELECT id FROM entrenadores WHERE identificacion=?', (identificacion,), True)
    if not ok_sel or not filas:
        return False, 'Entrenador no encontrado.'
    eid = filas[0][0]
    ok, n = _execute('DELETE FROM entrenadores WHERE identificacion=?', (identificacion,))
    if ok and n > 0:
                                                                                    
        _execute('UPDATE clientes SET entrenador_id=NULL WHERE entrenador_id=?', (eid,))
        return True, 'Entrenador eliminado correctamente.'
    return False, 'Entrenador no encontrado.'


                                                                          
def crear_membresia(nombre, tipo, precio, clases, inicio, fin):
    ok, _ = _execute('INSERT INTO membresias(nombre,tipo,precio,clases_incluidas,fecha_inicio,fecha_fin) VALUES(?,?,?,?,?,?)', (nombre, tipo, precio, clases, inicio, fin))
    return ok, 'Membresía registrada correctamente.' if ok else 'No se pudo registrar la membresía.'


def membresias():
    return _execute('SELECT id,nombre,tipo,precio,clases_incluidas,fecha_inicio,fecha_fin,estado FROM membresias ORDER BY id DESC', fetch=True)[1]


def asignar_membresia(ci, mid):
    ok_c, cliente = _execute('SELECT id FROM clientes WHERE identificacion=?', (ci,), True)
    if not ok_c or not cliente:
        return False, 'Cliente no encontrado.'
    ok_m, membresia = _execute('SELECT id FROM membresias WHERE id=?', (mid,), True)
    if not ok_m or not membresia:
        return False, 'La membresía seleccionada no existe.'
    ok, n = _execute('UPDATE clientes SET membresia_id=? WHERE identificacion=?', (mid, ci))
    return ok and n > 0, 'Membresía asignada correctamente.' if ok and n > 0 else 'No se pudo asignar la membresía.'


def estado_membresia(ci):
    ok, r = _execute('''SELECT m.tipo,m.fecha_inicio,m.fecha_fin,m.estado,m.clases_incluidas,c.clases_disponibles FROM clientes c LEFT JOIN membresias m ON c.membresia_id=m.id WHERE c.identificacion=?''', (ci,), True)
    if not ok or not r:
        return None
    fila = r[0]
    if fila[0] is None:
        return None
    return fila


def renovar_membresia(ci, mid):
    return asignar_membresia(ci, mid)


def asignar_membresia_y_pago(ci, mid, fecha, valor, concepto):
    con = None
    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute('SELECT id FROM clientes WHERE identificacion=?', (ci,))
        cliente = cur.fetchone()
        if not cliente:
            con.close()
            return False, 'Cliente no encontrado.'
        cur.execute('SELECT id,clases_incluidas FROM membresias WHERE id=?', (mid,))
        membresia = cur.fetchone()
        if not membresia:
            con.close()
            return False, 'La membresía seleccionada no existe.'
        clases_incluidas = membresia[1] or 0
                                                                             
        cur.execute('UPDATE clientes SET membresia_id=?, clases_disponibles=? WHERE id=?', (mid, clases_incluidas, cliente[0]))
        cur.execute('INSERT INTO pagos(cliente_id,fecha,valor,concepto,membresia_id) VALUES(?,?,?,?,?)', (cliente[0], fecha, valor, concepto, mid))
        con.commit()
        con.close()
        return True, f'Membresía asignada/renovada y pago registrado correctamente. Clases disponibles: {clases_incluidas}.'
    except Exception as e:
        if con is not None:
            try:
                con.rollback()
                con.close()
            except Exception:
                pass
        return False, f'No se pudo completar la operación: {e}'


def registrar_pago(ci, fecha, valor, concepto):
    ok_c, r = _execute('SELECT id FROM clientes WHERE identificacion=?', (ci,), True)
    if not ok_c or not r:
        return False, 'Cliente no encontrado.'
    ok, _ = _execute('INSERT INTO pagos(cliente_id,fecha,valor,concepto) VALUES(?,?,?,?)', (r[0][0], fecha, valor, concepto))
    return ok, 'Pago registrado correctamente.' if ok else 'No se pudo registrar el pago.'


def pagos_cliente(ci):
    return _execute('''SELECT p.fecha,p.valor,p.concepto FROM pagos p JOIN clientes c ON p.cliente_id=c.id WHERE c.identificacion=? ORDER BY p.id DESC''', (ci,), True)[1]


                                                                            
def registrar_ingreso(ci, fecha_hora):
                                                                                  
                                                             
    ok, r = _execute("SELECT c.id,c.estado,m.fecha_inicio,m.fecha_fin FROM clientes c LEFT JOIN membresias m ON c.membresia_id=m.id WHERE c.identificacion=?", (ci,), True)
    if not ok or not r:
        return False, 'Cliente no encontrado.'
    cid, estado, inicio, fin = r[0]
    if estado != 'Activo':
        return False, 'Acceso bloqueado: el cliente está desactivado.'
    from datetime import date
    hoy = date.today().isoformat()
    if not fin:
        return False, 'Acceso bloqueado: el cliente no tiene una membresía asignada.'
    if fin < hoy:
        return False, 'Acceso bloqueado: la membresía está vencida.'
    if inicio and inicio > hoy:
        return False, 'Acceso bloqueado: la membresía todavía no está activa.'
    ok, _ = _execute('INSERT INTO ingresos(cliente_id,fecha_hora) VALUES(?,?)', (cid, fecha_hora))
    return ok, 'Ingreso registrado correctamente.' if ok else 'No se pudo registrar el ingreso.'


def registrar_salida(ci, fecha_hora):
    ok_c, r = _execute('SELECT id FROM clientes WHERE identificacion=?', (ci,), True)
    if not ok_c or not r:
        return False, 'Cliente no encontrado.'
    ok, _ = _execute('INSERT INTO salidas(cliente_id,fecha_hora) VALUES(?,?)', (r[0][0], fecha_hora))
    return ok, 'Salida registrada correctamente.' if ok else 'No se pudo registrar la salida.'


def asistencia_cliente(ci):
                                                                
    ok, rows = _execute('''
        SELECT 'Ingreso', i.fecha_hora FROM ingresos i JOIN clientes c ON i.cliente_id=c.id WHERE c.identificacion=?
        UNION ALL
        SELECT 'Salida', s.fecha_hora FROM salidas s JOIN clientes c ON s.cliente_id=c.id WHERE c.identificacion=?
        ORDER BY 2 DESC
    ''', (ci, ci), True)
    return rows if ok else []


                                                                       
def registrar_maquina(nombre, marca, estado):
    ok, _ = _execute('INSERT INTO maquinas(nombre,marca,estado) VALUES(?,?,?)', (nombre, marca, estado))
    return ok, 'Máquina registrada correctamente.' if ok else 'No se pudo registrar la máquina.'


def maquinas():
    return _execute('SELECT id,nombre,marca,estado FROM maquinas ORDER BY nombre', fetch=True)[1]


def cambiar_estado_maquina(mid, estado):
    ok, n = _execute('UPDATE maquinas SET estado=? WHERE id=?', (estado, mid))
    return ok and n > 0, 'Estado actualizado.' if ok and n > 0 else 'Máquina no encontrada.'


                                                                     
def registrar_rutina(ci, nombre, descripcion, fecha):
    ok_c, r = _execute('SELECT id FROM clientes WHERE identificacion=?', (ci,), True)
    if not ok_c or not r:
        return False, 'Cliente no encontrado.'
    ok, _ = _execute('INSERT INTO rutinas(cliente_id,nombre,descripcion,fecha) VALUES(?,?,?,?)', (r[0][0], nombre, descripcion, fecha))
    return ok, 'Rutina registrada correctamente.' if ok else 'No se pudo registrar la rutina.'


def rutinas():
    return _execute('''SELECT r.id,c.identificacion,c.nombre,r.nombre,r.descripcion,r.fecha FROM rutinas r JOIN clientes c ON r.cliente_id=c.id ORDER BY r.id DESC''', fetch=True)[1]


def rutinas_cliente(ci):
                                                             
    return _execute('''SELECT r.id,c.identificacion,c.nombre,r.nombre,r.descripcion,r.fecha FROM rutinas r JOIN clientes c ON r.cliente_id=c.id WHERE c.identificacion=? ORDER BY r.id DESC''', (ci,), True)[1]


def asignar_entrenador(ci, eid):
    ok_c, cliente = _execute('SELECT id FROM clientes WHERE identificacion=?', (ci,), True)
    if not ok_c or not cliente:
        return False, 'Cliente no encontrado.'
    ok_e, entrenador = _execute('SELECT id FROM entrenadores WHERE id=?', (eid,), True)
    if not ok_e or not entrenador:
        return False, 'El entrenador seleccionado no existe.'
    ok, n = _execute('UPDATE clientes SET entrenador_id=? WHERE identificacion=?', (eid, ci))
    return ok and n > 0, 'Entrenador asignado correctamente.' if ok and n > 0 else 'No se pudo asignar el entrenador.'


                                                                                                
                                                                                                
def clases_disponibles_cliente(ci):
                                                              
    ok, rows = _execute('SELECT clases_disponibles FROM clientes WHERE identificacion=?', (ci,), True)
    if ok and rows:
        return rows[0][0]
    return None


def registrar_participacion_clase(ci, entrenador_id, fecha):
                                                                                              
                                                                                        
    ok_c, cli = _execute('SELECT id,clases_disponibles,estado FROM clientes WHERE identificacion=?', (ci,), True)
    if not ok_c or not cli:
        return False, 'Cliente no encontrado.'
    cid, disponibles, estado = cli[0]
    if estado != 'Activo':
        return False, 'El cliente está desactivado y no puede participar en clases.'
    ok_e, ent = _execute('SELECT id FROM entrenadores WHERE id=?', (entrenador_id,), True)
    if not ok_e or not ent:
        return False, 'El instructor seleccionado no existe.'
    if disponibles is None or disponibles <= 0:
        return False, 'El cliente ya utilizó todas las clases incluidas en su membresía. No puede participar en más clases.'

    con = None
    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute('INSERT INTO clases_realizadas(cliente_id,entrenador_id,fecha) VALUES(?,?,?)', (cid, entrenador_id, fecha))
        cur.execute('UPDATE clientes SET clases_disponibles = clases_disponibles - 1 WHERE id=?', (cid,))
        con.commit()
        con.close()
        return True, f'Participación registrada correctamente. Clases disponibles restantes: {disponibles - 1}.'
    except Exception as e:
        if con is not None:
            try:
                con.rollback()
                con.close()
            except Exception:
                pass
        return False, f'No se pudo registrar la participación: {e}'


def clases_realizadas_cliente(ci):
                                                                       
    return _execute(
        '''SELECT cr.id, cr.fecha, e.nombre FROM clases_realizadas cr
           JOIN clientes c ON cr.cliente_id = c.id
           JOIN entrenadores e ON cr.entrenador_id = e.id
           WHERE c.identificacion=? ORDER BY cr.id DESC''',
        (ci,), True
    )[1]


def todas_clases_realizadas():
                                                                 
    return _execute(
        '''SELECT cr.id, c.identificacion, c.nombre, e.nombre, cr.fecha FROM clases_realizadas cr
           JOIN clientes c ON cr.cliente_id = c.id
           JOIN entrenadores e ON cr.entrenador_id = e.id
           ORDER BY cr.id DESC''',
        fetch=True
    )[1]


                                                               
def actualizar_estados_membresia():
                                                                            
    from datetime import date
    hoy = date.today().isoformat()
    _execute(
        """UPDATE membresias SET estado = CASE
             WHEN fecha_fin < ? THEN 'Vencida'
             WHEN fecha_inicio > ? THEN 'Inactiva'
             WHEN julianday(fecha_fin) - julianday(?) <= 7 THEN 'Por vencer'
             ELSE 'Activa'
           END""",
        (hoy, hoy, hoy)
    )


                                                                                                
                                                                                                
def resumen_pagos_instructores(anio_mes):
                                                                                       
                                                                                            
    ok, rows = _execute('''
        SELECT e.id, e.nombre, e.especialidad, COUNT(cr.id) AS clases_mes
        FROM entrenadores e
        LEFT JOIN clases_realizadas cr ON cr.entrenador_id = e.id AND substr(cr.fecha,1,7) = ?
        GROUP BY e.id, e.nombre, e.especialidad
        ORDER BY e.nombre
    ''', (anio_mes,), True)
    if not ok or not rows:
        return []
    return [(eid, nombre, esp, clases, clases * PAGO_POR_CLASE) for eid, nombre, esp, clases in rows]


def total_clases_mes(anio_mes):
                                                                  
    ok, rows = _execute('SELECT COUNT(*) FROM clases_realizadas WHERE substr(fecha,1,7) = ?', (anio_mes,), True)
    return rows[0][0] if ok and rows else 0


def total_pagar_instructores_mes(anio_mes):
                                                                               
    return total_clases_mes(anio_mes) * PAGO_POR_CLASE


                                                                                                
                                                                                                
def participantes_unicos_mes(anio_mes):
                                                                                               
    ok, rows = _execute(
        'SELECT COUNT(DISTINCT cliente_id) FROM clases_realizadas WHERE substr(fecha,1,7) = ?',
        (anio_mes,), True
    )
    return rows[0][0] if ok and rows else 0


def participantes_por_membresia_mes(anio_mes):
                                                                                                  
                                                                                        
    ok, rows = _execute('''
        SELECT m.tipo, COUNT(DISTINCT cr.cliente_id)
        FROM clases_realizadas cr
        JOIN clientes c ON cr.cliente_id = c.id
        JOIN membresias m ON c.membresia_id = m.id
        WHERE substr(cr.fecha,1,7) = ?
        GROUP BY m.tipo
    ''', (anio_mes,), True)
    conteos = {tipo: 0 for tipo in PLANES_MEMBRESIA}
    if ok and rows:
        for tipo, cantidad in rows:
            if tipo in conteos:
                conteos[tipo] = cantidad
    return conteos


def ingresos_por_membresia_mes(anio_mes):
                                                                                       
    ok, rows = _execute('''
        SELECT m.tipo, COALESCE(SUM(p.valor),0)
        FROM pagos p
        JOIN membresias m ON p.membresia_id = m.id
        WHERE substr(p.fecha,1,7) = ?
        GROUP BY m.tipo
    ''', (anio_mes,), True)
    ingresos = {tipo: 0 for tipo in PLANES_MEMBRESIA}
    if ok and rows:
        for tipo, total in rows:
            if tipo in ingresos:
                ingresos[tipo] = total
    return ingresos


def ingreso_total_membresias_mes(anio_mes):
                                                                                      
    ok, rows = _execute(
        'SELECT COALESCE(SUM(valor),0) FROM pagos WHERE membresia_id IS NOT NULL AND substr(fecha,1,7) = ?',
        (anio_mes,), True
    )
    return rows[0][0] if ok and rows else 0


def resumen_mensual(anio_mes):
                                                                                                 
                                                                                       
    return {
        'mes': anio_mes,
        'total_clases': total_clases_mes(anio_mes),
        'participantes_unicos': participantes_unicos_mes(anio_mes),
        'participantes_por_membresia': participantes_por_membresia_mes(anio_mes),
        'ingresos_por_membresia': ingresos_por_membresia_mes(anio_mes),
        'ingreso_total_membresias': ingreso_total_membresias_mes(anio_mes),
        'pagos_instructores': resumen_pagos_instructores(anio_mes),
        'total_pagar_instructores': total_pagar_instructores_mes(anio_mes),
    }


                                                                                 
def estado_cliente(ci):
                                                                      
    ok, rows = _execute('SELECT nombre, estado FROM clientes WHERE identificacion=?', (ci,), True)
    if ok and rows:
        return rows[0]
    return None


                                                                
def reporte_general():
    def _uno(sql, params=()):
        ok, rows = _execute(sql, params, True)
        return rows[0][0] if ok and rows else 0

    return {
        'total_clientes': _uno('SELECT COUNT(*) FROM clientes'),
        'clientes_activos': _uno("SELECT COUNT(*) FROM clientes WHERE estado='Activo'"),
        'membresias_activas': _uno("SELECT COUNT(*) FROM membresias WHERE estado='Activa'"),
        'membresias_por_vencer': _uno("SELECT COUNT(*) FROM membresias WHERE estado='Por vencer'"),
        'membresias_vencidas': _uno("SELECT COUNT(*) FROM membresias WHERE estado='Vencida'"),
        'total_recaudado': _uno('SELECT COALESCE(SUM(valor),0) FROM pagos'),
        'total_asistencias': _uno('SELECT COUNT(*) FROM ingresos'),
        'total_clases_realizadas': _uno('SELECT COUNT(*) FROM clases_realizadas'),
        'total_maquinas': _uno('SELECT COUNT(*) FROM maquinas'),
        'maquinas_mantenimiento': _uno("SELECT COUNT(*) FROM maquinas WHERE estado='Mantenimiento'"),
    }


crear_tablas()
_sembrar_usuarios()
actualizar_estados_membresia()
