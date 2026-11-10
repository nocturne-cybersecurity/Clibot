#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Try to import rich for beautiful output, fallback to plain text
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.text import Text
    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    console = None


def print_msg(message="", color=None):
    """Print message with or without rich formatting."""
    if RICH_AVAILABLE:
        if color:
            console.print(f"[{color}]{message}[/{color}]")
        else:
            console.print(message)
    else:
        print(message)


def print_panel(title, border_color="cyan"):
    """Print panel with or without rich."""
    if RICH_AVAILABLE:
        console.print(Panel(
            Text(title, style="bold"),
            border_style=border_color,
            padding=(1, 2)
        ))
    else:
        print("=" * 60)
        print(f"  {title}")
        print("=" * 60)


def check_python_version():
    """Verifica que Python 3.11+ esté instalado."""
    if sys.version_info < (3, 11):
        print_msg("✗ CLIBOT requiere Python 3.11 o superior", "red")
        print_msg(f"   Versión actual: {sys.version}")
        sys.exit(1)
    print_msg(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", "green")


def create_venv(project_dir):
    """Crea el entorno virtual."""
    venv_path = project_dir / ".venv"
    if venv_path.exists():
        print_msg("✓ Entorno virtual ya existe", "green")
        return venv_path
    
    print_msg("Creando entorno virtual...")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        print_msg("✓ Entorno virtual creado", "green")
        return venv_path
    except subprocess.CalledProcessError as e:
        print_msg(f"✗ Error al crear entorno virtual: {e}", "red")
        sys.exit(1)


def check_dependencies_installed(venv_path):
    """Verifica si las dependencias ya están instaladas."""
    pip_path = venv_path / "bin" / "pip"
    try:
        result = subprocess.run(
            [str(pip_path), "list", "--format=freeze"],
            capture_output=True,
            text=True,
            check=True
        )
        installed = {line.split('==')[0].lower() for line in result.stdout.split('\n') if line}
        # Verificar algunas dependencias clave
        key_deps = ['pyyaml', 'rich', 'prompt-toolkit']
        return all(dep in installed for dep in key_deps)
    except Exception:
        return False


def install_dependencies(project_dir, venv_path):
    """Instala las dependencias."""
    pip_path = venv_path / "bin" / "pip"
    requirements_path = project_dir / "requirements.txt"
    
    if check_dependencies_installed(venv_path):
        print_msg("✓ Dependencias ya instaladas", "green")
    else:
        print_msg("Instalando dependencias...")
        try:
            if RICH_AVAILABLE:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console
                ) as progress:
                    task = progress.add_task("Instalando paquetes...", total=None)
                    subprocess.run([str(pip_path), "install", "-r", str(requirements_path)], check=True)
                    progress.update(task, completed=True)
            else:
                subprocess.run([str(pip_path), "install", "-r", str(requirements_path)], check=True)
            print_msg("✓ Dependencias instaladas", "green")
        except subprocess.CalledProcessError as e:
            print_msg(f"✗ Error al instalar dependencias: {e}", "red")
            sys.exit(1)
    
    # Instalar el paquete en modo editable
    print_msg("Verificando instalación de CLIBOT...")
    try:
        subprocess.run([str(pip_path), "install", "-e", str(project_dir)], check=True)
        print_msg("✓ CLIBOT instalado en modo editable", "green")
    except subprocess.CalledProcessError as e:
        print_msg(f"✗ Error al instalar CLIBOT: {e}", "red")
        sys.exit(1)


def check_voice_installed(venv_path):
    """Verifica si Vosk ya está instalado."""
    pip_path = venv_path / "bin" / "pip"
    try:
        result = subprocess.run(
            [str(pip_path), "list", "--format=freeze"],
            capture_output=True,
            text=True,
            check=True
        )
        installed = result.stdout.lower()
        return 'vosk' in installed
    except Exception:
        return False


def install_voice_dependencies(project_dir, venv_path):
    """Pregunta si desea instalar dependencias de voz."""
    if check_voice_installed(venv_path):
        print_msg("✓ Vosk ya está instalado", "green")
        response = input("\n¿Deseas reinstalar/actualizar Vosk? [s/N]: ").strip().lower()
        if response not in ('s', 'si', 'yes', 'y'):
            return
    
    response = input("\n¿Deseas instalar soporte de voz (Vosk)? [s/N]: ").strip().lower()
    if response not in ('s', 'si', 'yes', 'y'):
        print_msg("Omitiendo instalación de voz.", "dim")
        return
    
    pip_path = venv_path / "bin" / "pip"
    print_msg("Instalando dependencias de voz...")
    try:
        subprocess.run([str(pip_path), "install", "-e", f"{project_dir}[voice]"], check=True)
        print_msg("✓ Dependencias de voz instaladas", "green")
        
        # Instalar alsa-utils si está en Linux
        if sys.platform == "linux":
            if shutil.which("arecord"):
                print_msg("✓ alsa-utils ya está instalado", "green")
            else:
                print_msg("\nPara usar el micrófono necesitas alsa-utils:")
                print_msg("  sudo apt install alsa-utils")
                response = input("¿Deseas instalarlo ahora? [s/N]: ").strip().lower()
                if response in ('s', 'si', 'yes', 'y'):
                    try:
                        subprocess.run(["sudo", "apt", "install", "-y", "alsa-utils"], check=True)
                        print_msg("✓ alsa-utils instalado", "green")
                    except subprocess.CalledProcessError:
                        print_msg("⚠ No se pudo instalar alsa-utils. Instálalo manualmente con: sudo apt install alsa-utils", "yellow")
    except subprocess.CalledProcessError as e:
        print_msg(f"✗ Error al instalar dependencias de voz: {e}", "red")


def check_tts_installed(venv_path):
    """Verifica si pyttsx3 ya está instalado."""
    pip_path = venv_path / "bin" / "pip"
    try:
        result = subprocess.run(
            [str(pip_path), "list", "--format=freeze"],
            capture_output=True,
            text=True,
            check=True
        )
        installed = result.stdout.lower()
        return 'pyttsx3' in installed
    except Exception:
        return False


def install_tts_dependencies(project_dir, venv_path):
    """Pregunta si desea instalar respuesta de voz (TTS)."""
    if check_tts_installed(venv_path):
        print_msg("✓ pyttsx3 ya está instalado", "green")
        response = input("\n¿Deseas reinstalar/actualizar pyttsx3? [s/N]: ").strip().lower()
        if response not in ('s', 'si', 'yes', 'y'):
            return
    
    response = input("\n¿Deseas instalar respuesta de voz (TTS)? [s/N]: ").strip().lower()
    if response not in ('s', 'si', 'yes', 'y'):
        print_msg("Omitiendo instalación de respuesta de voz.", "dim")
        return
    
    pip_path = venv_path / "bin" / "pip"
    print_msg("Instalando dependencias de respuesta de voz (pyttsx3)...")
    try:
        subprocess.run([str(pip_path), "install", "-e", f"{project_dir}[tts]"], check=True)
        print_msg("✓ Respuesta de voz instalada", "green")
        print_msg("  Usa /voice on para activar la respuesta de voz en CLIBOT.")
    except subprocess.CalledProcessError as e:
        print_msg(f"✗ Error al instalar respuesta de voz: {e}", "red")


def setup_alias(project_dir, venv_path):
    """Configura el alias global 'clibot'."""
    print_msg("\nConfigurando comando global 'clibot'...")
    
    # Intentar usar ~/.local/bin
    local_bin = Path.home() / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)
    
    script_path = local_bin / "clibot"
    
    # Verificar si el script ya existe
    if script_path.exists():
        print_msg(f"✓ Script ya existe en {script_path}", "green")
        response = input("¿Deseas actualizarlo? [s/N]: ").strip().lower()
        if response not in ('s', 'si', 'yes', 'y'):
            return True
    
    script_content = f"""#!/usr/bin/env bash
"{venv_path}/bin/python" "{project_dir}/llmah.py" "$@"
"""
    
    try:
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        print_msg(f"✓ Script creado en {script_path}", "green")
        
        # Verificar si ~/.local/bin está en PATH
        shell_config = None
        if "SHELL" in os.environ:
            shell = os.environ["SHELL"]
            if "bash" in shell:
                shell_config = Path.home() / ".bashrc"
            elif "zsh" in shell:
                shell_config = Path.home() / ".zshrc"
        
        if shell_config and shell_config.exists():
            with open(shell_config, "r") as f:
                config_content = f.read()
            
            if ".local/bin" not in config_content:
                print_msg(f"\nAgregando ~/.local/bin a tu PATH en {shell_config}...")
                with open(shell_config, "a") as f:
                    f.write('\n# CLIBOT\nexport PATH="$HOME/.local/bin:$PATH"\n')
                print_msg(f"✓ PATH actualizado en {shell_config}", "green")
                print_msg(f"  Ejecuta: source {shell_config}")
            else:
                print_msg("✓ ~/.local/bin ya está en tu PATH", "green")
        else:
            print_msg("\n⚠ No se detectó tu configuración de shell.", "yellow")
            print_msg("  Asegúrate de que ~/.local/bin esté en tu PATH:")
            print_msg("  export PATH=\"$HOME/.local/bin:$PATH\"")
        
        return True
    except Exception as e:
        print_msg(f"✗ Error al configurar alias: {e}", "red")
        return False


def main():
    """Función principal de instalación."""
    print_panel("CLIBOT - Script de Instalación Automatizada", "cyan")
    print_msg()
    
    # Obtener directorio del proyecto
    project_dir = Path(__file__).parent.resolve()
    
    # Verificar Python
    check_python_version()
    
    # Crear entorno virtual
    venv_path = create_venv(project_dir)
    
    # Instalar dependencias
    install_dependencies(project_dir, venv_path)
    
    # Preguntar sobre voz
    install_voice_dependencies(project_dir, venv_path)
    
    # Preguntar sobre TTS
    install_tts_dependencies(project_dir, venv_path)
    
    # Configurar alias
    setup_alias(project_dir, venv_path)
    
    print_msg()
    print_panel("✓ Instalación completada", "green")
    print_msg()
    print_msg("Para usar CLIBOT:")
    print_msg("  1. Si configuraste el alias, ejecuta: source ~/.bashrc o source ~/.zshrc")
    print_msg("  2. Luego simplemente escribe: clibot")
    print_msg()
    print_msg("O si prefieres usar el entorno virtual directamente:")
    print_msg(f"  {venv_path}/bin/python {project_dir}/llmah.py")
    print_msg()
    print_msg("La primera vez que ejecutes CLIBOT, te preguntará si deseas")
    print_msg("instalar un modelo de IA (Ollama). Esto es opcional.")
    print_msg()


if __name__ == "__main__":
    main()
