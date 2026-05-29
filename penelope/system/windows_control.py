"""
Penélope — Windows Control
Commands for interacting with the Windows 11 operating system.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional

try:
    import pyautogui
except ImportError:
    pyautogui = None

from penelope.auth.permissions import Permission, requires_permission
from penelope.utils.constants import SCREENSHOTS_DIR
from penelope.utils.logger import get_logger

log = get_logger(__name__)

# Disable pyautogui fail-safe pause
if pyautogui:
    pyautogui.PAUSE = 0.1


class WindowsControl:
    """
    Interface for controlling Windows 11 via voice commands.

    Handles app launching, volume control, screenshots,
    shutdown, and other system operations.
    """

    def __init__(self) -> None:
        self._app_registry: Dict[str, str] = {
            "chrome": "chrome",
            "google chrome": "chrome",
            "navegador": "chrome",
            "browser": "chrome",
            "edge": "msedge",
            "microsoft edge": "msedge",
            "explorador": "explorer",
            "explorador de arquivos": "explorer",
            "vscode": "code",
            "vs code": "code",
            "visual studio code": "code",
            "spotify": "spotify",
            "whatsapp": "whatsapp",
            "discord": "discord",
            "notepad": "notepad",
            "bloco de notas": "notepad",
            "calculadora": "calc",
            "calculator": "calc",
            "task manager": "taskmgr",
            "gerenciador de tarefas": "taskmgr",
            "paint": "mspaint",
            "terminal": "wt",
            "cmd": "cmd",
            "powershell": "powershell",
            "configurações": "ms-settings:",
            "settings": "ms-settings:",
            "vlc": "vlc",
            "zoom": "zoom",
            "teams": "teams",
            "outlook": "outlook",
        }

        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    def open_app(self, app_name: str) -> Dict:
        """
        Open an application by name.

        Args:
            app_name: Natural language app name.

        Returns:
            Result dict with success status.
        """
        normalized = app_name.strip().lower()
        exe = self._app_registry.get(normalized, normalized)

        try:
            if exe.startswith("ms-settings") or exe.startswith("http"):
                os.startfile(exe)
            else:
                subprocess.Popen(
                    exe,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            log.info(f"Opened app: {app_name} ({exe})")
            return {"success": True, "message": f"{app_name} aberto."}

        except Exception as e:
            log.error(f"Failed to open {app_name}: {e}")
            return {"success": False, "message": f"Não consegui abrir {app_name}."}

    def close_app(self, app_name: str) -> Dict:
        """Close an application by name."""
        normalized = app_name.strip().lower()
        exe = self._app_registry.get(normalized, normalized)

        try:
            subprocess.run(
                ["taskkill", "/IM", f"{exe}.exe", "/F"],
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            log.info(f"Closed app: {app_name}")
            return {"success": True, "message": f"{app_name} fechado."}
        except Exception as e:
            log.error(f"Failed to close {app_name}: {e}")
            return {"success": False, "message": f"Não consegui fechar {app_name}."}

    def take_screenshot(self) -> Dict:
        """Take a screenshot and save to the screenshots directory."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filepath = SCREENSHOTS_DIR / f"screenshot_{timestamp}.png"
        
        # Try using pyautogui first
        if pyautogui:
            try:
                screenshot = pyautogui.screenshot()
                screenshot.save(str(filepath))
                log.info(f"Screenshot saved via pyautogui: {filepath}")
                return {
                    "success": True,
                    "message": "Captura de tela salva.",
                    "path": str(filepath),
                }
            except Exception as e:
                log.warning(f"Screenshot via pyautogui failed, trying native PowerShell: {e}")

        # Fallback using native C#/PowerShell (requires no dependencies)
        try:
            path_str = str(filepath).replace("\\", "/")
            cmd = [
                "powershell",
                "-Command",
                "[Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); "
                "[Reflection.Assembly]::LoadWithPartialName('System.Drawing'); "
                "$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
                "$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height); "
                "$graphics = [System.Drawing.Graphics]::FromImage($bitmap); "
                "$graphics.CopyFromScreen($screen.X, $screen.Y, 0, 0, $bitmap.Size); "
                "$bitmap.Save('" + path_str + "', [System.Drawing.Imaging.ImageFormat]::Png); "
                "$graphics.Dispose(); "
                "$bitmap.Dispose();"
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=15
            )
            if result.returncode == 0 and filepath.exists():
                log.info(f"Screenshot saved via native PowerShell: {filepath}")
                return {
                    "success": True,
                    "message": "Captura de tela salva.",
                    "path": str(filepath),
                }
            else:
                stderr = result.stderr.decode("utf-8", errors="ignore")
                log.error(f"Native screenshot via PowerShell failed: {stderr}")
        except Exception as e:
            log.error(f"Native screenshot failed: {e}")
            
        return {"success": False, "message": "Falha na captura de tela."}

    def shutdown(self, delay_seconds: int = 30) -> Dict:
        """
        Shutdown the computer with a delay.

        Args:
            delay_seconds: Seconds before shutdown.
        """
        try:
            subprocess.Popen(
                ["shutdown", "/s", "/t", str(delay_seconds)],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            log.info(f"Shutdown scheduled in {delay_seconds}s")
            return {
                "success": True,
                "message": f"Computador será desligado em {delay_seconds} segundos.",
            }
        except Exception as e:
            log.error(f"Shutdown failed: {e}")
            return {"success": False, "message": "Falha ao programar desligamento."}

    def cancel_shutdown(self) -> Dict:
        """Cancel a scheduled shutdown."""
        try:
            subprocess.run(
                ["shutdown", "/a"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return {"success": True, "message": "Desligamento cancelado."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def restart(self, delay_seconds: int = 30) -> Dict:
        """Restart the computer."""
        try:
            subprocess.Popen(
                ["shutdown", "/r", "/t", str(delay_seconds)],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return {
                "success": True,
                "message": f"Computador será reiniciado em {delay_seconds} segundos.",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def lock_screen(self) -> Dict:
        """Lock the Windows session."""
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return {"success": True, "message": "Tela bloqueada."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def empty_recycle_bin(self) -> Dict:
        """Empty the Windows recycle bin."""
        try:
            import ctypes
            # SHEmptyRecycleBin flags: no confirmation, no progress, no sound
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x0007)
            return {"success": True, "message": "Lixeira esvaziada."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_ip_address(self) -> Dict:
        """Get the local IP address."""
        import socket
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return {
                "success": True,
                "message": f"Seu IP é {ip}.",
                "ip": ip,
                "hostname": hostname,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_current_time(self) -> Dict:
        """Get the current time."""
        now = time.strftime("%H:%M")
        date = time.strftime("%d de %B de %Y")
        return {
            "success": True,
            "message": f"São {now}, {date}.",
            "time": now,
            "date": date,
        }

    def toggle_airplane_mode(self) -> Dict:
        """Toggle airplane mode (requires special handling on Win11)."""
        try:
            # Use keyboard shortcut approach
            if pyautogui:
                pyautogui.hotkey("win", "a")  # Open Action Center
                time.sleep(0.5)
                return {
                    "success": True,
                    "message": "Painel de ações aberto. Altere o modo avião manualmente.",
                }
            else:
                return {
                    "success": True,
                    "message": "Para alternar o Modo Avião, abra o Painel de Ações pressionando Windows+A no teclado.",
                }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def media_play_pause(self) -> Dict:
        """Play or pause active media (e.g. Spotify)."""
        try:
            import ctypes
            # VK_MEDIA_PLAY_PAUSE = 0xB3
            ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xB3, 0, 2, 0)
            return {"success": True, "message": "Mídia pausada ou retomada."}
        except Exception as e:
            log.error(f"Media play/pause failed: {e}")
            return {"success": False, "message": "Falha ao controlar mídia."}

    def media_next(self) -> Dict:
        """Skip to next media track."""
        try:
            import ctypes
            # VK_MEDIA_NEXT_TRACK = 0xB0
            ctypes.windll.user32.keybd_event(0xB0, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xB0, 0, 2, 0)
            return {"success": True, "message": "Pulei para a próxima faixa."}
        except Exception as e:
            log.error(f"Media next failed: {e}")
            return {"success": False, "message": "Falha ao passar música."}

    def media_prev(self) -> Dict:
        """Go back to previous media track."""
        try:
            import ctypes
            # VK_MEDIA_PREV_TRACK = 0xB1
            ctypes.windll.user32.keybd_event(0xB1, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xB1, 0, 2, 0)
            return {"success": True, "message": "Voltando para a música anterior."}
        except Exception as e:
            log.error(f"Media prev failed: {e}")
            return {"success": False, "message": "Falha ao voltar música."}

    def browser_search(self, query: str) -> Dict:
        """Search query in Google Chrome."""
        try:
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={encoded_query}"
            os.startfile(url)
            return {"success": True, "message": f"Pesquisando por {query} no navegador."}
        except Exception as e:
            log.error(f"Browser search failed: {e}")
            return {"success": False, "message": "Falha ao abrir pesquisa."}

    def browser_new_tab(self) -> Dict:
        """Open a new tab in active browser."""
        try:
            if pyautogui:
                pyautogui.hotkey("ctrl", "t")
                return {"success": True, "message": "Nova aba aberta."}
            return {"success": False, "message": "Automatizador de interface não disponível."}
        except Exception as e:
            log.error(f"Browser new tab failed: {e}")
            return {"success": False, "message": "Falha ao abrir aba."}

    def browser_close_tab(self) -> Dict:
        """Close active tab in active browser."""
        try:
            if pyautogui:
                pyautogui.hotkey("ctrl", "w")
                return {"success": True, "message": "Aba fechada."}
            return {"success": False, "message": "Automatizador de interface não disponível."}
        except Exception as e:
            log.error(f"Browser close tab failed: {e}")
            return {"success": False, "message": "Falha ao fechar aba."}

    def whatsapp_send(self, contact: str, message: str) -> Dict:
        """Send a WhatsApp message via GUI automation."""
        try:
            if not pyautogui:
                return {"success": False, "message": "Biblioteca PyAutoGUI não disponível."}

            log.info(f"Opening WhatsApp for contact: {contact}")
            try:
                os.startfile("whatsapp://")
            except Exception:
                exe = self._app_registry.get("whatsapp", "whatsapp")
                subprocess.Popen(exe, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            time.sleep(3.0)

            pyautogui.hotkey("ctrl", "f")
            time.sleep(0.5)

            pyautogui.write(contact, interval=0.05)
            time.sleep(1.0)

            pyautogui.press("enter")
            time.sleep(0.8)

            pyautogui.write(message, interval=0.03)
            time.sleep(0.5)

            pyautogui.press("enter")

            log.info(f"WhatsApp message sent to {contact}")
            return {"success": True, "message": f"Mensagem enviada para {contact}."}

        except Exception as e:
            log.error(f"WhatsApp automation failed: {e}")
            return {"success": False, "message": "Falha ao enviar mensagem pelo WhatsApp."}

    def register_app(self, name: str, command: str) -> None:
        """Register a custom app name to command mapping."""
        self._app_registry[name.lower()] = command
        log.info(f"App registered: {name} → {command}")

    def get_registered_apps(self) -> Dict[str, str]:
        """Get all registered app mappings."""
        return dict(self._app_registry)
