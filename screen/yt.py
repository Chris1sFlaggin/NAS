#!/usr/bin/env python3
import subprocess
import os
import sys
import numpy as np

NUM_VIDS = 1
VIDEO_URL = ["https://www.youtube.com/watch?v=SDd3OkIljEA"]
FRAMEBUFFER_DEV = "/dev/fb1"

FB_WIDTH = 480
FB_HEIGHT = 320

PIXEL_FORMAT = "rgb565" 
BYTES_PER_PIXEL = 2      

# --- Funzioni ---

def get_youtube_stream_url(youtube_url):
    """Usa yt-dlp per ottenere l'URL diretto del flusso video."""
    print("-> Ottenimento dell'URL di streaming con yt-dlp...")
    try:
        cmd = ['yt-dlp', '-f', 'bestvideo', '-g', youtube_url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Errore nell'esecuzione di yt-dlp: {e.stderr}", file=sys.stderr)
        sys.exit(1)

def play_video_to_framebuffer(stream_url):
    """Decodifica il video con ffmpeg e scrive su /dev/fb1."""
    print(f"-> Apertura del framebuffer {FRAMEBUFFER_DEV}...")
    fb = None 

    try:
        fb = os.open(FRAMEBUFFER_DEV, os.O_WRONLY)
    except OSError as e:
        print(f"ERRORE: Impossibile aprire {FRAMEBUFFER_DEV}. Controlla i permessi: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"-> Avvio della decodifica con ffmpeg...")

    video_filters = f'scale={FB_WIDTH}:{FB_HEIGHT}:in_range=mpeg,transpose=2,transpose=2'

    ffmpeg_cmd = [
        'ffmpeg',
        '-i', stream_url,
        '-vf', video_filters, 
        '-f', 'rawvideo',
        '-pix_fmt', PIXEL_FORMAT, 
        '-s', f'{FB_WIDTH}x{FB_HEIGHT}',
        '-',  
    ]

    ffmpeg_proc = None 

    try:
        frame_size = FB_WIDTH * FB_HEIGHT * BYTES_PER_PIXEL
        print(f"-> Streaming a {FB_WIDTH}x{FB_HEIGHT} con {PIXEL_FORMAT} (dimensione frame: {frame_size} bytes)...")

        ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=frame_size)

        while True:
            raw_frame = ffmpeg_proc.stdout.read(frame_size)

            if not raw_frame or len(raw_frame) != frame_size:
                break

            os.lseek(fb, 0, os.SEEK_SET) 
            os.write(fb, raw_frame)

    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.")
    except Exception as e:
        print(f"Errore durante lo streaming: {e}", file=sys.stderr)
    finally:
        if ffmpeg_proc and ffmpeg_proc.poll() is None:
            ffmpeg_proc.terminate()
            ffmpeg_proc.wait()
        if fb:
            os.close(fb)
            print("Fatto. Framebuffer chiuso.")

# --- Esecuzione principale ---

if __name__ == "__main__":
    if not os.path.exists(FRAMEBUFFER_DEV):
        print(f"Errore: Il dispositivo framebuffer {FRAMEBUFFER_DEV} non esiste.", file=sys.stderr)
        sys.exit(1)

    stream_url = get_youtube_stream_url(VIDEO_URL)

    play_video_to_framebuffer(stream_url)
