"""
main.py
Punto de entrada del bot de Conquer Online (solo Windows).
Lanza el servidor web (por defecto http://localhost:5173).
Si 5173 está ocupado y no definís PORT, usa el siguiente puerto libre (5174, …).
"""

import sys
import os
import socket

os.chdir(os.path.dirname(os.path.abspath(__file__)))


def require_windows():
    """Conquer Online en PC es Windows; el paquete `keyboard` no mapea teclas en macOS/Linux."""
    if sys.platform != "win32":
        print("❌ Este bot solo está pensado para Windows.")
        print("   Conquer Online (cliente oficial) corre en PC Windows; aquí se usa el paquete «keyboard»,")
        print("   que en macOS/Linux no reconoce teclas como 1, a, F1, etc.")
        print(f"   Sistema detectado: {sys.platform!r}")
        sys.exit(1)


def _port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
        except OSError:
            return False
    return True


def resolve_listen_port() -> int:
    """
    - Si existe PORT en el entorno, solo ese puerto (sale con error si está ocupado).
    - Si no, el primer libre entre 5173 y 5200.
    """
    raw = os.environ.get("PORT", "").strip()
    if raw:
        p = int(raw)
        if not _port_free("0.0.0.0", p):
            print(f"❌ El puerto {p} (PORT) está en uso. Liberá el puerto o probá otro, ej.:")
            print(f"   PORT={p + 1} python main.py")
            sys.exit(1)
        return p

    for p in range(5173, 5201):
        if _port_free("0.0.0.0", p):
            if p != 5173:
                print(f"💡 Puerto 5173 ocupado; usando {p}")
            return p
    print("❌ No hay puerto libre entre 5173 y 5200.")
    sys.exit(1)


def check_dependencies():
    missing = []
    required = {
        "flask":        "flask",
        "flask_socketio": "flask-socketio",
        "keyboard":     "keyboard",
    }
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if missing:
        root = os.path.dirname(os.path.abspath(__file__))
        print("❌ Faltan dependencias para el intérprete que estás usando.")
        print(f"   Instalá con:  py -m pip install {' '.join(missing)}")
        print("   (o  python -m pip install …  desde el mismo Python que usás para el bot)")
        if sys.platform == "win32":
            vpy = os.path.join(root, "venv", "Scripts", "python.exe")
            if os.path.isfile(vpy):
                print()
                print("💡 Con el venv del proyecto:")
                print(f"   {vpy} main.py")
        else:
            vpy = os.path.join(root, "venv", "bin", "python")
            if os.path.isfile(vpy):
                print()
                print("💡 Con el venv del proyecto:")
                print(f"   {vpy} main.py")
        sys.exit(1)

if __name__ == "__main__":
    require_windows()
    check_dependencies()
    port = resolve_listen_port()
    print("=" * 55)
    print("  ⚔️  Conquer Online Bot v1.0  —  Interfaz Web")
    print(f"  Abrí en el navegador: http://localhost:{port}")
    print("=" * 55)
    from server import app, socketio
    import threading, webbrowser, time

    def open_browser():
        time.sleep(1.2)
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=open_browser, daemon=True).start()
    socketio.run(app, host="0.0.0.0", port=port, debug=False, use_reloader=False)

