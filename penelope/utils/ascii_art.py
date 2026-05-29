"""
Penélope — ASCII Art & Console Boot Animations
Provides cyberpunk terminal effects, ANSI-colored logos, and boot diagnostics.
"""

import sys
import time
import random

# ANSI Escape Sequences for neon colors
CYAN = "\033[38;5;51m"
PURPLE = "\033[38;5;99m"
GREEN = "\033[38;5;82m"
YELLOW = "\033[38;5;226m"
RED = "\033[38;5;196m"
BLUE = "\033[38;5;33m"
WHITE = "\033[97m"
GRAY = "\033[90m"
RESET = "\033[0m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"

# Large cybernetic ASCII logo
LOGO_ASCII = f"""
{CYAN}    ____  ______ _   __ ______ __     ____   ____  ______
   / __ \\/ ____// | / // ____// /    / __ \\ / __ \\/ ____/
  / /_/ // __/  /  |/ // __/  / /    / / / // /_/ // __/   
 {PURPLE}/ ____// /___ / /|  // /___ / /___ / /_/ // ____// /___   
/_/    /_____//_/ |_//_____//_____/ \\____//_/    /_____/  
{RESET}"""

CORE_AVATAR = f"""
{CYAN}                 .::::::::::.
             .::::::::::::::::::.
           .::::::::::::::::::::::.
          .::::::::::::::::::::::::.
         .::::::::::::::::::::::::::.
        .::::::{PURPLE}===  PENÉLOPE  ==={CYAN}::::::.
        .:::::{WHITE}  [ HOLOGRAPHIC CORE ] {CYAN}:::::.
         .::::::::::::::::::::::::::.
          .::::::::::::::::::::::::.
           .::::::::::::::::::::::.
             .::::::::::::::::::.
                 '::::::::::'
{RESET}"""

def clear_console():
    """Clear terminal screen."""
    if sys.platform == "win32":
        import os
        os.system("cls")
    else:
        print("\033[H\033[J", end="")

def typewriter_print(text: str, delay: float = 0.02, color: str = WHITE):
    """Print text with a typewriter effect."""
    for char in text:
        sys.stdout.write(f"{color}{char}")
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(RESET + "\n")
    sys.stdout.flush()

def draw_cyber_border():
    """Draw a neon visual separator."""
    border = "═" * 60
    print(f"{PURPLE}{border}{RESET}")

def play_boot_animation():
    """Execute a simulated high-tech boot sequence with diagnostics."""
    clear_console()
    draw_cyber_border()
    print(LOGO_ASCII)
    draw_cyber_border()
    
    typewriter_print("⚡ SEEDING NEURAL PATHWAYS & CORE SUBSYSTEMS...", 0.015, CYAN)
    time.sleep(0.3)
    
    stages = [
        ("INITIALIZING HARDWARE INTERFACES", ["CPU cores map", "VRAM optimization", "COM controls"]),
        ("CONNECTING LOCAL COGNITIVE LAYER", ["Ollama API link", "Model temperature calibrator"]),
        ("MOUNTING VECTOR KNOWLEDGE BASE", ["ChromaDB client", "Short/Long memory synchronization"]),
        ("ESTABLISHING VOICE CHANNELS", ["Whisper audio buffer", "Vosk STT fallback", "TTS engine"]),
        ("LAUNCHING HOLOGRAPHIC HUD INTERFACE", ["PyQt6 event loop", "Radial menu hooks", "System Tray"]),
    ]
    
    for stage, items in stages:
        print(f"\n{BOLD}{CYAN}>> {stage}{RESET}")
        time.sleep(0.1)
        for item in items:
            # Simulate scanning / checking
            status = f"{GRAY}[WAIT]{RESET} Check {item}..."
            sys.stdout.write(f"   {status}")
            sys.stdout.flush()
            
            # Simulated progress loading bar
            duration = random.uniform(0.1, 0.4)
            steps = 10
            for k in range(steps):
                time.sleep(duration / steps)
                progress = "▰" * (k + 1) + "▱" * (steps - k - 1)
                sys.stdout.write(f"\r   {GRAY}[WAIT]{RESET} {item:<30} {PURPLE}[{progress}]{RESET}")
                sys.stdout.flush()
                
            sys.stdout.write(f"\r   {GREEN}[ OK ]{RESET} {item:<30} {GREEN}[COMPLETE]{RESET}\n")
            sys.stdout.flush()
            time.sleep(0.05)
            
    print(f"\n{BOLD}{GREEN}✓ ALL SYSTEMS OPERATIONAL.{RESET}")
    draw_cyber_border()
    typewriter_print("PENÉLOPE V4.0 SUCESSFULLY BOOTED IN ACTIVE BACKGROUND MODE.", 0.01, WHITE)
    draw_cyber_border()
    print()

def show_hologram_command():
    """Simulate showing Penélope's holographic core in console."""
    draw_cyber_border()
    print(CORE_AVATAR)
    draw_cyber_border()
    typewriter_print("Penélope Hologram Core: ONLINE & SECURE.", 0.02, CYAN)
    print()

def run_full_diagnostics():
    """Perform a high-tech simulated diagnostics check in console."""
    draw_cyber_border()
    typewriter_print("🔍 RUNNING SYSTEM INTEGRITY DIAGNOSTIC...", 0.015, PURPLE)
    time.sleep(0.2)
    
    import psutil
    
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("C:/").percent
    
    checks = [
        ("CPU Cores Integrity", f"{cpu}% load - STABLE"),
        ("System Memory Mapping", f"{ram}% usage - ALLOCATED"),
        ("Local Disk Partition", f"{disk}% used - OPTIMAL"),
        ("Chroma Vector Database", "SYNCED (1.2k tokens index)"),
        ("Ollama Cognitive Loop", "CONNECTED (model: active)"),
        ("Audio Input/Output Wave", "STEREO CHANNEL ACTIVE"),
        ("Security Level Handshake", "VERIFIED (Owner: Pietro)"),
    ]
    
    for name, status in checks:
        sys.stdout.write(f"   Analyzing {name}...")
        sys.stdout.flush()
        time.sleep(random.uniform(0.1, 0.3))
        sys.stdout.write(f"\r   {GREEN}[PASS]{RESET} {name:<26} :: {CYAN}{status}{RESET}\n")
        sys.stdout.flush()
        
    draw_cyber_border()
    typewriter_print("DIAGNOSTIC REPORT: ALL SYSTEMS ARE OPERATING WITHIN EXCELLENT METRICS.", 0.01, GREEN)
    draw_cyber_border()
    print()
