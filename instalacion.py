#!/usr/bin/env python3
"""Script de instalación automatizada para CLIBOT.

Este script configura todo lo necesario para ejecutar CLIBOT:
- Crea el entorno virtual
- Instala dependencias
- Configura el alias global 'clibot'
- Instala dependencias opcionales de voz (si el usuario desea)
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def check_python_version():
    """Verifica que Python 3.11+ esté instalado."""
    if sys.version_info < (3, 11):
        print("❌ Error: CLIBOT requiere Python 3.11 o superior")
        print(f"   Versión actual: {sys.version}")
        sys.exit(1)
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} detectado")


def create_venv(project_dir):
    """Crea el entorno virtual."""
    venv_path = project_dir / ".venv"
    if venv_path.exists():
        print("✓ Entorno virtual ya existe")
        return venv_path
    
    print("Creando entorno virtual...")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        print("✓ Entorno virtual creado")
        return venv_path
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al crear entorno virtual: {e}")
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
        print("✓ Dependencias ya instaladas")
    else:
        print("Instalando dependencias...")
        try:
            subprocess.run([str(pip_path), "install", "-r", str(requirements_path)], check=True)
            print("✓ Dependencias instaladas")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error al instalar dependencias: {e}")
            sys.exit(1)
    
    # Instalar el paquete en modo editable
    print("Verificando instalación de CLIBOT...")
    try:
        subprocess.run([str(pip_path), "install", "-e", str(project_dir)], check=True)
        print("✓ CLIBOT instalado en modo editable")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al instalar CLIBOT: {e}")
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
        print("✓ Vosk ya está instalado")
        response = input("\n¿Deseas reinstalar/actualizar Vosk? [s/N]: ").strip().lower()
        if response not in ('s', 'si', 'yes', 'y'):
            return
    
    response = input("\n¿Deseas instalar soporte de voz (Vosk)? [s/N]: ").strip().lower()
    if response not in ('s', 'si', 'yes', 'y'):
        print("Omitiendo instalación de voz.")
        return
    
    pip_path = venv_path / "bin" / "pip"
    print("Instalando dependencias de voz...")
    try:
        subprocess.run([str(pip_path), "install", "-e", f"{project_dir}[voice]"], check=True)
        print("✓ Dependencias de voz instaladas")
        
        # Instalar alsa-utils si está en Linux
        if sys.platform == "linux":
            if shutil.which("arecord"):
                print("✓ alsa-utils ya está instalado")
            else:
                print("\nPara usar el micrófono necesitas alsa-utils:")
                print("  sudo apt install alsa-utils")
                response = input("¿Deseas instalarlo ahora? [s/N]: ").strip().lower()
                if response in ('s', 'si', 'yes', 'y'):
                    try:
                        subprocess.run(["sudo", "apt", "install", "-y", "alsa-utils"], check=True)
                        print("✓ alsa-utils instalado")
                    except subprocess.CalledProcessError:
                        print("⚠ No se pudo instalar alsa-utils. Instálalo manualmente con: sudo apt install alsa-utils")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al instalar dependencias de voz: {e}")


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
        print("✓ pyttsx3 ya está instalado")
        response = input("\n¿Deseas reinstalar/actualizar pyttsx3? [s/N]: ").strip().lower()
        if response not in ('s', 'si', 'yes', 'y'):
            return
    
    response = input("\n¿Deseas instalar respuesta de voz (TTS)? [s/N]: ").strip().lower()
    if response not in ('s', 'si', 'yes', 'y'):
        print("Omitiendo instalación de respuesta de voz.")
        return
    
    pip_path = venv_path / "bin" / "pip"
    print("Instalando dependencias de respuesta de voz (pyttsx3)...")
    try:
        subprocess.run([str(pip_path), "install", "-e", f"{project_dir}[tts]"], check=True)
        print("✓ Respuesta de voz instalada")
        print("  Usa /voice on para activar la respuesta de voz en CLIBOT.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al instalar respuesta de voz: {e}")


def setup_alias(project_dir, venv_path):
    """Configura el alias global 'clibot'."""
    print("\nConfigurando comando global 'clibot'...")
    
    # Intentar usar ~/.local/bin
    local_bin = Path.home() / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)
    
    script_path = local_bin / "clibot"
    
    # Verificar si el script ya existe
    if script_path.exists():
        print(f"✓ Script ya existe en {script_path}")
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
        print(f"✓ Script creado en {script_path}")
        
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
                print(f"\nAgregando ~/.local/bin a tu PATH en {shell_config}...")
                with open(shell_config, "a") as f:
                    f.write('\n# CLIBOT\nexport PATH="$HOME/.local/bin:$PATH"\n')
                print(f"✓ PATH actualizado en {shell_config}")
                print(f"  Ejecuta: source {shell_config}")
            else:
                print("✓ ~/.local/bin ya está en tu PATH")
        else:
            print("\n⚠ No se detectó tu configuración de shell.")
            print("  Asegúrate de que ~/.local/bin esté en tu PATH:")
            print("  export PATH=\"$HOME/.local/bin:$PATH\"")
        
        return True
    except Exception as e:
        print(f"❌ Error al configurar alias: {e}")
        return False


def main():
    """Función principal de instalación."""
    print("=" * 60)
    print("  CLIBOT - Script de Instalación Automatizada")
    print("=" * 60)
    print()
    
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
    
    print()
    print("=" * 60)
    print("  ✓ Instalación completada")
    print("=" * 60)
    print()
    print("Para usar CLIBOT:")
    print("  1. Si configuraste el alias, ejecuta: source ~/.bashrc o source ~/.zshrc")
    print("  2. Luego simplemente escribe: clibot")
    print()
    print("O si prefieres usar el entorno virtual directamente:")
    print(f"  {venv_path}/bin/python {project_dir}/llmah.py")
    print()
    print("La primera vez que ejecutes CLIBOT, te preguntará si deseas")
    print("instalar un modelo de IA (Ollama). Esto es opcional.")
    print()


if __name__ == "__main__":
    main()
