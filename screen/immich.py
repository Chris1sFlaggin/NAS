import os
import subprocess
import time
import itertools
import sys
import tempfile
from PIL import Image

# --- CONFIGURAZIONE ---
ROOT_SCAN_DIRECTORY = "/mnt/raidbox/library/library/43b4b13a-4027-4270-9b39-a0cf27ad1641/2025/"

FBI_COMMAND = "fbi"

FBI_ARGS = ["-a", "-T", "1", "-d", "/dev/fb1"]

DELAY_BETWEEN_ASSETS = 120

ROTATED_IMAGE_PATH = os.path.join(tempfile.gettempdir(), "rotated_asset.png")

PHOTO_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.tiff', '.heic']

# --- LOGICA DELLO SCRIPT ---
def find_subdirectories_with_media(root_dir):
    """Trova tutte le sottodirectory che contengono almeno un file FOTO e mappa i loro contenuti."""
    all_media_lists = {}
    
    for subdir_name in os.listdir(root_dir):
        subdir_path = os.path.join(root_dir, subdir_name)
        
        if not os.path.isdir(subdir_path):
            continue
            
        photo_files = []
        for filename in os.listdir(subdir_path):
            filepath = os.path.join(subdir_path, filename)
            
            if not os.path.isfile(filepath):
                continue

            ext = os.path.splitext(filename)[1].lower()
            
            if ext in PHOTO_EXTENSIONS:
                photo_files.append((filepath, "photo", subdir_name))
        
        if photo_files:
            photo_files.sort(key=lambda x: x[0])
            all_media_lists[subdir_name] = photo_files
            
    return all_media_lists


def run_viewer(file_path, directory_name):
    """Esegue fbi per visualizzare la foto, applicando prima la rotazione di 180°."""
    
    print(f"\n--- Visualizzazione FOTO da [{directory_name}]: {os.path.basename(file_path)} ---", file=sys.stderr)
    
    final_path = file_path
    
    # --- GESTIONE ROTAZIONE IMMAGINI (PIL, salva su percorso fisso) ---
    try:
        image = Image.open(file_path)
        rotated_image = image.rotate(180) 
        rotated_image.save(ROTATED_IMAGE_PATH)
        
        final_path = ROTATED_IMAGE_PATH 
        print(f"File ruotato salvato in: {ROTATED_IMAGE_PATH}", file=sys.stderr)

    except Exception as e:
        print(f"ERRORE PIL/Rotazione Immagine. Visualizzazione dell'originale. Errore: {e}", file=sys.stderr)
        final_path = file_path
            
    # --- ESECUZIONE FBI ---
    full_command = [FBI_COMMAND] + FBI_ARGS + [final_path]
    print(f"Esecuzione: {' '.join(full_command)}", file=sys.stderr)
    
    try:
        subprocess.run(full_command)
        
    except FileNotFoundError:
        print(f"ERRORE: Comando '{FBI_COMMAND}' non trovato. Assicurati che fbi sia installato.", file=sys.stderr)
    except Exception as e:
        print(f"ERRORE durante l'esecuzione del visualizzatore fbi: {e}", file=sys.stderr)

    print(f"\nPremi 'q' in fbi per passare al prossimo asset. In pausa per {DELAY_BETWEEN_ASSETS} secondi...", file=sys.stderr)
         
    time.sleep(DELAY_BETWEEN_ASSETS)


def main():
    if not os.path.isdir(ROOT_SCAN_DIRECTORY):
        print(f"ERRORE: La directory radice non esiste: {ROOT_SCAN_DIRECTORY}", file=sys.stderr)
        print("Aggiorna la variabile ROOT_SCAN_DIRECTORY con un percorso valido.", file=sys.stderr)
        return

    directory_media_map = find_subdirectories_with_media(ROOT_SCAN_DIRECTORY)
    
    if not directory_media_map:
        print(f"Nessuna sottodirectory con foto trovate in: {ROOT_SCAN_DIRECTORY}", file=sys.stderr)
        return

    print(f"Trovate {len(directory_media_map)} sottodirectory con foto. Inizio visualizzazione a rotazione infinita...", file=sys.stderr)

    cyclic_iterators = {
        dir_name: itertools.cycle(media_list) 
        for dir_name, media_list in directory_media_map.items()
    }

    directory_cycler = itertools.cycle(cyclic_iterators.keys())
    
    while True:
        current_dir_name = next(directory_cycler)
        current_iterator = cyclic_iterators[current_dir_name]
        
        try:
            file_path, _, subdir_name = next(current_iterator) 
            
            run_viewer(file_path, subdir_name)
                
        except Exception as e:
            print(f"ERRORE critico durante il ciclo: {e}. Riavvio del ciclo di rotazione.", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    print("ATTENZIONE: Questo script chiama fbi e deve essere eseguito sulla console TTY.", file=sys.stderr)
    print("ATTENZIONE: Per la rotazione delle foto è richiesta la libreria PIL/Pillow. Installala con: 'pip install Pillow'.", file=sys.stderr)
    print("Potrebbe richiedere 'sudo' se non si dispone dei permessi per i dispositivi framebuffer.", file=sys.stderr)
    main()