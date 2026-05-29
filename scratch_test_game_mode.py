import sys
import os
import shutil
import time
import subprocess
import psutil

# 1. Create a dummy game executable by copying the base python.exe (not the venv one)
workspace = r"c:\Users\alunos\Downloads\penelope_pia"
dummy_exe = os.path.join(workspace, "gta5.exe")

# Get base python.exe path to avoid pyvenv.cfg issues
base_prefix = sys.base_exec_prefix
python_exe = os.path.join(base_prefix, "python.exe")
if not os.path.exists(python_exe):
    python_exe = sys.executable

print(f"Base Python path: {python_exe}")
print(f"Creating dummy game executable: {dummy_exe}")
shutil.copy(python_exe, dummy_exe)

# 2. Run the dummy game in the background
# It runs a simple python command that sleeps for 30 seconds
game_proc = subprocess.Popen([dummy_exe, "-c", "import time; time.sleep(30)"])
print(f"Started dummy game process with PID {game_proc.pid}")

try:
    # Wait for psutil to recognize the name
    time.sleep(2)
    found = False
    for p in psutil.process_iter(["name"]):
        if p.info["name"] and p.info["name"].lower() == "gta5.exe":
            print(f"Verified: dummy process is running under name: {p.info['name']}")
            found = True
            break
    if not found:
        print("Warning: gta5.exe not found in active processes.")

    # 3. Import and initialize Penélope modules to check if optimizer detects it
    from penelope.core.event_bus import get_event_bus
    from penelope.utils.constants import EventType, SystemMode
    from penelope.core.resource_optimizer import ResourceOptimizer

    class MockMainModule:
        def __init__(self):
            self._wake_word = self
            self._hud = self
            self._llm_client = self
            self._command_executor = self
            self._current_mode = SystemMode.NORMAL
            self.clipboard_manager = self
            self.interval = 100
            self.history_cleared = False
            self.clipboard_stopped = False
            self.clipboard_started = False
            self.hud_hidden = False
            self.hud_shown = False

        @property
        def current_mode(self):
            return self._current_mode

        def set_interval(self, val):
            self.interval = val
            print(f"[Mock] WakeWord check interval set to {val}ms")

        def hide(self):
            self.hud_hidden = True
            print("[Mock] HUD hidden")

        def show(self):
            self.hud_shown = True
            print("[Mock] HUD shown")

        def set_mode(self, mode):
            self._current_mode = mode
            print(f"[Mock] HUD mode set to {mode.value}")

        def set_response(self, text):
            print(f"[Mock] HUD text response set to: '{text}'")

        def clear_history(self):
            self.history_cleared = True
            print("[Mock] LLM Client history cleared")

        def stop(self):
            self.clipboard_stopped = True
            print("[Mock] Clipboard Manager stopped")

        def start(self):
            self.clipboard_started = True
            print("[Mock] Clipboard Manager started")

    mock_main = MockMainModule()
    optimizer = ResourceOptimizer(mock_main)

    # Listen to EventBus for mode changes
    mode_changes = []
    def on_mode_changed(old_mode, new_mode, **kwargs):
        print(f"[Event] MODE_CHANGED: {old_mode} -> {new_mode}")
        mode_changes.append((old_mode, new_mode))

    get_event_bus().on(EventType.MODE_CHANGED, on_mode_changed)

    # Start the optimizer (which starts the game detection loop)
    # We set detection interval to 2 seconds for testing
    optimizer._detection_interval = 2.0
    optimizer.start()

    print("Optimizer started. Waiting for game detection...")
    time.sleep(5)

    assert len(mode_changes) > 0, "Error: Game Mode was not detected and triggered!"
    assert mode_changes[0][1] == "game", f"Error: Mode changed to {mode_changes[0][1]} instead of game!"
    print("Success: Game Mode successfully detected and activated!")

    # 4. Now terminate the game
    print("Terminating dummy game process...")
    game_proc.terminate()
    game_proc.wait()

    print("Waiting for optimizer to restore normal mode...")
    time.sleep(5)

    assert mode_changes[-1][1] == "normal", f"Error: Normal Mode was not restored! Last mode: {mode_changes[-1][1]}"
    print("Success: Normal Mode successfully restored after game exit!")

    optimizer.stop()
    print("Test passed successfully!")

finally:
    # Cleanup dummy exe
    if game_proc.poll() is None:
        game_proc.kill()
    if os.path.exists(dummy_exe):
        try:
            os.remove(dummy_exe)
            print("Cleaned up dummy game executable.")
        except Exception as e:
            print(f"Failed to remove dummy exe: {e}")
