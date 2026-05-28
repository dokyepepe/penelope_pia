"""
Penélope — Setup Wizard
First-boot CLI wizard to create the owner profile.
"""

import sys
from typing import Optional

from penelope.utils.constants import DATA_DIR, LOGS_DIR, CHROMA_DIR, SCREENSHOTS_DIR
from penelope.utils.logger import get_logger

log = get_logger(__name__)


def ensure_directories() -> None:
    """Create all required data directories."""
    for d in (DATA_DIR, LOGS_DIR, CHROMA_DIR, SCREENSHOTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
    log.debug("Data directories verified")


def run_setup_wizard() -> bool:
    """
    Run the interactive first-boot setup wizard.

    Creates the owner profile with a spoken passphrase.
    Returns True if setup completed successfully.
    """
    _print_banner()

    print("\n  Este é o primeiro boot do sistema Penélope.")
    print("  Vamos configurar o perfil do Proprietário.\n")

    # --- Owner name ---
    owner_name = _ask("  Qual é o seu nome?", default="Pietro")
    if not owner_name:
        print("  ✗ Nome não pode ser vazio.")
        return False

    # --- Passphrase ---
    print("\n  Escolha uma frase-chave de acesso.")
    print("  (Você vai falar esta frase para se autenticar por voz)\n")

    passphrase = _ask("  Frase-chave")
    if not passphrase or len(passphrase) < 3:
        print("  ✗ Frase-chave muito curta (mínimo 3 caracteres).")
        return False

    confirm = _ask("  Confirme a frase-chave")
    if confirm.strip().lower() != passphrase.strip().lower():
        print("  ✗ As frases não coincidem. Tente novamente.")
        return False

    # --- Create profile ---
    try:
        from penelope.auth.authenticator import Authenticator

        auth = Authenticator()
        profile = auth.setup_first_owner(name=owner_name, passphrase=passphrase)
        print(f"\n  ✓ Perfil criado: {profile.name} (Nível {profile.level.name})")
        print(f"  ✓ ID: {profile.id}")
    except RuntimeError as e:
        print(f"\n  ✗ Erro: {e}")
        return False
    except Exception as e:
        log.error(f"Setup wizard failed: {e}")
        print(f"\n  ✗ Erro inesperado: {e}")
        return False

    # --- Ollama check (informational) ---
    _check_ollama()

    # --- Hardware summary ---
    _show_hardware_summary()

    print("\n  ══════════════════════════════════════════════")
    print("  ✓ Setup concluído! Penélope está pronta.")
    print("  ══════════════════════════════════════════════\n")

    return True


def needs_setup() -> bool:
    """
    Check if the first-boot setup is needed.

    Returns True if there is no owner profile in the database.
    """
    try:
        from penelope.auth.profiles import ProfileManager
        pm = ProfileManager()
        return not pm.has_owner()
    except Exception:
        return True


def _print_banner() -> None:
    """Print the setup wizard banner."""
    print()
    print("  ══════════════════════════════════════════════")
    print("  ██████  ███████ ███    ██ ███████ ██      ██████  ██████  ███████")
    print("  ██   ██ ██      ████   ██ ██      ██     ██    ██ ██   ██ ██     ")
    print("  ██████  █████   ██ ██  ██ █████   ██     ██    ██ ██████  █████  ")
    print("  ██      ██      ██  ██ ██ ██      ██     ██    ██ ██      ██     ")
    print("  ██      ███████ ██   ████ ███████ ███████ ██████  ██      ███████")
    print("  ══════════════════════════════════════════════")
    print("  Assistente Pessoal de IA Local · v0.1.0")
    print("  ══════════════════════════════════════════════")


def _ask(prompt: str, default: Optional[str] = None) -> str:
    """Ask the user for input with an optional default."""
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "

    try:
        answer = input(full_prompt).strip()
        return answer if answer else (default or "")
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelado pelo usuário.")
        sys.exit(0)


def _check_ollama() -> None:
    """Check if Ollama is running and report status."""
    print("\n  Verificando Ollama...")
    try:
        import ollama as ollama_lib
        models = ollama_lib.list()
        available = [m.model for m in models.models] if models.models else []
        if available:
            print(f"  ✓ Ollama online — modelos: {', '.join(available)}")
        else:
            print("  ⚠ Ollama online, mas nenhum modelo instalado.")
            print("    Execute: ollama pull llama3.1:8b")
    except Exception:
        print("  ⚠ Ollama não encontrado ou offline.")
        print("    Instale em: https://ollama.com")
        print("    O sistema vai operar em modo degradado (regras simples).")


def _show_hardware_summary() -> None:
    """Show a hardware summary."""
    print("\n  Hardware detectado:")
    try:
        from penelope.utils.system_info import get_system_snapshot

        snap = get_system_snapshot()
        print(f"    CPU:  {snap.cpu_name} ({snap.cpu_cores}C/{snap.cpu_threads}T)")
        print(f"    RAM:  {snap.ram_total_gb:.1f} GB total, {snap.ram_free_gb:.1f} GB livre")
        print(f"    Disco: {snap.disk_free_gb:.1f} GB livre de {snap.disk_total_gb:.1f} GB")

        if snap.gpu.cuda_available:
            print(
                f"    GPU:  {snap.gpu.name} "
                f"({snap.gpu.vram_total_mb}MB VRAM, "
                f"{snap.gpu.vram_free_mb}MB livre)"
            )
        else:
            print("    GPU:  Nenhuma GPU NVIDIA detectada (modo CPU)")
    except Exception as e:
        print(f"    (Não foi possível detectar: {e})")
