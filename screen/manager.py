from evdev import InputDevice, ecodes
import os
import struct
import sys
import time
import subprocess
import signal # Necessario per terminare i processi

# --- Costanti di configurazione ---
FB_WIDTH, FB_HEIGHT = 480, 320
FRAMEBUFFER_DEVICE = '/dev/fb1'
TOUCHSCREEN_DEVICE = '/dev/input/event0'

# --- Costanti di Design (Tema "Apple Dark") ---
# (Le tue costanti colore... BG_COLOR, TEXT_COLOR, ecc.)
BG_COLOR = (20, 20, 22)         
TEXT_COLOR = (240, 240, 240)    
PRIMARY_COLOR = (10, 132, 255)  
SECONDARY_COLOR = (142, 142, 147) 
GREEN = (52, 199, 89)
RED = (255, 69, 58)
YELLOW = (255, 214, 10)
ORANGE = (255, 159, 10)

PADDING = 20
CORNER_RADIUS = 10

# Rimuoviamo gli import che non servono più:
# import psutil
# import immich 
# import yt
# import rpi

# --- Variabile globale per il processo attivo ---
current_process = None

def start_app(app_name):
    global current_process
    
    # 1. Termina il processo precedente, se esiste
    if current_process:
        print(f"Sto terminando il processo precedente (PID: {current_process.pid})...")
        try:
            # Usiamo os.killpg per terminare l'intero gruppo di processi (figli inclusi, come fbi o ffmpeg)
            os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
            current_process.wait(timeout=2) # Aspettiamo che termini
        except (ProcessLookupError, subprocess.TimeoutExpired, PermissionError):
            # Se non termina o è già morto, usiamo SIGKILL
            try:
                os.killpg(os.getpgid(current_process.pid), signal.SIGKILL)
            except Exception as e:
                print(f"Errore nel terminare il processo: {e}")
        current_process = None

    # 2. Avvia il nuovo processo
    command = []
    if app_name == 'immich':
        # Assicurati che il path sia corretto e usa 'sudo' se serve per fb1
        command = ['sudo', 'python3', 'immich.py']
    elif app_name == 'yt':
        command = ['sudo', 'python3', 'yt.py']
    elif app_name == 'rpi':
        command = ['sudo', 'python3', 'rpi.py']
    else:
        print(f"App non riconosciuta: {app_name}")
        return

    print(f"Avvio di: {' '.join(command)}")
    try:
        # preexec_fn=os.setsid è FONDAMENTALE per creare un nuovo gruppo di processi
        # che possiamo terminare in modo affidabile
        current_process = subprocess.Popen(command, preexec_fn=os.setsid)
    except Exception as e:
        print(f"Errore durante l'avvio di {app_name}: {e}")

# --- Schermate dell'applicazione ---
def listen(stato = 10):
    global current_process 
    
    try:
        device = InputDevice(TOUCHSCREEN_DEVICE)
    except Exception as e:
        print(f"Errore: Impossibile avviare il listener del touchscreen: {e}")
        print("Assicurati che il dispositivo sia connesso e i permessi siano corretti ('sudo'?).")
        return

    print(f"Dispositivo: {device.name}")
    print(f"In attesa di tocchi su {TOUCHSCREEN_DEVICE}...")

    try:
        abs_x_info = device.absinfo(ecodes.ABS_X)
        abs_y_info = device.absinfo(ecodes.ABS_Y)
        max_touch_raw_x = abs_x_info.max
        max_touch_raw_y = abs_y_info.max
    except KeyError:
        print("Avviso: Impossibile ottenere absinfo. Uso valori di fallback (4095).")
        max_touch_raw_x = 4095 
        max_touch_raw_y = 4095
    
    if max_touch_raw_x == 0 or max_touch_raw_y == 0:
        print("Errore: I valori massimi del touchscreen non sono validi (0).")
        return

    current_raw_x, current_raw_y = 0, 0
    center_x = FB_WIDTH // 2
    center_y = FB_HEIGHT // 2

    count = 0 
    try:
        for event in device.read_loop():
            if event.type == ecodes.EV_ABS:
                if event.code == ecodes.ABS_X:
                    current_raw_x = event.value
                elif event.code == ecodes.ABS_Y:
                    current_raw_y = event.value
            
            elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH and event.value == 1:
                count += 1
                
                scaled_x = int(((max_touch_raw_y - current_raw_y) / max_touch_raw_y) * FB_WIDTH)
                scaled_y = int((current_raw_x / max_touch_raw_x) * FB_HEIGHT)
                scaled_x = max(0, min(FB_WIDTH - 1, scaled_x))
                scaled_y = max(0, min(FB_HEIGHT - 1, scaled_y))

                print(f"Tocco raw: ({current_raw_x}, {current_raw_y}) -> Scalato: ({scaled_x}, {scaled_y})")
                
                if count % 2 == 0:
                    if stato == 0: 
                        if scaled_x < center_x:
                                print("-> IMMICH")
                                stato = 10
                                start_app('immich') 
                                
                    elif stato == 10: 
                        if scaled_x < center_x:
                                print("-> YOUTUBE")
                                stato = 20
                                start_app('yt') 
                        if scaled_x > center_x:
                                print("-> SETTINGS")
                                stato = 0
                                start_app('rpi') 

                    elif stato == 20: 
                        if scaled_x > center_x:
                                print("-> IMMICH")
                                stato = 10 
                                start_app('immich') 
                                
    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.")
    finally:
        if current_process:
             print("Pulizia finale...")
             try:
                 os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
             except Exception:
                 pass 

if __name__ == "__main__":
    if sys.platform != 'linux':
        print("Questo script è progettato per sistemi Linux.")
        sys.exit(1)

    stato = 10
    start_app('immich') 
    listen(stato)       