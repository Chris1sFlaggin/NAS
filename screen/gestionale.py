#!/usr/bin/env python3
import os
import sys
import time
import subprocess
from evdev import InputDevice, ecodes

# Importa il modulo rpi.py come una libreria
# (Assicurati che rpi.py sia nella stessa cartella)
try:
    import rpi 
except ImportError:
    print("ERRORE: Impossibile importare 'rpi.py'. Assicurati che sia nella stessa cartella.")
    sys.exit(1)

# --- Configurazione del Gestionale ---

# Stato iniziale: 0 = RPI, 1 = IMMICH (Default), 2 = YT
# Iniziamo con IMMICH (schermata di apertura)
current_screen = 1 

# Stato interno per la navigazione del modulo RPI
# 0 = Dashboard, 1 = Pagina interna (es. Servizi), 2 = Sottomenu (es. Logs)
rpi_state = 0 

# Processo attivo (per Immich o YT)
active_process = None

# URL di default per il modulo YouTube
YOUTUBE_DEFAULT_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 

# Costanti dal modulo RPI (per non doverle importare tutte)
TOUCHSCREEN_DEVICE = rpi.TOUCHSCREEN_DEVICE
FB_WIDTH = rpi.FB_WIDTH
FB_HEIGHT = rpi.FB_HEIGHT

# --- Funzioni di Gestione Processi ---

def kill_active_process():
    """Termina il processo in background (Immich o YT) se è in esecuzione."""
    global active_process
    if active_process:
        print(f"-> Terminazione del processo {active_process.pid}...")
        try:
            active_process.terminate() # Invia SIGTERM
            active_process.wait(timeout=2) # Attende max 2 secondi
        except subprocess.TimeoutExpired:
            active_process.kill() # Forza la chiusura
            active_process.wait()
        except Exception as e:
            print(f"Errore durante la terminazione del processo: {e}")
        active_process = None
        
        # Pulisce lo schermo dopo aver chiuso un processo video/immagini
        try:
            rpi.draw_image_to_fb(rpi.Image.new('RGB', (FB_WIDTH, FB_HEIGHT), color=rpi.BG_COLOR))
        except Exception:
            pass # Non critico se fallisce

def start_screen(screen_index):
    """Avvia la schermata richiesta."""
    global current_screen, active_process, rpi_state
    
    # 1. Uccidi qualsiasi processo precedente
    kill_active_process()
    
    # 2. Imposta il nuovo stato
    current_screen = screen_index
    
    # 3. Avvia la nuova schermata
    if current_screen == 0:
        # --- SCHERMATA SINISTRA (RPI) ---
        print("Avvio Schermata RPI Dashboard...")
        rpi_state = 0 # Resetta lo stato interno di RPI
        rpi.print_dashboard() # Disegna la dashboard
        
    elif current_screen == 1:
        # --- SCHERMATA CENTRALE (IMMICH) ---
        print("Avvio Schermata IMMICH Slideshow...")
        # Lancia immich.py come processo separato
        try:
            active_process = subprocess.Popen(['python3', 'immich.py'])
        except FileNotFoundError:
            print("ERRORE: 'immich.py' non trovato.")
            # Disegna un errore
            img = rpi.Image.new('RGB', (FB_WIDTH, FB_HEIGHT), color=rpi.BG_COLOR)
            draw = rpi.ImageDraw.Draw(img)
            rpi.draw_header(draw, "Errore")
            draw.text((rpi.PADDING, 100), "immich.py non trovato.", fill=rpi.RED, font=rpi.get_font(rpi.FONT_PATH_REG, 18))
            rpi.draw_image_to_fb(img)
            
    elif current_screen == 2:
        # --- SCHERMATA DESTRA (YT) ---
        print(f"Avvio Schermata YT Player (URL: {YOUTUBE_DEFAULT_URL})...")
        # Lancia yt.py come processo separato con l'URL
        try:
            active_process = subprocess.Popen(['python3', 'yt.py', YOUTUBE_DEFAULT_URL])
        except FileNotFoundError:
            print("ERRORE: 'yt.py' non trovato.")
            img = rpi.Image.new('RGB', (FB_WIDTH, FB_HEIGHT), color=rpi.BG_COLOR)
            draw = rpi.ImageDraw.Draw(img)
            rpi.draw_header(draw, "Errore")
            draw.text((rpi.PADDING, 100), "yt.py non trovato.", fill=rpi.RED, font=rpi.get_font(rpi.FONT_PATH_REG, 18))
            rpi.draw_image_to_fb(img)

# --- Logica di Navigazione ---

def handle_swipe_left():
    """Gestisce uno swipe verso sinistra (va alla schermata successiva)."""
    global current_screen
    print("-> Swipe Sinistra rilevato")
    if current_screen == 0: # Da RPI -> IMMICH
        start_screen(1)
    elif current_screen == 1: # Da IMMICH -> YT
        start_screen(2)
    # Se siamo su YT (schermo 2), non facciamo nulla (siamo alla fine)

def handle_swipe_right():
    """Gestisce uno swipe verso destra (va alla schermata precedente)."""
    global current_screen
    print("-> Swipe Destra rilevato")
    if current_screen == 2: # Da YT -> IMMICH
        start_screen(1)
    elif current_screen == 1: # Da IMMICH -> RPI
        start_screen(0)
    # Se siamo su RPI (schermo 0), non facciamo nulla (siamo all'inizio)

def handle_rpi_tap(x, y):
    """Gestisce i tocchi quando la schermata RPI è attiva."""
    global rpi_state
    
    center_x = FB_WIDTH // 2
    center_y = FB_HEIGHT // 2
    
    print(f"Tocco RPI (Stato: {rpi_state}) a ({x}, {y})")

    # Logica del pulsante "Back" (presente in stato 1 e 2)
    if rpi_state > 0:
        back_btn_x = FB_WIDTH - 100 - rpi.PADDING
        back_btn_y = rpi.PADDING - 5
        if (x > back_btn_x and x < back_btn_x + 100 and
            y > back_btn_y and y < back_btn_y + 40):
            print("-> Tasto BACK (Home RPI)")
            rpi_state = 0
            rpi.print_dashboard()
            return

    # Logica specifica dello stato
    if rpi_state == 0: # Siamo sulla Dashboard
        if x >= center_x and y < center_y:      # Q3: Servizi
            print("-> RPI: Servizi")
            rpi_state = 1
            rpi.servizi()
        elif x < center_x and y < center_y:     # Q4: Storage
            print("-> RPI: Storage")
            rpi_state = 1
            rpi.memoria()
        elif x < center_x and y >= center_y:    # Q2: Logs
            print("-> RPI: Logs (Menu)")
            rpi_state = 2 # Sottomenu Logs
            rpi.logs()
        elif x >= center_x and y >= center_y:   # Q1: Prestazioni
            print("-> RPI: Prestazioni")
            rpi_state = 1
            rpi.prestazioni()
            
    elif rpi_state == 1: # Siamo in una pagina (es. Servizi, Storage...)
        # Solo il tasto BACK funziona (gestito sopra)
        pass 
        
    elif rpi_state == 2: # Siamo nel sottomenu Logs
        if x >= center_x and y < center_y:      # Q3: Nginx
            print("-> RPI: Logs Nginx")
            rpi_state = 1 # È una pagina finale
            rpi.nginx()
        elif x < center_x and y < center_y:     # Q4: Squid
            print("-> RPI: Logs Squid")
            rpi_state = 1
            rpi.squid()
        elif x < center_x and y >= center_y:    # Q2: Immich
            print("-> RPI: Logs Immich")
            rpi_state = 1
            rpi.immich()
        # Q1 è vuoto nel menu logs

def main_touch_loop():
    """Loop principale che ascolta per swipe o tocchi. (Versione con DEBUG)"""
    global rpi_state
    try:
        device = InputDevice(TOUCHSCREEN_DEVICE)
    except Exception as e:
        print(f"ERRORE: Impossibile avviare il listener del touchscreen: {e}")
        print(f"Controlla il dispositivo: {TOUCHSCREEN_DEVICE}")
        return

    print(f"Gestionale avviato. In ascolto su {device.name}...")

    # Variabili per rilevamento
    touch_down = False
    start_x_raw, start_y_raw = 0, 0
    current_x_raw, current_y_raw = 0, 0 # Traccia le coordinate correnti
    start_time = 0

    try:
        abs_x_info = device.absinfo(ecodes.ABS_X)
        abs_y_info = device.absinfo(ecodes.ABS_Y)
        max_touch_raw_x = abs_x_info.max
        max_touch_raw_y = abs_y_info.max
    except KeyError:
        max_touch_raw_x = 4095
        max_touch_raw_y = 4095
    
    if max_touch_raw_x == 0 or max_touch_raw_y == 0:
        print("Errore: Valori massimi del touchscreen non validi.")
        return
        
    # --- Costanti di calibrazione ---
    # Come da rpi.py:
    # Asse Orizzontale (X) dello schermo = Asse Y Raw (ABS_Y)
    # Asse Verticale (Y) dello schermo = Asse X Raw (ABS_X)
    
    # Soglia per lo SWIPE: Deve muoversi di almeno 1/3 dell'asse X (che è max_touch_raw_y)
    SWIPE_THRESHOLD_X_RAW = max_touch_raw_y / 3
    # Soglia per il TAP: Non deve muoversi verticalmente più di 1/4 dell'asse Y (che è max_touch_raw_x)
    SWIPE_THRESHOLD_Y_RAW = max_touch_raw_x / 4
    SWIPE_MAX_TIME = 0.5 # Max 500ms per uno swipe

    print(f"Info Touch: MaxRawX(Y)={max_touch_raw_x}, MaxRawY(X)={max_touch_raw_y}")
    print(f"Soglia Swipe X: {SWIPE_THRESHOLD_X_RAW:.0f} (basata su Y-Raw)")
    print(f"Soglia Tap Y: {SWIPE_THRESHOLD_Y_RAW:.0f} (basata su X-Raw)")
    
    try:
        for event in device.read_loop():
            
            if event.type == ecodes.EV_ABS:
                if event.code == ecodes.ABS_X:
                    current_x_raw = event.value # Questo è l'asse Y scalato
                elif event.code == ecodes.ABS_Y:
                    current_y_raw = event.value # Questo è l'asse X scalato
            
            elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
                
                if event.value == 1 and not touch_down: # Tocco Iniziato
                    touch_down = True
                    # Leggiamo le coordinate *attuali* all'inizio del tocco
                    start_x_raw = current_x_raw 
                    start_y_raw = current_y_raw
                    start_time = time.time()
                
                elif event.value == 0 and touch_down: # Tocco Rilasciato
                    touch_down = False
                    end_time = time.time()
                    
                    delta_t = end_time - start_time
                    
                    # Calcoliamo i delta *calibrati*
                    # delta_x_calib_raw usa l'asse Y raw (ABS_Y), che è invertito
                    delta_x_calib_raw = start_y_raw - current_y_raw 
                    # delta_y_calib_raw usa l'asse X raw (ABS_X)
                    delta_y_calib_raw = current_x_raw - start_x_raw 

                    # --- DEBUGGING FONDAMENTALE ---
                    print(f"--- GESTO RILASCIATO ---")
                    print(f"Tempo: {delta_t:.2f}s (Max: {SWIPE_MAX_TIME})")
                    print(f"Delta X (Swipe L/R): {delta_x_calib_raw} (Soglia: +/-{SWIPE_THRESHOLD_X_RAW:.0f})")
                    print(f"Delta Y (Tap U/D):   {delta_y_calib_raw} (Soglia: +/-{SWIPE_THRESHOLD_Y_RAW:.0f})")
                    # --- FINE DEBUGGING ---

                    # --- LOGICA DECISIONALE ---
                    is_swipe = False
                    
                    # 1. È stato abbastanza veloce?
                    if delta_t < SWIPE_MAX_TIME:
                        # 2. È uno swipe orizzontale? (Movimento X grande, Movimento Y piccolo)
                        if abs(delta_x_calib_raw) > SWIPE_THRESHOLD_X_RAW and abs(delta_y_calib_raw) < SWIPE_THRESHOLD_Y_RAW:
                            
                            # --- LOGICA CORRETTA ---
                            # Dalla calibrazione di rpi.py:
                            # max_touch_raw_y (start_y_raw) -> 0 (scaled_x) -> Sinistra
                            # 0 (current_y_raw) -> FB_WIDTH (scaled_x) -> Destra
                            
                            # Swipe da SX a DX: (start_y_raw è alto) - (current_y_raw è basso) = POSITIVO
                            # Swipe da DX a SX: (start_y_raw è basso) - (current_y_raw è alto) = NEGATIVO
                            
                            if delta_x_calib_raw > 0:
                                print(">>> AZIONE: SWIPE DESTRA (Rilevato: SX -> DX)")
                                handle_swipe_right()
                            else:
                                print(">>> AZIONE: SWIPE SINISTRA (Rilevato: DX -> SX)")
                                handle_swipe_left()
                            is_swipe = True
                            
                        # (Aggiungi qui 'elif abs(delta_y_calib_raw) > ...' se vuoi swipe verticali)
                    
                    # 3. Se non è uno swipe, è un tocco (solo per RPI)
                    if not is_swipe and current_screen == 0:
                        print(">>> AZIONE: TOCCO")
                        # Scaliamo le coordinate *finali* del rilascio
                        scaled_x = int(((max_touch_raw_y - current_y_raw) / max_touch_raw_y) * FB_WIDTH)
                        scaled_y = int((current_x_raw / max_touch_raw_x) * FB_HEIGHT)
                        
                        scaled_x = max(0, min(FB_WIDTH - 1, scaled_x))
                        scaled_y = max(0, min(FB_HEIGHT - 1, scaled_y))
                        
                        print(f"Posizione tocco: ({scaled_x}, {scaled_y})")
                        handle_rpi_tap(scaled_x, scaled_y)

    except KeyboardInterrupt:
        print("\nInterrotto dall'utente. Chiusura...")
    finally:
        kill_active_process() # Assicurati che tutto sia chiuso
        print("Gestionale terminato.")

# --- Avvio ---
if __name__ == "__main__":
    # Avvia la schermata di apertura (Immich)
    start_screen(current_screen)
    # Avvia il loop di ascolto principale
    main_touch_loop()