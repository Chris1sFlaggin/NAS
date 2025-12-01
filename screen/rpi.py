from evdev import InputDevice, ecodes
from PIL import Image, ImageDraw, ImageFont
import os
import struct
import sys
import time
import psutil
import subprocess

# --- Costanti di configurazione ---
FB_WIDTH, FB_HEIGHT = 480, 320
FRAMEBUFFER_DEVICE = '/dev/fb1'
TOUCHSCREEN_DEVICE = '/dev/input/event0'

# --- Costanti di Design (Tema "Apple Dark") ---
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

# --- Percorsi Font ---
FONT_PATH_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_PATH_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# --- Funzioni di utilità (Helpers) ---
def get_docker_logs(container_name, lines=10):
    try:
        command = ['docker', 'logs', container_name]
        
        result = subprocess.run(command, 
                              capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            if result.stdout.strip():
                return result.stdout.strip().split('\n')
            else:
                return ["(Nessun log Docker trovato)"]
        else:
            err = result.stderr.strip().split('\n')[-1] 
            return [f"Errore Docker: {err[:60]}..."]
    except FileNotFoundError:
        return ["Errore: Comando 'docker' non trovato."]
    except Exception as e:
        return [f"Eccezione Docker: {str(e)}"]
    
def get_logs(service_name, lines=10):
    try:
        if not service_name.endswith('.service'):
            service_name += '.service'
            
        command = ['journalctl', '-u', service_name, '--no-pager']

        result = subprocess.run(command, 
                              capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            if result.stdout.strip():
                return result.stdout.strip().split('\n')
            else:
                return [f"(Nessun log journal per {service_name})"]
        else:
            err = result.stderr.strip().split('\n')[-1]
            if not err: 
                 err = result.stdout.strip().split('\n')[-1]
            return [f"Errore Journal: {err[:60]}..."]
    except FileNotFoundError:
        return ["Errore: Comando 'journalctl' non trovato."]
    except Exception as e:
        return [f"Eccezione Journal: {str(e)}"]

def get_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except IOError:
        print(f"Attenzione: Font non trovato a {path}. Uso il default.")
        return ImageFont.load_default()

def draw_rounded_rectangle(draw, xy, radius, fill=None, outline=None, width=1):
    x1, y1, x2, y2 = xy
    draw.rectangle(
        (x1 + radius, y1, x2 - radius, y2),
        fill=fill, outline=outline, width=width
    )
    draw.rectangle(
        (x1, y1 + radius, x2, y2 - radius),
        fill=fill, outline=outline, width=width
    )
    draw.pieslice(
        (x1, y1, x1 + radius * 2, y1 + radius * 2),
        180, 270, fill=fill, outline=outline, width=width
    )
    draw.pieslice(
        (x2 - radius * 2, y1, x2, y1 + radius * 2),
        270, 360, fill=fill, outline=outline, width=width
    )
    draw.pieslice(
        (x1, y2 - radius * 2, x1 + radius * 2, y2),
        90, 180, fill=fill, outline=outline, width=width
    )
    draw.pieslice(
        (x2 - radius * 2, y2 - radius * 2, x2, y2),
        0, 90, fill=fill, outline=outline, width=width
    )

def rgb565(r, g, b):
    pixel = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return struct.pack("<H", pixel)

def draw_image_to_fb(img):
    img = img.rotate(180, expand=True)
    
    try:
        image_bytes = img.tobytes("raw", "RGB")
        rgb565_data_buffer = bytearray(FB_WIDTH * FB_HEIGHT * 2)
        
        idx_565 = 0
        for i in range(0, len(image_bytes), 3):
            r = image_bytes[i]
            g = image_bytes[i+1]
            b = image_bytes[i+2]
            
            packed_pixel = rgb565(r, g, b)
            rgb565_data_buffer[idx_565:idx_565+2] = packed_pixel
            idx_565 += 2

        with open(FRAMEBUFFER_DEVICE, 'wb') as fb:
            fb.write(rgb565_data_buffer)
    except Exception as e:
        print(f"Errore during writing to framebuffer: {e}")
        img.save('/tmp/fb_fallback.png')
        print("Immagine di fallback salvata in /tmp/fb_fallback.png")

def draw_header(draw, title_text, show_back_button=False):
    font_title = get_font(FONT_PATH_BOLD, 22)
    font_back = get_font(FONT_PATH_REG, 18)
    
    draw.text((PADDING, PADDING), title_text, fill=TEXT_COLOR, font=font_title)
    
    if show_back_button:
        back_btn_width = 100
        back_btn_height = 40
        back_btn_x = FB_WIDTH - back_btn_width - PADDING
        back_btn_y = PADDING - 5 
        
        draw_rounded_rectangle(
            draw, 
            (back_btn_x, back_btn_y, back_btn_x + back_btn_width, back_btn_y + back_btn_height),
            CORNER_RADIUS,
            fill=PRIMARY_COLOR
        )
        draw.text(
            (back_btn_x + 20, back_btn_y + 8), 
            "< Home", 
            fill=TEXT_COLOR, 
            font=font_back
        )

def draw_progress_bar(draw, y_pos, percent, label, value_text):
    font_label = get_font(FONT_PATH_REG, 16)
    font_value = get_font(FONT_PATH_REG, 14)

    bar_width = FB_WIDTH - (PADDING * 2)
    bar_height = 25
    bar_x = PADDING
    
    draw.text((bar_x, y_pos), label, fill=TEXT_COLOR, font=font_label)
    percent_str = f"{percent:.1f}%"
    percent_w = draw.textlength(percent_str, font=font_label)
    draw.text((FB_WIDTH - PADDING - percent_w, y_pos), percent_str, fill=PRIMARY_COLOR, font=font_label)

    y_pos += 30

    color = GREEN
    if percent > 85:
        color = RED
    elif percent > 65:
        color = YELLOW

    draw_rounded_rectangle(
        draw,
        (bar_x, y_pos, bar_x + bar_width, y_pos + bar_height),
        CORNER_RADIUS,
        fill=(50, 50, 50) 
    )
    
    if percent > 0:
        filled_width = int((percent / 100) * bar_width)
        
        if filled_width < (CORNER_RADIUS * 2):
            draw.rectangle(
                (bar_x, y_pos, bar_x + filled_width, y_pos + bar_height),
                fill=color
            )
        else:
            draw_rounded_rectangle(
                draw,
                (bar_x, y_pos, bar_x + filled_width, y_pos + bar_height),
                CORNER_RADIUS,
                fill=color
            )
        
    value_w = draw.textlength(value_text, font=font_value)
    draw.text((FB_WIDTH - PADDING - value_w, y_pos + bar_height + 8), value_text, fill=SECONDARY_COLOR, font=font_value)


# --- Schermate dell'applicazione ---
def immich():
    image = Image.new('RGB', (FB_WIDTH, FB_HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(image)
    draw_header(draw, "Logs: immich_service", show_back_button=True)

    font_log = get_font(FONT_PATH_REG, 11) 
    font_subtitle = get_font(FONT_PATH_BOLD, 14)

    y_pos = 80
    draw.text((PADDING, y_pos), "Ultime 20 righe:", fill=SECONDARY_COLOR, font=font_subtitle)
    y_pos += 30

    logs = get_docker_logs('immich_server', lines=20)
    
    line_height = 14
    for line in logs:
        clean_line = line.strip().replace('\t', ' ')
        draw.text((PADDING, y_pos), clean_line[:70], fill=TEXT_COLOR, font=font_log)
        y_pos += line_height
        if y_pos > FB_HEIGHT - PADDING:
            break 

    draw_image_to_fb(image)

def nginx():
    image = Image.new('RGB', (FB_WIDTH, FB_HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(image)
    draw_header(draw, "Logs: nginx", show_back_button=True)

    font_log = get_font(FONT_PATH_REG, 11)
    font_subtitle = get_font(FONT_PATH_BOLD, 14)

    y_pos = 80
    draw.text((PADDING, y_pos), "Ultime 20 righe:", fill=SECONDARY_COLOR, font=font_subtitle)
    y_pos += 30

    logs = get_logs('nginx', lines=20)
    
    line_height = 14
    for line in logs:
        clean_line = line.strip().replace('\t', ' ')
        draw.text((PADDING, y_pos), clean_line[:70], fill=TEXT_COLOR, font=font_log)
        y_pos += line_height
        if y_pos > FB_HEIGHT - PADDING:
            break

    draw_image_to_fb(image)

def squid():
    image = Image.new('RGB', (FB_WIDTH, FB_HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(image)
    draw_header(draw, "Logs: squid", show_back_button=True)

    font_log = get_font(FONT_PATH_REG, 11)
    font_subtitle = get_font(FONT_PATH_BOLD, 14)

    y_pos = 80
    draw.text((PADDING, y_pos), "Ultime 20 righe:", fill=SECONDARY_COLOR, font=font_subtitle)
    y_pos += 30

    logs = get_logs('squid', lines=20)
    
    line_height = 14
    for line in logs:
        clean_line = line.strip().replace('\t', ' ')
        draw.text((PADDING, y_pos), clean_line[:70], fill=TEXT_COLOR, font=font_log)
        y_pos += line_height
        if y_pos > FB_HEIGHT - PADDING:
            break

    draw_image_to_fb(image)

def memoria():
    image = Image.new('RGB', (FB_WIDTH, FB_HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(image)
    draw_header(draw, "Storage", show_back_button=True)

    def get_disk_usage(path):
        try:
            statvfs = os.statvfs(path)
            total = statvfs.f_frsize * statvfs.f_blocks
            available = statvfs.f_frsize * statvfs.f_bavail
            used = total - available
            return used, total
        except:
            return 0, 1 

    used_root, total_root = get_disk_usage('/')
    percent_root = (used_root / total_root) * 100 if total_root > 0 else 0
    text_root = f"{used_root/1024**3:.1f} GB / {total_root/1024**3:.1f} GB"
    
    used_mnt, total_mnt = get_disk_usage('/mnt/router_hdd')
    percent_mnt = (used_mnt / total_mnt) * 100 if total_mnt > 0 else 0
    text_mnt = f"{used_mnt/1024**3:.1f} GB / {total_mnt/1024**3:.1f} GB"

    used_mnt_R, total_mnt_R = get_disk_usage('/mnt/raidbox')
    percent_mnt_R = (used_mnt_R / total_mnt_R) * 100 if total_mnt_R > 0 else 0
    text_mnt_R = f"{used_mnt_R/1024**3:.1f} GB / {total_mnt_R/1024**3:.1f} GB"

    draw_progress_bar(draw, 80, percent_root, "Root (/)", text_root)
    draw_progress_bar(draw, 160, percent_mnt_R, "RAIDBOX", text_mnt_R)
    draw_progress_bar(draw, 240, percent_mnt, "ROUTER", text_mnt)

    draw_image_to_fb(image)

def servizi():
    image = Image.new('RGB', (FB_WIDTH, FB_HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(image)
    draw_header(draw, "Servizi di Sistema", show_back_button=True)

    font_service = get_font(FONT_PATH_REG, 16)
    font_docker = get_font(FONT_PATH_REG, 14)

    services = ['squid', 'nginx', 'docker', 'cron', 'ssh']
    y_pos = 80
    x_pos = PADDING + 25
    
    draw.text((PADDING, y_pos), "Servizi Systemd:", fill=SECONDARY_COLOR, font=font_service)
    y_pos += 30

    for service in services:
        try:
            status = os.system(f"systemctl is-active --quiet {service}")
            color = GREEN if status == 0 else RED
        except Exception:
            color = ORANGE
        
        draw.ellipse((x_pos - 15, y_pos + 4, x_pos - 5, y_pos + 14), fill=color)
        draw.text((x_pos, y_pos), service, fill=TEXT_COLOR, font=font_service)
        y_pos += 30

    y_pos += 10
    draw.text((PADDING, y_pos), "Container Docker:", fill=SECONDARY_COLOR, font=font_service)
    y_pos += 25
    
    try:
        result = subprocess.run(['docker', 'ps', '--format', '{{.Names}}\t{{.Status}}'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if lines and lines[0]:
                for line in lines[:4]: 
                    parts = line.split('\t')
                    name = parts[0][:20]
                    status_text = parts[1]
                    color = GREEN if 'Up' in status_text else RED
                    
                    draw.ellipse((x_pos - 15, y_pos + 3, x_pos - 5, y_pos + 13), fill=color)
                    draw.text((x_pos, y_pos), f"{name} ({status_text[:10]})", fill=TEXT_COLOR, font=font_docker)
                    y_pos += 25
            else:
                draw.text((x_pos, y_pos), "Nessun container attivo", fill=YELLOW, font=font_docker)
        else:
            draw.text((x_pos, y_pos), "Docker non disponibile", fill=RED, font=font_docker)
    except Exception as e:
        draw.text((x_pos, y_pos), "Errore controllo Docker", fill=ORANGE, font=font_docker)

    draw_image_to_fb(image)

def logs():
    image = Image.new('RGB', (FB_WIDTH, FB_HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(image)
    
    font_btn = get_font(FONT_PATH_BOLD, 20)
    
    center_x = FB_WIDTH // 2
    center_y = FB_HEIGHT // 2
    margin = 8 
    
    btn_color = (44, 44, 46) 

    q1_xy = (center_x + margin // 2, center_y + margin // 2, FB_WIDTH - PADDING, FB_HEIGHT - PADDING)
    q2_xy = (PADDING, center_y + margin // 2, center_x - margin // 2, FB_HEIGHT - PADDING)
    q3_xy = (center_x + margin // 2, PADDING, FB_WIDTH - PADDING, center_y - margin // 2)
    q4_xy = (PADDING, PADDING, center_x - margin // 2, center_y - margin // 2)

    text_y_top = (q4_xy[1] + q4_xy[3]) // 2 - (font_btn.size // 2)
    text_y_bottom = (q2_xy[1] + q2_xy[3]) // 2 - (font_btn.size // 2)

    draw_rounded_rectangle(draw, q1_xy, CORNER_RADIUS, fill=BG_COLOR)
    
    draw_rounded_rectangle(draw, q2_xy, CORNER_RADIUS, fill=btn_color)
    draw.text((q2_xy[0] + 20, text_y_bottom), "Immich", fill=TEXT_COLOR, font=font_btn)

    draw_rounded_rectangle(draw, q3_xy, CORNER_RADIUS, fill=btn_color)
    draw.text((q3_xy[0] + 20, text_y_top), "Nginx", fill=TEXT_COLOR, font=font_btn)

    draw_rounded_rectangle(draw, q4_xy, CORNER_RADIUS, fill=btn_color)
    draw.text((q4_xy[0] + 20, text_y_top), "Squid", fill=TEXT_COLOR, font=font_btn)

    draw_image_to_fb(image)

def prestazioni():
    image = Image.new('RGB', (FB_WIDTH, FB_HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(image)
    draw_header(draw, "Prestazioni", show_back_button=True)
    
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    draw_progress_bar(draw, 80, cpu_percent, "Utilizzo CPU", f"{cpu_percent:.1f}%")
    
    # RAM
    mem = psutil.virtual_memory()
    mem_percent = mem.percent
    mem_text = f"{mem.used/1024**3:.1f} GB / {mem.total/1024**3:.1f} GB"
    draw_progress_bar(draw, 160, mem_percent, "Utilizzo RAM", mem_text)
    
    # SWAP totale
    swap = psutil.swap_memory()
    swap_percent = swap.percent
    swap_text = f"{swap.used/1024**3:.1f} GB / {swap.total/1024**3:.1f} GB"
    draw_progress_bar(draw, 240, swap_percent, "Utilizzo SWAP", swap_text)
    
    draw_image_to_fb(image)
    
def print_dashboard():
    image = Image.new('RGB', (FB_WIDTH, FB_HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(image)
    
    font_btn = get_font(FONT_PATH_BOLD, 20)
    
    center_x = FB_WIDTH // 2
    center_y = FB_HEIGHT // 2
    margin = 8 
    
    btn_color = (44, 44, 46) 

    q1_xy = (center_x + margin // 2, center_y + margin // 2, FB_WIDTH - PADDING, FB_HEIGHT - PADDING)
    q2_xy = (PADDING, center_y + margin // 2, center_x - margin // 2, FB_HEIGHT - PADDING)
    q3_xy = (center_x + margin // 2, PADDING, FB_WIDTH - PADDING, center_y - margin // 2)
    q4_xy = (PADDING, PADDING, center_x - margin // 2, center_y - margin // 2)

    text_y_top = (q4_xy[1] + q4_xy[3]) // 2 - (font_btn.size // 2)
    text_y_bottom = (q2_xy[1] + q2_xy[3]) // 2 - (font_btn.size // 2)

    draw_rounded_rectangle(draw, q1_xy, CORNER_RADIUS, fill=btn_color)
    draw.text((q1_xy[0] + 20, text_y_bottom), "Prestazioni", fill=TEXT_COLOR, font=font_btn)
    
    draw_rounded_rectangle(draw, q2_xy, CORNER_RADIUS, fill=btn_color)
    draw.text((q2_xy[0] + 20, text_y_bottom), "Logs", fill=TEXT_COLOR, font=font_btn)

    draw_rounded_rectangle(draw, q3_xy, CORNER_RADIUS, fill=btn_color)
    draw.text((q3_xy[0] + 20, text_y_top), "Servizi", fill=TEXT_COLOR, font=font_btn)

    draw_rounded_rectangle(draw, q4_xy, CORNER_RADIUS, fill=btn_color)
    draw.text((q4_xy[0] + 20, text_y_top), "Storage", fill=TEXT_COLOR, font=font_btn)

    draw_image_to_fb(image)


def listen_touchscreen(stato = 0):
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
                        
                        if scaled_x >= center_x and scaled_y < center_y:
                                print("-> LOGS")
                                stato = 2
                                logs()
                        elif scaled_x < center_x and scaled_y < center_y:
                                print("-> PRESTAZIONI")
                                stato = 1
                                prestazioni()
                        elif scaled_x < center_x and scaled_y >= center_y:
                                print("-> SERVIZI")
                                stato = 1
                                servizi()
                        elif scaled_x >= center_x and scaled_y >= center_y:
                                print("-> MEMORIA")
                                stato = 1
                                memoria()
                                
                    elif stato == 1: 
                        
                        if scaled_x >= center_x and scaled_y >= center_y:
                                print("-> Tasto BACK (Home)")
                                stato = 0
                                print_dashboard()

                    elif stato == 2: 
                        
                        if scaled_x >= center_x and scaled_y < center_y:
                                print("-> IMMICH")
                                stato = 1
                                immich()
                        elif scaled_x < center_x and scaled_y >= center_y:
                                print("-> NGINX")
                                stato = 1
                                nginx()
                        elif scaled_x >= center_x and scaled_y >= center_y:
                                print("-> SQUID")
                                stato = 1
                                squid()

    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.")

def main():
    if sys.platform != 'linux':
        print("Questo script è progettato per sistemi Linux.")

    stato = 0
    print_dashboard()
    listen_touchscreen(stato)

if __name__ == "__main__":
    main()
