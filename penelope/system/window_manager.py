"""
Penélope — Window Manager
Manages desktop windows: list, snap, close, organize.
"""

import ctypes
from typing import Dict, List, Optional

try:
    import pyautogui
except ImportError:
    pyautogui = None

from penelope.utils.logger import get_logger

log = get_logger(__name__)


class WindowManager:
    """
    Manages desktop windows using Win32 API and pyautogui.

    Supports listing windows, snap layouts, selective closing,
    and special modes (meeting, presentation).
    """

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32

    def get_open_windows(self) -> List[Dict[str, str]]:
        """
        List all visible, non-minimized windows.

        Returns:
            List of dicts with 'title' and 'hwnd' keys.
        """
        windows = []

        def enum_callback(hwnd, _):
            if self._user32.IsWindowVisible(hwnd):
                length = self._user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    self._user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.strip()
                    if title and title not in ("", "Program Manager"):
                        windows.append({
                            "title": title,
                            "hwnd": hwnd,
                        })
            return True

        enum_func_type = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int)
        )
        self._user32.EnumWindows(enum_func_type(enum_callback), 0)

        return windows

    def close_window_by_title(self, title_part: str) -> Dict:
        """
        Close a window matching a title substring.

        Args:
            title_part: Partial title to match.

        Returns:
            Result dict.
        """
        windows = self.get_open_windows()
        closed = 0

        for win in windows:
            if title_part.lower() in win["title"].lower():
                try:
                    WM_CLOSE = 0x0010
                    self._user32.PostMessageW(win["hwnd"], WM_CLOSE, 0, 0)
                    closed += 1
                    log.info(f"Closed window: {win['title']}")
                except Exception as e:
                    log.error(f"Failed to close '{win['title']}': {e}")

        if closed > 0:
            return {"success": True, "message": f"{closed} janela(s) fechada(s)."}
        return {"success": False, "message": f"Nenhuma janela encontrada com '{title_part}'."}

    def close_all_except(self, keep_title: str) -> Dict:
        """
        Close all windows except those matching a title.

        Args:
            keep_title: Title substring to keep open.

        Returns:
            Result dict.
        """
        windows = self.get_open_windows()
        closed = 0

        for win in windows:
            if keep_title.lower() not in win["title"].lower():
                try:
                    WM_CLOSE = 0x0010
                    self._user32.PostMessageW(win["hwnd"], WM_CLOSE, 0, 0)
                    closed += 1
                except Exception:
                    pass

        log.info(f"Closed {closed} windows, kept '{keep_title}'")
        return {
            "success": True,
            "message": f"{closed} janela(s) fechada(s). {keep_title} mantido.",
        }

    def organize_windows(self) -> Dict:
        """
        Auto-organize open windows.

        Uses Win+Z snap layout if pyautogui is available, otherwise tiles windows horizontally natively.
        """
        if pyautogui:
            try:
                pyautogui.hotkey("win", "z")
                return {"success": True, "message": "Layout de janelas ativado."}
            except Exception:
                pass
                
        # Native fallback using Shell.Application COM Object
        try:
            import subprocess
            subprocess.run(
                ["powershell", "-Command", "(New-Object -ComObject shell.application).TileHorizontally()"],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return {"success": True, "message": "Janelas organizadas horizontalmente."}
        except Exception as e:
            log.error(f"Failed to organize windows natively: {e}")
            return {"success": False, "message": str(e)}

    def minimize_all(self) -> Dict:
        """Minimize all windows (show desktop)."""
        if pyautogui:
            try:
                pyautogui.hotkey("win", "d")
                return {"success": True, "message": "Todas as janelas minimizadas."}
            except Exception:
                pass
                
        # Native fallback
        try:
            import subprocess
            subprocess.run(
                ["powershell", "-Command", "(New-Object -ComObject shell.application).MinimizeAll()"],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return {"success": True, "message": "Todas as janelas minimizadas."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def focus_window(self, title_part: str) -> Dict:
        """Bring a window to the foreground."""
        windows = self.get_open_windows()

        for win in windows:
            if title_part.lower() in win["title"].lower():
                try:
                    self._user32.ShowWindow(win["hwnd"], 9)  # SW_RESTORE
                    self._user32.SetForegroundWindow(win["hwnd"])
                    return {"success": True, "message": f"{win['title']} em foco."}
                except Exception as e:
                    return {"success": False, "message": str(e)}

        return {"success": False, "message": f"Janela '{title_part}' não encontrada."}

    def enter_meeting_mode(self) -> Dict:
        """
        Activate meeting mode:
        - Open Zoom/Teams
        - Disable notifications
        - Focus microphone
        """
        actions = []

        # Try to focus or open Zoom/Teams
        if not self.focus_window("zoom")["success"]:
            if not self.focus_window("teams")["success"]:
                actions.append("Zoom/Teams não encontrado")

        # Enable Focus Assist (Do Not Disturb)
        if pyautogui:
            try:
                pyautogui.hotkey("win", "a")
                actions.append("Painel de ações aberto")
            except Exception:
                pass
        else:
            actions.append("Pressione Windows+A para alternar Focus Assist")

        return {
            "success": True,
            "message": "Modo reunião ativado. " + "; ".join(actions),
        }

    def enter_presentation_mode(self) -> Dict:
        """
        Activate presentation mode:
        - Disable notifications
        - Set Do Not Disturb
        """
        try:
            # Windows Presentation Settings
            import subprocess
            subprocess.Popen(
                "presentationsettings /start",
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return {"success": True, "message": "Modo apresentação ativado."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def list_windows_text(self) -> str:
        """Get a human-readable list of open windows."""
        windows = self.get_open_windows()
        if not windows:
            return "Nenhuma janela aberta."

        lines = [f"📋 {len(windows)} janela(s) aberta(s):"]
        for i, win in enumerate(windows[:15], 1):
            lines.append(f"  {i}. {win['title']}")
        if len(windows) > 15:
            lines.append(f"  ... e mais {len(windows) - 15}")

        return "\n".join(lines)
