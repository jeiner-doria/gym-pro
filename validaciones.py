import re
from datetime import datetime

def texto(valor, campo):
    valor=valor.strip()
    if not valor: return False, f'{campo} es obligatorio.'
    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+",valor): return False, f'Dato inválido en {campo}: solo letras y espacios.'
    return True,''
def numeros(valor,campo):
    if not valor.strip().isdigit(): return False, f'Dato inválido en {campo}: solo números.'
    return True,''
def correo(valor):
    if not re.fullmatch(r'^[^\s@]+@[^\s@]+\.[^\s@]+$',valor.strip()): return False,'Dato inválido en correo. Ejemplo: usuario@gmail.com'
    return True,''
def fecha(valor,campo='fecha'):
    try: datetime.strptime(valor.strip(),'%Y-%m-%d'); return True,''
    except ValueError: return False,f'Dato inválido en {campo}. Use YYYY-MM-DD.'
def positivo(valor,campo):
    try:
        if float(valor)<=0: raise ValueError
        return True,''
    except ValueError:return False,f'Dato inválido en {campo}: debe ser un número positivo.'
def anio_mes(valor):
    try: datetime.strptime(valor.strip(),'%Y-%m'); return True,''
    except ValueError: return False,'Dato inválido en mes. Use el formato YYYY-MM, por ejemplo 2026-09.'
