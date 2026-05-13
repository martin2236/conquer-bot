"""
calibrate.py
Herramienta de calibración para el bot de Conquer Online.

USO:
    python calibrate.py

Te permite:
  1. Capturar la pantalla y ver los valores HSV de cualquier pixel
  2. Definir la región del juego (para modo ventana)
  3. Localizar las barras de HP/MP en la UI
  4. Guardar la configuración calibrada en config.py
"""

import sys
import time
import numpy as np
import cv2
import pyautogui
from pynput import mouse


# ── Estado de calibración ──────────────────────────────────────────────────────
selected_points = []
current_mode = "none"

def capture_screen() -> np.ndarray:
    screenshot = pyautogui.screenshot()
    return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)


def show_hsv_at_click():
    """
    Modo 1: Clickeás en cualquier parte de la pantalla
    y te muestra el valor HSV de ese pixel.
    Útil para encontrar los colores de los ítems.
    """
    print("\n📍 MODO: Inspector de colores HSV")
    print("   Mové el mouse sobre el color del ítem en el juego")
    print("   Presioná CTRL+C para terminar\n")

    try:
        while True:
            x, y = pyautogui.position()
            screenshot = pyautogui.screenshot()
            frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            bgr = frame[y, x]
            hsv = frame_hsv[y, x]

            print(f"\r  Posición: ({x:4d}, {y:4d}) | "
                  f"BGR: ({bgr[0]:3d},{bgr[1]:3d},{bgr[2]:3d}) | "
                  f"HSV: ({hsv[0]:3d},{hsv[1]:3d},{hsv[2]:3d})   ",
                  end="", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n✅ Inspector finalizado")


def capture_region():
    """
    Modo 2: Captura un screenshot y te deja seleccionar
    una región rectangular con el mouse en la imagen.
    Útil para definir game_region, hp_bar_region, mp_bar_region.
    """
    print("\n📍 MODO: Selector de región")
    print("   Se abrirá una ventana con la pantalla.")
    print("   Dibujá el rectángulo de la región que querés.")
    print("   Presioná SPACE o ENTER para confirmar, ESC para cancelar.\n")

    frame = capture_screen()
    # Escalar si la pantalla es muy grande
    h, w = frame.shape[:2]
    scale = min(1.0, 1280 / w)
    display = cv2.resize(frame, (int(w * scale), int(h * scale)))

    roi = cv2.selectROI("Selecciona la región — ENTER para confirmar, ESC para cancelar",
                        display, fromCenter=False, showCrosshair=True)
    cv2.destroyAllWindows()

    if roi == (0, 0, 0, 0):
        print("❌ Cancelado")
        return None

    # Escalar de vuelta a coordenadas reales
    x = int(roi[0] / scale)
    y = int(roi[1] / scale)
    w2 = int(roi[2] / scale)
    h2 = int(roi[3] / scale)

    print(f"✅ Región seleccionada: left={x}, top={y}, width={w2}, height={h2}")
    print(f"   Copiá esto en config.py o vision.py:")
    print(f"   ({x}, {y}, {w2}, {h2})")
    return (x, y, w2, h2)


def test_item_detection():
    """
    Modo 3: Toma un screenshot y muestra visualmente qué ítems detecta.
    """
    print("\n📍 MODO: Test de detección de ítems")
    print("   Posicioná el juego con ítems visibles en el suelo")
    print("   Presioná ENTER cuando estés listo...")
    input()

    from vision import VisionEngine, ITEM_COLOR_RANGES, RARITY_ORDER

    engine = VisionEngine()
    path = engine.save_debug_frame("debug_items.png")
    print(f"✅ Screenshot guardado en debug_items.png")
    print("   Abrilo para ver qué detectó el bot (rectángulos verdes = ítems)")

    # Mostrar también en ventana
    img = cv2.imread("debug_items.png")
    if img is not None:
        h, w = img.shape[:2]
        scale = min(1.0, 1280 / w)
        display = cv2.resize(img, (int(w * scale), int(h * scale)))
        cv2.imshow("Detección de ítems — ESC para cerrar", display)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


def find_hsv_range():
    """
    Modo 4: Ayuda a encontrar el rango HSV exacto de un color.
    Tomás un screenshot, seleccionás el área del color y te da el rango.
    """
    print("\n📍 MODO: Encontrar rango HSV")
    print("   Posicioná el juego con un ítem visible")
    print("   Se abrirá la pantalla — seleccioná el texto del ítem")

    frame = capture_screen()
    h, w = frame.shape[:2]
    scale = min(1.0, 1280 / w)
    display = cv2.resize(frame, (int(w * scale), int(h * scale)))

    roi = cv2.selectROI("Selecciona el área del color del ítem", display,
                        fromCenter=False, showCrosshair=True)
    cv2.destroyAllWindows()

    if roi == (0, 0, 0, 0):
        print("❌ Cancelado")
        return

    x = int(roi[0] / scale)
    y = int(roi[1] / scale)
    w2 = int(roi[2] / scale)
    h2 = int(roi[3] / scale)

    roi_img = frame[y:y+h2, x:x+w2]
    roi_hsv  = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)

    h_vals = roi_hsv[:,:,0].flatten()
    s_vals = roi_hsv[:,:,1].flatten()
    v_vals = roi_hsv[:,:,2].flatten()

    print(f"\n✅ Rango HSV del área seleccionada:")
    print(f"   H: {h_vals.min():3d} → {h_vals.max():3d}")
    print(f"   S: {s_vals.min():3d} → {s_vals.max():3d}")
    print(f"   V: {v_vals.min():3d} → {v_vals.max():3d}")
    print(f"\n   Copiá esto en vision.py (ITEM_COLOR_RANGES):")
    print(f'   "mi_rareza": {{')
    print(f'       "lower": np.array([{h_vals.min()}, {s_vals.min()}, {v_vals.min()}]),')
    print(f'       "upper": np.array([{h_vals.max()}, {s_vals.max()}, {v_vals.max()}]),')
    print(f'   }},')


# ── Menú principal ─────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  ⚔️  Conquer Online Bot — Herramienta de Calibración")
    print("=" * 55)
    print()
    print("  [1] Inspector de colores HSV (mover mouse sobre ítems)")
    print("  [2] Selector de región (game window, HP bar, MP bar)")
    print("  [3] Test de detección de ítems (screenshot anotado)")
    print("  [4] Encontrar rango HSV de un color específico")
    print("  [0] Salir")
    print()

    while True:
        choice = input("  Elegí una opción: ").strip()
        if   choice == "1": show_hsv_at_click()
        elif choice == "2": capture_region()
        elif choice == "3": test_item_detection()
        elif choice == "4": find_hsv_range()
        elif choice == "0": sys.exit(0)
        else: print("  Opción inválida")
        print()


if __name__ == "__main__":
    main()
