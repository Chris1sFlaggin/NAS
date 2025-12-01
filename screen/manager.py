from evdev import InputDevice, ecodes
import os
import sys
import time
import subprocess
import signal
import psutil 

# --- Costanti di configurazione ---
FB_WIDTH, FB_HEIGHT = 480, 320
TOUCHSCREEN_DEVICE = '/dev/input/event0'

# --- Variabile globale per il processo attivo ---
current_process = None

def clean_lingering_processes():
    """
    Cerca e termina processi binari che potrebbero bloccare il framebuffer.
    """
    target_processes = ['fbi', 'ffmpeg', 'yt-dlp', 'omxplayer']
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] in target_processes:
                print(f"Pulizia preventiva: termino processo orfano {proc.info['name']} (PID: {proc.info['pid']})")
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except psutil.TimeoutExpired:
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def kill_process_tree(pid):
    """
    Termina un processo e TUTTI i suoi figli ricorsivamente in modo sicuro.
    """
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return

    children = parent.children(recursive=True)
    
    for child in children:
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
            
    try:
        parent.terminate()
    except psutil.NoSuchProcess:
        pass

    gone, alive = psutil.wait_procs(children + [parent], timeout=3)
    
    for p in alive:
        try:
            print(f"Forzo kill su {p.pid}")
            p.kill()
        except psutil.NoSuchProcess:
            pass

def start_app(app_name):
    global current_process
    
    if current_process:
        print(f"Stop app corrente (PID: {current_process.pid})...")
        kill_process_tree(current_process.pid)
        current_process = None
        
    clean_lingering_processes()
    time.sleep(0.5) 

    command = []
    if app_name == 'immich':
        command = ['sudo', 'python3', 'immich.py']
    elif app_name == 'yt':
        command = ['sudo', 'python3', 'yt.py']
    elif app_name == 'rpi':
        command = ['sudo', 'python3', 'rpi.py']
    else:
        print(f"App sconosciuta: {app_name}")
        return

    print(f"--- Avvio di: {app_name} ---")
    try:
        current_process = subprocess.Popen(command)
    except Exception as e:
        print(f"ERRORE critico avvio {app_name}: {e}")

# --- Loop di ascolto ---
def listen(stato_iniziale=10):
    global current_process 
    
    stato = stato_iniziale
    
    try:
        device = InputDevice(TOUCHSCREEN_DEVICE)
    except Exception as e:
        print(f"Errore Touchscreen: {e}")
        return

    print(f"Manager avviato. In ascolto su {TOUCHSCREEN_DEVICE}...")

    try:
        abs_x_info = device.absinfo(ecodes.ABS_X)
        abs_y_info = device.absinfo(ecodes.ABS_Y)
        max_raw_x = abs_x_info.max
        max_raw_y = abs_y_info.max
    except KeyError:
        max_raw_x = 4095 
        max_raw_y = 4095
    
    center_x = FB_WIDTH // 2
    count = 0 
    
    # --- FIX: Inizializzazione variabili coordinate ---
    curr_x = 0
    curr_y = 0
    # --------------------------------------------------

    try:
        for event in device.read_loop():
            if event.type == ecodes.EV_ABS:
                if event.code == ecodes.ABS_X:
                    curr_x = event.value
                elif event.code == ecodes.ABS_Y:
                    curr_y = event.value
            
            elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH and event.value == 1:
                count += 1
                
                # Calcolo coordinate
                scaled_x = int(((max_raw_y - curr_y) / max_raw_y) * FB_WIDTH)
                scaled_y = int((curr_x / max_raw_x) * FB_HEIGHT)
                
                if count % 2 == 0:
                    print(f"Touch rilevato: Stato {stato} -> X:{scaled_x} Y:{scaled_y}")

                    nuovo_stato = stato
                    app_da_lanciare = None

                    if stato == 0: # RPI SETTINGS
                        if scaled_x < center_x: 
                             nuovo_stato = 10
                             app_da_lanciare = 'immich'

                    elif stato == 10: # IMMICH (HOME)
                        if scaled_x < center_x: # Sinistra -> YouTube
                             nuovo_stato = 20
                             app_da_lanciare = 'yt'
                        elif scaled_x > center_x: # Destra -> Settings
                             nuovo_stato = 0
                             app_da_lanciare = 'rpi'

                    elif stato == 20: # YOUTUBE
                        if scaled_x > center_x: # Destra -> Home
                             nuovo_stato = 10
                             app_da_lanciare = 'immich'
                    
                    if app_da_lanciare:
                        print(f"Cambio stato: {stato} -> {nuovo_stato} ({app_da_lanciare})")
                        stato = nuovo_stato
                        start_app(app_da_lanciare)

    except KeyboardInterrupt:
        print("\nChiusura Manager...")
    finally:
        if current_process:
             kill_process_tree(current_process.pid)
        clean_lingering_processes()

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("ERRORE: Questo script deve essere eseguito con sudo.")
        sys.exit(1)

    clean_lingering_processes()
    
    start_app('immich') 
    listen(10)
