# GYM PRO – versión web (RF01 a RF50)

Misma lógica que la versión Tkinter (`database.py` y `validaciones.py`), pero con interfaz web hecha en Flask.

## Probar en tu computador
```bash
pip install -r requirements.txt
python app.py          # abre http://localhost:5000
```
Usuarios de prueba: `admin/admin123`, `empleado/empleado123`, `entrenador/entrenador123`.

## Desplegar en Render
1. Sube esta carpeta a un repositorio de GitHub (el `.gitignore` ya excluye la base de datos).
2. En Render: **New + → Blueprint** y elige el repositorio (usa `render.yaml`).
   - O manualmente: **New + → Web Service**, Build Command `pip install -r requirements.txt`,
     Start Command `gunicorn app:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT`.
3. Variables de entorno: `SECRET_KEY` (cualquier texto largo y aleatorio) y, si usas disco, `DB_PATH=/var/data/gimnasio.db`.

### Importante: persistencia de datos
SQLite guarda los datos en un archivo. En el plan **gratuito** de Render el disco es temporal:
los datos se borran en cada reinicio o nuevo despliegue. Opciones:
- **Para entregar/exponer el proyecto**: plan gratuito sin disco (se recrea con los usuarios de prueba).
- **Para conservar datos**: plan de pago con *Disk* montado en `/var/data` (ya configurado en `render.yaml`).

Mantén `--workers 1` mientras uses SQLite.

## Cambios respecto a la versión de escritorio
- Interfaz web con login, menú lateral por rol y submenú por módulo.
- Contraseñas guardadas con hash (antes en texto plano).
- Las fechas usan selector de calendario; los meses usan selector de mes.
- Asignar membresía y asignar entrenador/instructor se eligen desde listas desplegables.
- Se mantienen todas las validaciones, el control de acceso por rol y los RF01–RF50.
