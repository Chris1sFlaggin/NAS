#!/usr/bin/env python3
import subprocess
import os
import sys
import numpy as np

# La risoluzione del tuo schermo TTY (adatta questi valori)
# *** AGGIORNATO ALLA RISOLUZIONE 480x320 del display mhs35-show ***
FB_WIDTH = 480
FB_HEIGHT = 320

# Formato pixel 16-bit (usato spesso per display embedded)
# CAMBIO: Inversione dei canali Rosso e Blu per correggere l'errore BGR -> RGB
PIXEL_FORMAT = "rgb565" # RGB565 (Rosso-Verde-Blu, 16 bit)
BYTES_PER_PIXEL = 2      # 2 byte per pixel (16 bit)

# --- Funzioni ---

def get_youtube_stream_url(youtube_url):
    """Usa yt-dlp per ottenere l'URL diretto del flusso video."""
    print("-> Ottenimento dell'URL di streaming con yt-dlp...")
    try:
        # Usiamo il formato 'bestvideo' per ottenere il flusso diretto
        cmd = ['yt-dlp', '-f', 'bestvideo', '-g', youtube_url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Errore nell'esecuzione di yt-dlp: {e.stderr}", file=sys.stderr)
        sys.exit(1)

def play_video_to_framebuffer(stream_url):
    """Decodifica il video con ffmpeg e scrive su /dev/fb1."""
    print(f"-> Apertura del framebuffer {FRAMEBUFFER_DEV}...")
    fb = None # Inizializza a None per gestione errori

    try:
        fb = os.open(FRAMEBUFFER_DEV, os.O_WRONLY)
    except OSError as e:
        print(f"ERRORE: Impossibile aprire {FRAMEBUFFER_DEV}. Controlla i permessi: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"-> Avvio della decodifica con ffmpeg...")

    # Costruisce la stringa dei filtri video per ffmpeg
    # 1. Scala alla risoluzione del framebuffer (480x320)
    # 2. Corregge i livelli di colore (in_range=mpeg) per aumentare il contrasto e scurendo il nero
    # 3. Ruota di 180 gradi (transpose=2,transpose=2)
    video_filters = f'scale={FB_WIDTH}:{FB_HEIGHT}:in_range=mpeg,transpose=2,transpose=2'

    # Comando ffmpeg: legge dall'URL, decodifica, scala, ruota e formatta i pixel
    ffmpeg_cmd = [
        'ffmpeg',
        '-i', stream_url,
        '-vf', video_filters, # Applica i filtri combinati
        '-f', 'rawvideo',
        '-pix_fmt', PIXEL_FORMAT, # Usa il formato (rgb565)
        '-s', f'{FB_WIDTH}x{FB_HEIGHT}',
        '-',  # Output su stdout (pipe)
    ]

    ffmpeg_proc = None # Inizializza a None

    try:
        # bufsize è impostato su dimensione frame o più per una lettura efficiente
        frame_size = FB_WIDTH * FB_HEIGHT * BYTES_PER_PIXEL
        print(f"-> Streaming a {FB_WIDTH}x{FB_HEIGHT} con {PIXEL_FORMAT} (dimensione frame: {frame_size} bytes)...")

        ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=frame_size)

        while True:
            # Legge un frame completo dal pipe di ffmpeg
            raw_frame = ffmpeg_proc.stdout.read(frame_size)

            if not raw_frame or len(raw_frame) != frame_size:
                # Se il pipe si chiude o non abbiamo letto un frame completo
                break

            # Scrive il frame direttamente sul framebuffer
            os.lseek(fb, 0, os.SEEK_SET) # Torna all'inizio del buffer
            os.write(fb, raw_frame)

    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.")
    except Exception as e:
        print(f"Errore durante lo streaming: {e}", file=sys.stderr)
    finally:
        if ffmpeg_proc and ffmpeg_proc.poll() is None:
            # Termina solo se il processo ffmpeg è ancora in esecuzione
            ffmpeg_proc.terminate()
            ffmpeg_proc.wait()
        if fb:
            os.close(fb)
            print("Fatto. Framebuffer chiuso.")

