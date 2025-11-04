from flask import Flask, render_template, render_template_string, request, jsonify, redirect, url_for
import os
import subprocess
import signal
import psutil
from threading import Thread
import sys
import time
from waitress import serve # <-- Aggiunto Waitress

app = Flask(__name__)

# Dizionario per tenere traccia dei processi attivi
active_processes = {}

# --- Nomi degli script per il telecomando ---
# Assicurati che questi nomi corrispondano ai tuoi file .py
SCRIPT_YOUTUBE = 'youtube.py'
SCRIPT_IMMICH = 'immich.py'
SCRIPT_RPI = 'rpi.py' # <-- Aggiunto RPI


def get_scripts():
    """Ottiene tutti i file .py nella cartella corrente"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    scripts = []
    # --- Correzione: rimosso "in" doppio ---
    for file in os.listdir(current_dir):
        if file.endswith('.py') and file != os.path.basename(__file__):
            scripts.append(file)
    return scripts

def is_process_running(pid):
    """Verifica se un processo è ancora attivo"""
    try:
        return psutil.pid_exists(pid)
    except psutil.NoSuchProcess:
        return False
    except Exception as e:
        print(f"Errore in is_process_running: {e}")
        return False

# --- NUOVA ROUTE: Il telecomando (Home Page) ---
@app.route('/')
def telecomando():
    # Serve il nuovo template del telecomando
    return render_template('telecomando.html')

# --- NUOVA ROUTE: Pagina Impostazioni (la vecchia home) ---
@app.route('/settings')
def index():
    scripts = get_scripts()
    for script in list(active_processes.keys()):
        process_data = active_processes[script]
        if not is_process_running(process_data['pid']):
            print(f"Il processo per {script} (PID: {process_data['pid']}) non è più in esecuzione. Rimuovo.")
            del active_processes[script]
    
    # Serve il template 'index.html' (la vecchia lista)
    return render_template('index.html', scripts=scripts, active_processes=active_processes)

# --- NUOVA ROUTE: Per il polling dello stato ---
@app.route('/status')
def status():
    """Restituisce i nomi degli script attualmente in esecuzione."""
    # Aggiorna la lista prima di restituirla
    for script in list(active_processes.keys()):
        if not is_process_running(active_processes[script]['pid']):
            del active_processes[script]
            
    active_script_names = list(active_processes.keys())
    return jsonify({'active_scripts': active_script_names})


@app.route('/start/<script>')
def start_script(script):
    if script in active_processes:
        return jsonify({'status': 'error', 'message': 'Script già in esecuzione'})
    
    try:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script)
        
        process = subprocess.Popen(
            ['sudo', sys.executable, script_path], 
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        time.sleep(0.5) 
        poll_status = process.poll()

        if poll_status is not None:
            stdout, stderr = process.communicate() 
            error_message = f"Lo script {script} è terminato immediatamente (Codice: {poll_status}).\n--- ERRORE ---\n{stderr}\n--- OUTPUT ---\n{stdout}"
            print(error_message)
            return jsonify({'status': 'error', 'message': f"Script {script} fallito all'avvio. Errore: {stderr.strip()}"})
        
        active_processes[script] = {
            'pid': process.pid,
            'process': process
        }
        print(f"Script {script} avviato con PID: {process.pid}")
        return jsonify({'status': 'success', 'message': f'Script {script} avviato (PID: {process.pid})'})
    
    except Exception as e:
        print(f"Errore in start_script: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/stop/<script>')
def stop_script(script):
    if script not in active_processes:
        return jsonify({'status': 'error', 'message': 'Script non in esecuzione'})
    
    try:
        pid_to_kill = active_processes[script]['pid']
        print(f"Tentativo di fermare lo script {script} con PID (sudo): {pid_to_kill}")
        
        subprocess.run(['sudo', '/usr/bin/kill', '-s', 'SIGTERM', str(pid_to_kill)], check=False)
        time.sleep(2) 
        
        if is_process_running(pid_to_kill):
            print(f"Processo {pid_to_kill} non ha terminato, provo con SIGKILL.")
            subprocess.run(['sudo', '/usr/bin/kill', '-s', 'SIGKILL', str(pid_to_kill)], check=False)
        else:
            print(f"Processo {pid_to_kill} terminato con successo.")
        
        del active_processes[script]
        return jsonify({'status': 'success', 'message': f'Script {script} fermato'})
    except Exception as e:
        print(f"Errore in stop_script: {e}")
        if script in active_processes:
            del active_processes[script]
        return jsonify({'status': 'success', 'message': f'Script {script} fermato (o già terminato).'})

if __name__ == '__main__':
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    os.makedirs(template_dir, exist_ok=True)
    
    # --- Template #1: index.html (la vecchia lista, ora Impostazioni) ---
    template_path_index = os.path.join(template_dir, 'index.html')
    html_template_index = '''
<!DOCTYPE html>
<html>
<head>
    <title>Gestionale Script - Impostazioni</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; 
        }
        /* Stile per il box di errore */
        #error-message {
            white-space: pre-wrap; /* Per mostrare gli errori su più righe */
        }
    </style>
</head>
<body class="bg-gray-100 text-gray-900 p-5">
    <div class="max-w-3xl mx-auto bg-white p-6 rounded-lg shadow-lg">
        <a href="/" class="text-blue-500 hover:underline">&larr; Torna al Telecomando</a>
        <h1 class="text-3xl font-bold text-gray-800 mt-4 mb-6">⚙️ Impostazioni Script</h1>

        <!-- Area per i messaggi di errore -->
        <div id="error-message" class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg relative mb-6 hidden"></div>
        
        {% if not scripts %}
        <div class="border-l-4 border-yellow-400 bg-yellow-50 p-4 rounded-md">
            <p>Nessuno script .py trovato in questa cartella (a parte gestionale.py).</p>
        </div>
        {% endif %}

        {% for script in scripts %}
        <div class="border border-gray-200 rounded-lg p-5 mb-4 {% if script in active_processes %}bg-blue-50 border-l-4 border-blue-500{% else %}bg-gray-50 border-l-4 border-gray-400{% endif %}">
            <h3 class="text-xl font-semibold text-gray-700">📄 {{ script }}</h3>
            <p class="my-3">Stato: 
                {% if script in active_processes %}
                    <span class="inline-block bg-green-100 text-green-800 text-sm font-medium px-3 py-1 rounded-full">✅ In esecuzione (PID: {{ active_processes[script]['pid'] }})</span>
                {% else %}
                    <span class="inline-block bg-red-100 text-red-800 text-sm font-medium px-3 py-1 rounded-full">❌ Fermo</span>
                {% endif %}
            </p>
            
            {% if script not in active_processes %}
                <button class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-lg shadow transition duration-200" onclick="controlScript('{{ script }}', 'start')">▶️ Avvia</button>
            {% else %}
                <button class="bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-4 rounded-lg shadow transition duration-200" onclick="controlScript('{{ script }}', 'stop')">⏹️ Ferma</button>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <script>
        function controlScript(script, action) {
            const errorDiv = document.getElementById('error-message');
            errorDiv.innerText = '';
            errorDiv.style.display = 'none';
            document.querySelectorAll('button').forEach(btn => btn.disabled = true);

            fetch(`/${action}/${script}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        location.reload();
                    } else {
                        showError(data.message);
                        document.querySelectorAll('button').forEach(btn => btn.disabled = false);
                    }
                })
                .catch(error => {
                    showError(error.message);
                    document.querySelectorAll('button').forEach(btn => btn.disabled = false);
                });
        }
        function showError(message) {
            const errorDiv = document.getElementById('error-message');
            errorDiv.innerText = 'Errore: ' + message;
            errorDiv.style.display = 'block';
        }
    </script>
</body>
</html>
    '''
    with open(template_path_index, 'w', encoding='utf-8') as f:
        f.write(html_template_index)
    print(f"Template Impostazioni scritto in {template_path_index}")

    # --- Template #2: telecomando.html (la nuova Home Page) ---
    template_path_remote = os.path.join(template_dir, 'telecomando.html')
    html_template_remote = f'''
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Telecomando</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        /* Per rimuovere il 'tap highlight' blu su mobile */
        * {{
            -webkit-tap-highlight-color: transparent;
        }}
        body, html {{
            height: 100%;
            overflow: hidden; /* Niente scrolling */
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
        }}
        /* Effetto pressione */
        .remote-btn:active {{
            transform: scale(0.97);
            filter: brightness(0.8);
        }}
        /* Stile per i loghi */
        .logo {{
            height: 40px; /* Altezza fissa per i loghi */
            width: auto;
            object-fit: contain;
        }}
        .logo.youtube {{
            height: 35px; /* Modificato per SVG */
            fill: currentColor; /* Per SVG bianco */
        }}
        .logo.settings {{
            filter: invert(1); /* Rende l'SVG del gear bianco */
            height: 35px;
        }}
        /* Stile per lo stato 'running' */
        .remote-btn.running {{
            background-color: #1a3a2a; /* Verde scuro */
            border-color: #22c55e; /* Bordo verde */
            color: #d1fae5;
        }}
        .remote-btn.running:hover {{
            background-color: #1e4b33;
        }}
        /* Stile per lo stato 'stopped' (default) */
        .remote-btn {{
            background-color: #262626; /* Grigio scuro */
            border-color: #404040;
            color: #d4d4d4;
        }}
        .remote-btn:hover {{
            background-color: #3f3f46;
        }}
    </style>
</head>
<body class="bg-black text-gray-300 h-screen overflow-hidden flex flex-col">

    <!-- Header: Pulsante Accensione e Stato -->
    <header class="flex justify-between items-center p-5">
        <div class="text-3xl text-red-500 opacity-70">
            ⏻
        </div>
        <div id="status-light" class="w-5 h-5 rounded-full bg-red-600 shadow-md transition-colors duration-300"></div>
    </header>

    <!-- Area Messaggi di Errore -->
    <div id="error-message" class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg relative m-4 hidden" style="white-space: pre-wrap;"></div>

    <!-- Pulsanti Principali -->
    <main class="flex-grow flex flex-col justify-center items-center p-6 space-y-6">

        <!-- Pulsante YOUTUBE -->
        <button id="btn-youtube" class="remote-btn w-full max-w-md p-6 border-2 rounded-2xl flex items-center justify-between shadow-lg transition-all duration-150">
            <!-- LOGO YOUTUBE INCORPORATO -->
            <svg class="logo youtube" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 20">
              <path d="M27.347 3.09C27.02 1.86 26.02 0.91 24.85 0.62C22.67 0 14 0 14 0S5.33 0 3.15 0.62C1.98 0.91 0.98 1.86 0.653 3.09C0 5.38 0 10 0 10S0 14.62 0.653 16.91C0.98 18.14 1.98 19.09 3.15 19.38C5.33 20 14 20 14 20S22.67 20 24.85 19.38C26.02 19.09 27.02 18.14 27.347 16.91C28 14.62 28 10 28 10S28 5.38 27.347 3.09ZM11.2 14.28V5.72L18.48 10L11.2 14.28Z"/>
            </svg>
            <span id="label-youtube" class="text-xl font-semibold">YouTube</span>
            <div class="w-10"></div> <!-- Spacer -->
        </button>

        <!-- Pulsante IMMICH -->
        <button id="btn-immich" class="remote-btn w-full max-w-md p-6 border-2 rounded-2xl flex items-center justify-between shadow-lg transition-all duration-150">
            <!-- LOGO IMMICH INCORPORATO (senza background) -->
            <svg class="logo" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="140 130 260 270">
                <path d="M379.031 391.266C376.101 394.04 372.43 395.422 368.016 395.422C363.602 395.422 359.93 394.04 356.999 391.266C354.069 388.492 352.604 384.984 352.604 380.742C352.604 376.5 354.069 372.992 356.999 370.219C359.93 367.445 363.602 366.055 368.016 366.055C372.43 366.055 376.101 367.445 379.031 370.219C381.961 372.992 383.427 376.5 383.427 380.742C383.427 384.984 381.961 388.492 379.031 391.266ZM393.176 342.344H342.848V131.953H393.176V342.344Z"/>
                <path d="M266.048 201.203H215.719V131.953H266.048V201.203Z"/>
                <path d="M289.445 391.266C286.516 394.04 282.844 395.422 278.43 395.422C274.016 395.422 270.344 394.04 267.414 391.266C264.484 388.492 263.02 384.984 263.02 380.742C263.02 376.5 264.484 372.992 267.414 370.219C270.344 367.445 274.016 366.055 278.43 366.055C282.844 366.055 286.516 367.445 289.445 370.219C292.375 372.992 293.84 376.5 293.84 380.742C293.84 384.984 292.375 388.492 289.445 391.266ZM303.591 342.344H253.262V242.609H303.591V342.344Z"/>
                <path d="M179.888 391.266C176.958 394.04 173.286 395.422 168.872 395.422C164.458 395.422 160.786 394.04 157.856 391.266C154.926 388.492 153.461 384.984 153.461 380.742C153.461 376.5 154.926 372.992 157.856 370.219C160.786 367.445 164.458 366.055 168.872 366.055C173.286 366.055 176.958 367.445 179.888 370.219C182.817 372.992 184.282 376.5 184.282 380.742C184.282 384.984 182.817 388.492 179.888 391.266ZM194.029 342.344H143.7V131.953H194.029V342.344Z"/>
            </svg>
            <span id="label-immich" class="text-xl font-semibold">Immich</span>
            <div class="w-10"></div> <!-- Spacer -->
        </button>

        <!-- Pulsante IMPOSTAZIONI (ora controlla RPI.PY) -->
        <button id="btn-settings" class="remote-btn w-full max-w-md p-6 border-2 rounded-2xl flex items-center justify-between shadow-lg transition-all duration-150">
             <!-- SVG Gear Icon (bianco) -->
            <svg class="logo settings" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 16 16">
              <path d="M8 4.754a3.246 3.246 0 1 0 0 6.492 3.246 3.246 0 0 0 0-6.492zM5.754 8a2.246 2.246 0 1 1 4.492 0 2.246 2.246 0 0 1-4.492 0z"/>
              <path d="M9.796 1.343c-.527-1.79-3.065-1.79-3.592 0l-.094.319a.873.873 0 0 1-1.255.52l-.292-.16c-1.64-.892-3.433.902-2.54 2.541l.159.292a.873.873 0 0 1-.52 1.255l-.319.094c-1.79.527-1.79 3.065 0 3.592l.319.094a.873.873 0 0 1 .52 1.255l-.16.292c-.892 1.64.901 3.434 2.541 2.54l.292-.159a.873.873 0 0 1 1.255.52l.094.319c.527 1.79 3.065 1.79 3.592 0l.094-.319a.873.873 0 0 1 1.255-.52l.292.16c1.64.892 3.433-.902 2.54-2.541l-.159-.292a.873.873 0 0 1 .52-1.255l.319-.094c-1.79-.527-1.79-3.065 0-3.592l-.319-.094a.873.873 0 0 1-.52-1.255l.16-.292c.892-1.64-.901-3.434-2.541-2.54l-.292.159a.873.873 0 0 1-1.255-.52l-.094-.319zM8 13c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/>
            </svg>
            <!-- ID Aggiunto qui -->
            <span id="label-settings" class="text-xl font-semibold">Impostazioni</span>
            <div class="w-10"></div> <!-- Spacer -->
        </button>

    </main>

    <script>
        // Nomi degli script
        const YOUTUBE_SCRIPT = '{SCRIPT_YOUTUBE}';
        const IMMICH_SCRIPT = '{SCRIPT_IMMICH}';
        const RPI_SCRIPT = '{SCRIPT_RPI}'; // <-- Aggiunto RPI

        // Elementi UI
        const btnYouTube = document.getElementById('btn-youtube');
        const btnImmich = document.getElementById('btn-immich');
        const btnSettings = document.getElementById('btn-settings');
        const labelYouTube = document.getElementById('label-youtube');
        const labelImmich = document.getElementById('label-immich');
        const labelSettings = document.getElementById('label-settings'); // <-- Aggiunto label Settings
        const statusLight = document.getElementById('status-light');
        const errorDiv = document.getElementById('error-message');

        // Stato locale
        let isYouTubeRunning = false;
        let isImmichRunning = false;
        let isRpiRunning = false; // <-- Aggiunto stato RPI
        let isRequestPending = false; // Per evitare click multipli

        // Funzione per aggiornare l'UI
        function updateUI(status) {{
            isYouTubeRunning = status.active_scripts.includes(YOUTUBE_SCRIPT);
            isImmichRunning = status.active_scripts.includes(IMMICH_SCRIPT);
            isRpiRunning = status.active_scripts.includes(RPI_SCRIPT); // <-- Aggiunto RPI

            // Stato luce
            if (status.active_scripts.length > 0) {{
                statusLight.classList.remove('bg-red-600');
                statusLight.classList.add('bg-green-500');
            }} else {{
                statusLight.classList.add('bg-red-600');
                statusLight.classList.remove('bg-green-500');
            }}

            // Pulsante YouTube
            if (isYouTubeRunning) {{
                btnYouTube.classList.add('running');
                labelYouTube.innerText = 'YouTube (On)';
            }} else {{
                btnYouTube.classList.remove('running');
                labelYouTube.innerText = 'YouTube';
            }}

            // Pulsante Immich
            if (isImmichRunning) {{
                btnImmich.classList.add('running');
                labelImmich.innerText = 'Immich (On)';
            }} else {{
                btnImmich.classList.remove('running');
                labelImmich.innerText = 'Immich';
            }}

            // Pulsante Impostazioni (RPI)
            if (isRpiRunning) {{
                btnSettings.classList.add('running');
                labelSettings.innerText = 'RPI (On)';
            }} else {{
                btnSettings.classList.remove('running');
                labelSettings.innerText = 'Impostazioni';
            }}
        }}

        // Funzione per fetchare lo stato
        async function fetchStatus() {{
            try {{
                const response = await fetch('/status');
                if (!response.ok) return;
                const data = await response.json();
                updateUI(data);
            }} catch (error) {{
                console.error("Errore fetchStatus:", error);
            }}
        }}

        // Funzione per controllare lo script
        async function controlScript(script, action) {{
            if (isRequestPending) return; // Evita doppi click
            isRequestPending = true;
            
            showError(''); // Pulisci errori
            btnYouTube.disabled = true;
            btnImmich.disabled = true;
            btnSettings.disabled = true; // <-- Disabilita anche questo

            try {{
                const response = await fetch(`/${{action}}/${{script}}`);
                const data = await response.json();

                if (data.status === 'success') {{
                    await fetchStatus(); // Aggiorna subito l'UI
                }} else {{
                    showError(data.message);
                }}
            }} catch (error) {{
                showError(error.message);
            }} finally {{
                isRequestPending = false;
                btnYouTube.disabled = false;
                btnImmich.disabled = false;
                btnSettings.disabled = false; // <-- Ri-abilita
            }}
        }}

        function showError(message) {{
            if (message) {{
                errorDiv.innerText = 'Errore: ' + message;
                errorDiv.style.display = 'block';
            }} else {{
                errorDiv.innerText = '';
                errorDiv.style.display = 'none';
            }}
        }}

        // Event Listeners
        btnYouTube.addEventListener('click', () => {{
            const action = isYouTubeRunning ? 'stop' : 'start';
            controlScript(YOUTUBE_SCRIPT, action);
        }});

        btnImmich.addEventListener('click', () => {{
            const action = isImmichRunning ? 'stop' : 'start';
            controlScript(IMMICH_SCRIPT, action);
        }});

        // <-- MODIFICATO: Ora controlla RPI_SCRIPT
        btnSettings.addEventListener('click', () => {{
            const action = isRpiRunning ? 'stop' : 'start';
            controlScript(RPI_SCRIPT, action);
        }});

        // Init
        document.addEventListener('DOMContentLoaded', () => {{
            fetchStatus();
            setInterval(fetchStatus, 3000); // Polling ogni 3 secondi
        }});
    </script>
</body>
</html>
    '''
    
    with open(template_path_remote, 'w', encoding='utf-8') as f:
        f.write(html_template_remote)
    print(f"Template Telecomando scritto in {template_path_remote}")
    
    # --- MODIFICA PER PRODUZIONE ---
    # Rimuovi debug=True e usa waitress
    print("Avvio del server di produzione (waitress) su http://0.0.0.0:5000")
    print("Visita http://<tuo_ip>:5000 per il telecomando")
    print("Visita http://<tuo_ip>:5000/settings per la lista script")
    serve(app, host='0.0.0.0', port=5000)

