## Conquer Online Bot

Bot para Windows con panel web, auto-skill, auto-pick y soporte opcional de vision por OpenCV.

## Requisito: solo Windows

El cliente de Conquer Online y los paquetes `keyboard` y `pyautogui` dependen de la sesion grafica real de Windows. Por eso este proyecto debe ejecutarse directamente en el host, no dentro de Docker, WSL o un contenedor Linux.

## Requisitos previos

Antes de arrancar, asegurate de tener:

- Windows
- Python 3.10 o superior instalado y agregado al `PATH`
- Conquer Online instalado
- PowerShell

Si no tenes Python, descargalo desde:

`https://www.python.org/downloads/windows/`

Durante la instalacion marca la opcion `Add Python to PATH`.

## Instalacion rapida

Desde la carpeta del proyecto:

```powershell
.\setup_windows.ps1
```

Ese script:

- detecta `py` o `python`
- crea `venv`
- actualiza `pip`
- instala las dependencias reales del proyecto

Si PowerShell bloquea el script, ejecuta primero:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## Ejecucion

Activa el entorno virtual y levanta el panel web:

```powershell
.\venv\Scripts\Activate.ps1
python main.py
```

Se abrira el navegador en `http://localhost:5173` o en el siguiente puerto libre (`5174`, `5175`, etc.).

## Modo alternativo: GUI de escritorio

Si preferis la interfaz Tkinter:

```powershell
.\venv\Scripts\Activate.ps1
python gui.py
```

## Calibracion de vision

Si vas a usar deteccion de items, enemigos o barras HP/MP:

```powershell
.\venv\Scripts\Activate.ps1
python calibrate.py
```

Esto te ayuda a ajustar colores y regiones segun tu resolucion y tu cliente.

## Detener y liberar el puerto

En la terminal donde corre el bot: `Ctrl+C`

Para ver que proceso usa el puerto:

```powershell
netstat -ano | findstr :5173
```

## Problemas comunes

### `python` o `py` no existe

Python no esta instalado o no quedo en `PATH`.

### El bot abre la web pero no controla el juego

Proba ejecutar PowerShell o la app con permisos de administrador. Algunos hooks globales de teclado no funcionan bien sin elevacion.

### La vision detecta mal

Corre `python calibrate.py` y revisa las regiones y rangos HSV en el modulo de vision.

### El puerto 5173 esta ocupado

`main.py` busca automaticamente otro puerto libre hasta `5200`.
