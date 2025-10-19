import psutil
import subprocess
from PIL import Image, ImageDraw, ImageFont
import time

# ---------------- CONFIGURAZIONE ----------------
SCREEN_WIDTH = 320
SCREEN_HEIGHT = 240
BACKGROUND_IMG = "sfondo.jpg"
OUTPUT_IMG = "dashboard.png"
FPS = 0.2

# Colori neon
CYAN = (0, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
DARK_GRAY = (16, 16, 16)
BLACK = (0, 0, 0)

TEXT_OFFSET = 5
LINE_HEIGHT = 18
BAR_HEIGHT = 5

# Font
try:
    font = ImageFont.truetype("Courier.ttf", 16)
except IOError:
    font = ImageFont.load_default()

# ---------------- FUNZIONI ----------------
def check_service(name):
    """Check service systemctl"""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.stdout.decode().strip() == "active"
    except Exception:
        return False

def check_immich_container():
    """Check if Immich docker container is up"""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=immich", "--filter", "status=running", "-q"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return bool(result.stdout.decode().strip())
    except Exception:
        return False

def get_stats():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    nginx = check_service("nginx")
    squid = check_service("squid")
    immich = check_immich_container()
    return cpu, ram, disk, nginx, squid, immich

# ---------------- CREAZIONE DASHBOARD ----------------
def create_dashboard_image():
    # Carica sfondo
    try:
        bg = Image.open(BACKGROUND_IMG).resize((SCREEN_WIDTH, SCREEN_HEIGHT))
    except FileNotFoundError:
        bg = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), BLACK)

    draw = ImageDraw.Draw(bg)

    # Statistiche e stato servizi
    cpu, ram, disk, nginx, squid, immich = get_stats()

    stats_text = [
        ("CPU", cpu),
        ("RAM", ram),
        ("DISK", disk),
        ("Nginx", nginx),
        ("Squid", squid),
        ("Immich", immich)
    ]

    # Dimensione box
    box_width = 150
    box_height = LINE_HEIGHT * len(stats_text) + TEXT_OFFSET * 2 + BAR_HEIGHT * len(stats_text)
    box_x0 = SCREEN_WIDTH - box_width - TEXT_OFFSET
    box_y0 = SCREEN_HEIGHT - box_height - TEXT_OFFSET
    box_x1 = SCREEN_WIDTH - TEXT_OFFSET
    box_y1 = SCREEN_HEIGHT - TEXT_OFFSET

    # Box leggermente sfumato per effetto glow
    box_overlay = Image.new("RGB", (box_width, box_height), DARK_GRAY)
    bg.paste(box_overlay, (box_x0, box_y0))

    # Scrive testo neon e barre sotto ogni valore
    y_text = box_y0 + TEXT_OFFSET
    for label, value in stats_text:
        # Determina colore
        if isinstance(value, bool):
            color = GREEN if value else RED
            display_text = f"{label}: {'ON' if value else 'OFF'}"
            bar_length = 0  # nessuna barra per i servizi booleani
        else:
            color = CYAN
            display_text = f"{label}: {value:.1f}%"
            bar_length = int((box_width - 2 * TEXT_OFFSET) * value / 100)

        # Disegna testo
        draw.text((box_x0 + TEXT_OFFSET, y_text), display_text, font=font, fill=color)

        # Disegna barra sotto il testo se necessario
        if bar_length > 0:
            bar_y0 = y_text + LINE_HEIGHT
            bar_y1 = bar_y0 + BAR_HEIGHT
            bar_x0 = box_x0 + TEXT_OFFSET
            bar_x1 = bar_x0 + bar_length
            draw.rectangle([bar_x0, bar_y0, bar_x1, bar_y1], fill=CYAN)

        y_text += LINE_HEIGHT + BAR_HEIGHT  # spazio per barra

    # Salva immagine
    bg = bg.rotate(180)
    bg.save(OUTPUT_IMG)
    
    # Esegui comando fbi per mostrare l'immagine
    try:
        subprocess.run(["sudo", "fbi", "-T", "1", "-d", "/dev/fb1", "-noverbose", "-a", OUTPUT_IMG], 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception:
        pass  # Ignora errori del comando fbi

# ---------------- LOOP PRINCIPALE ----------------
if __name__ == "__main__":
    while True:
        create_dashboard_image()
        time.sleep(1 / FPS)
