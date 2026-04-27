import os
import csv
import time
import asyncio
import pandas as pd
from datetime import datetime
import threading
import random
from nicegui import ui, app

# --- 1. GLOBAL STATE ---
# CRITICAL: Using strings for keys "0" through "6" to prevent NiceGUI binding errors
state = {
    'pt': {'TK': 0.0, 'CH': 0.0, 'FU': 0.0, 'OX': 0.0},
    'lc': [0.0, 0.0, 0.0], 
    'volts': {str(i): 0.0 for i in range(7)}, 
    'is_logging': False,
    'current_file': '',
    'start_time': None,
    'status': 'SAFE', 
    'valves': {'FIL': False, 'PUR': False, 'FMV': False, 'OMV': False, 'EMATCH': False}
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# --- 2. LOGIC & ACTIONS ---

def trigger_abort():
    state['status'] = 'SAFE'
    for k in state['valves']: state['valves'][k] = False
    ui.notify('EMERGENCY ABORT: SYSTEM SAFED', type='negative', position='top')

async def run_ignition_sequence(arm_checkbox):
    if not arm_checkbox.value:
        ui.notify('ARMING REQUIRED', type='negative')
        return
    
    state['status'] = 'COUNTDOWN: 10'
    for i in range(10, -1, -1):
        if state['status'] == 'SAFE': return 
        state['status'] = f'COUNTDOWN: {i}'
        await asyncio.sleep(1)
    
    if state['status'] != 'SAFE':
        state['status'] = 'FIRING'
        state['valves']['OMV'] = True
        state['valves']['FMV'] = True
        state['valves']['EMATCH'] = True
        ui.notify('IGNITION ACTIVE', color='red', duration=None)

def toggle_logging():
    if not state['is_logging']:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"rocket_test_{timestamp}.csv"
        full_path = os.path.join(LOG_DIR, filename)
        state['current_file'] = filename
        with open(full_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Seconds', 'PT_TK', 'PT_CH', 'PT_FU', 'PT_OX', 'TotalThrust'])
        state['start_time'] = time.time()
        state['is_logging'] = True
        ui.notify(f'RECORDING: {filename}', type='positive')
    else:
        state['is_logging'] = False
        ui.notify('RECORDING STOPPED', type='warning')

# --- 3. UI SHARED COMPONENTS ---

def nav_header():
    with ui.header().classes('items-center justify-between px-8 bg-slate-900 shadow-md'):
        ui.label('NKU LIQUID ROCKET DAQ 2026').classes('text-2xl font-bold tracking-tight')
        with ui.row().classes('gap-6'):
            ui.link('DASHBOARD', '/').classes('text-white font-medium hover:text-cyan-400')
            ui.link('TEST', '/test').classes('text-white font-medium hover:text-cyan-400')
            ui.link('ANALYSIS', '/analysis').classes('text-white font-medium hover:text-cyan-400')

# --- 4. PAGES ---

@ui.page('/')
def dashboard():
    ui.colors(primary='#0f172a', secondary='#b91c1c')
    nav_header()
    
    with ui.row().classes('w-full no-wrap p-4 gap-4'):
        # --- LEFT COLUMN: COMMAND CENTER ---
        with ui.card().classes('w-1/3 shadow-lg border-t-4 border-red-800'):
            ui.label('COMMAND CENTER').classes('text-xl font-bold text-slate-600')
            ui.button('ABORT', on_click=trigger_abort).classes('w-full h-20 bg-red-800 text-white font-black text-2xl mb-4')
            
            with ui.column().classes('w-full border p-4 rounded bg-slate-50 gap-3'):
                ui.label('MANUAL VALVE OVERRIDE').classes('font-bold mb-2 text-xs uppercase text-slate-400')
                
                btn_refs = {}

                for v in ['FIL', 'PUR', 'FMV', 'OMV']:
                    with ui.row().classes('w-full items-center justify-between'):
                        ui.label(v).classes('font-bold text-slate-700')
                        
                        with ui.row().classes('gap-0 border rounded overflow-hidden'):
                            # CLOSE Button
                            c_btn = ui.button('CLOSE', on_click=lambda v=v: state['valves'].__setitem__(v, False)) \
                                .props('flat square size=sm').classes('px-3 font-bold')
                            
                            # OPEN Button
                            o_btn = ui.button('OPEN', on_click=lambda v=v: state['valves'].__setitem__(v, True)) \
                                .props('flat square size=sm').classes('px-3 font-bold')
                            
                            btn_refs[v] = {'close': c_btn, 'open': o_btn}
            
            ui.separator().classes('my-4')
            
            with ui.column().classes('w-full border p-4 rounded bg-red-50'):
                ui.label('IGNITION CONTROL').classes('font-bold text-red-700 text-xs uppercase')
                arm = ui.checkbox('ARM E-MATCH')
                ui.label().bind_text_from(state, 'status').classes('text-6xl font-black text-center w-full text-orange-600 py-4 font-mono').bind_visibility_from(state, 'status', lambda x: 'COUNTDOWN' in x)
                ui.button('START SEQUENCE', on_click=lambda: run_ignition_sequence(arm)).classes('w-full h-20 bg-orange-700 text-white font-bold text-lg').bind_visibility_from(state, 'status', lambda x: x not in ['FIRING'] and 'COUNTDOWN' not in x)
                ui.button('FIRING - CLICK TO ABORT', on_click=trigger_abort).classes('w-full h-20 bg-red-600 text-white font-black animate-pulse text-lg').bind_visibility_from(state, 'status', lambda x: x == 'FIRING')

            ui.separator().classes('my-4')
            ui.button('START LOGGING', on_click=toggle_logging).classes('w-full').bind_visibility_from(state, 'is_logging', backward=lambda x: not x)
            ui.button('STOP LOGGING', on_click=toggle_logging, color='red').classes('w-full').bind_visibility_from(state, 'is_logging')

        # --- RIGHT COLUMN: TELEMETRY ---
        with ui.card().classes('flex-grow shadow-lg border-t-4 border-cyan-600'):
            with ui.row().classes('items-center justify-between w-full mb-4'):
                ui.label('LIVE TELEMETRY').classes('text-xl font-bold text-slate-600')
                status_badge = ui.badge('SAFE').classes('p-2 px-4 text-sm uppercase font-bold')
            
            with ui.grid(columns=2).classes('w-full gap-4 p-2'):
                for key in ['TK', 'CH', 'FU', 'OX']:
                    with ui.card().classes('items-center bg-slate-900 text-white p-4 border border-slate-700'):
                        ui.label(f'PT-{key} (PSI)').classes('text-xs text-slate-400 font-bold uppercase')
                        ui.label().bind_text_from(state['pt'], key, backward=lambda x: f"{x:.1f}").classes('text-5xl font-mono text-cyan-400')
                
                with ui.card().classes('col-span-2 items-center bg-blue-900 text-white p-8 border-2 border-blue-400'):
                    ui.label('TOTAL MEASURED THRUST').classes('text-sm text-blue-200 font-bold uppercase tracking-widest')
                    thrust_label = ui.label('0.00 kg').classes('text-8xl font-mono text-white')

            # --- UI UPDATE TIMER ---
            def update_ui():
                # Update Thrust & Status
                thrust_label.set_text(f"{sum(state['lc']):.2f} kg")
                status_badge.set_text(state['status'])
                curr = state['status']
                status_badge.style(f'background-color: {"#ea580c" if "COUNTDOWN" in curr else "#dc2626" if curr == "FIRING" else "#16a34a"}')

                # Update Valve Button Styles based on current state
                for v, btns in btn_refs.items():
                    is_open = state['valves'][v]
                    # Update CLOSE button
                    btns['close'].classes(remove='bg-slate-300 text-slate-700 text-slate-400', 
                                         add='bg-slate-300 text-slate-700' if not is_open else 'text-slate-400')
                    # Update OPEN button
                    btns['open'].classes(remove='bg-green-600 text-white text-slate-400', 
                                        add='bg-green-600 text-white' if is_open else 'text-slate-400')

            ui.timer(0.1, update_ui)

@ui.page('/test')
def test_page():
    nav_header()
    ui.label('HARDWARE TEST BENCH (I/O)').classes('text-2xl font-bold p-4 text-slate-700')
    
    with ui.row().classes('w-full p-4 gap-6'):
        # --- DIGITAL OUTPUT CONTROL (FIO 0-4) ---
        with ui.card().classes('w-2/5 p-6 shadow-md'):
            ui.label('DIGITAL OUTPUTS (FIO)').classes('text-lg font-bold text-slate-500 mb-4')
            
            # FIL(0), PUR(1), FMV(2), OMV(3), EMATCH(4)
            fio_keys = ['FIL', 'PUR', 'FMV', 'OMV', 'EMATCH']
            
            for idx, key in enumerate(fio_keys):
                with ui.row().classes('w-full items-center justify-between mb-4 p-3 bg-slate-50 rounded border'):
                    with ui.column():
                        ui.input(label=f'Label for FIO-{idx}', value=key).classes('w-32')
                        ui.label(f'FIO-{idx}').classes('text-xs text-slate-400')
                    
                    with ui.row().classes('gap-2'):
                        ui.button('TEST GND', on_click=lambda k=key: state['valves'].__setitem__(k, False)) \
                            .props('outline color=grey-7').classes('w-24 font-bold')
                        
                        ui.button('TEST 5V', on_click=lambda k=key: state['valves'].__setitem__(k, True)) \
                            .props('color=green-6').classes('w-24 font-bold')

        # --- LIVE ANALOG INPUTS (AIN) ---
        with ui.card().classes('flex-grow p-6 bg-slate-900 text-white shadow-xl'):
            ui.label('LIVE ANALOG INPUTS (AIN)').classes('text-lg font-bold text-cyan-400 mb-4')
            
            with ui.column().classes('w-full gap-4'):
                ui.label('GROUP 1: LOAD CELLS').classes('text-xs font-bold text-slate-400 uppercase tracking-widest')
                with ui.grid(columns=3).classes('w-full gap-4'):
                    for i in range(3):
                        s_idx = str(i) 
                        with ui.column().classes('items-center border border-slate-700 p-4 rounded'):
                            ui.label(f'AIN-{s_idx}').classes('text-xs text-slate-400')
                            ui.label().bind_text_from(state['volts'], s_idx, backward=lambda x: f"{x:.3f} V") \
                                .classes('text-2xl font-mono text-yellow-400')

                ui.label('GROUP 2: PRESSURE TRANSDUCERS').classes('text-xs font-bold text-slate-400 uppercase tracking-widest mt-4')
                with ui.grid(columns=4).classes('w-full gap-4'):
                    for i in range(3, 7):
                        s_idx = str(i)
                        with ui.column().classes('items-center border border-slate-700 p-4 rounded'):
                            ui.label(f'AIN-{s_idx}').classes('text-xs text-slate-400')
                            ui.label().bind_text_from(state['volts'], s_idx, backward=lambda x: f"{x:.3f} V") \
                                .classes('text-2xl font-mono text-yellow-400')

@ui.page('/analysis')
def analysis():
    nav_header()
    ui.label('POST-FIRE ANALYSIS').classes('text-2xl font-bold p-4 text-slate-700')
    log_files = sorted([f for f in os.listdir(LOG_DIR) if f.endswith('.csv')], reverse=True) if os.path.exists(LOG_DIR) else []
    res_container = ui.column().classes('w-full p-4')

    def run_analysis(fn):
        try:
            df = pd.read_csv(os.path.join(LOG_DIR, fn))
            res_container.clear()
            with res_container:
                ui.label(f"Peak Thrust: {df['TotalThrust'].max():.2f} kg").classes('text-4xl font-bold text-blue-600')
                ui.label(f"Peak Tank: {df['PT_TK'].max():.2f} PSI").classes('text-2xl text-slate-500')
        except: ui.notify("Error reading log")

    with ui.row().classes('p-4 bg-slate-50 w-full border-b'):
        for f in log_files: ui.button(f, on_click=lambda _, f=f: run_analysis(f)).props('flat icon=description')

# --- 5. BACKGROUND DAQ ---
def background_daq():
    while True:
        is_firing = (state['status'] == 'FIRING')
        for k in state['pt']: state['pt'][k] = random.uniform(400, 550) if is_firing else random.uniform(0, 5)
        state['lc'] = [random.uniform(20, 35) if is_firing else 0.0 for _ in range(3)]
        
        for i in range(7):
            state['volts'][str(i)] = random.uniform(0, 5)
            
        if state['is_logging']:
            elapsed = time.time() - state['start_time']
            with open(os.path.join(LOG_DIR, state['current_file']), 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([datetime.now(), elapsed, *state['pt'].values(), sum(state['lc'])])
        time.sleep(0.1)

threading.Thread(target=background_daq, daemon=True).start()
ui.run(title="NKU Rocket DAQ", port=8080)