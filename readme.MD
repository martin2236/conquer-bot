### Requisito: solo Windows (PC)

El cliente de Conquer Online y el paquete `keyboard` están pensados para Windows. En macOS/Linux las teclas (`1`, `a`, `F1`, …) **no** se mapean bien y el bot fallará al simular teclas.

### Iniciar el bot (Windows)

```text
cd ruta\al\proyecto-bot
venv\Scripts\activate
python main.py
```

Abrí en el navegador la URL que imprime la consola (por defecto `http://localhost:5173`). Si el puerto 5173 está ocupado, el script puede usar 5174, etc.

### Detener y liberar el puerto

En la terminal donde corre el bot: **Ctrl+C**.

Para ver qué proceso usa el puerto:

```text
netstat -ano | findstr :5173
```

### Dependencias (ejemplo)

```text
py -m pip install flask flask-socketio keyboard pyautogui opencv-python numpy pillow
```

(O instalá desde `requirements.txt` según tu entorno.)
