"""Error handling with recovery suggestions and corrections."""
import re
from pathlib import Path


class ErrorHandler:
    """Handle errors with intelligent suggestions for recovery."""

    ERROR_SUGGESTIONS = {
        'FileNotFoundError': [
            'Verifica que la ruta sea correcta',
            'Usa rutas absolutas (ej: /home/usuario/archivo.txt)',
            'Verifica que el archivo o carpeta exista',
        ],
        'PermissionError': [
            'Ejecuta con sudo si necesitas permisos de administrador',
            'Verifica los permisos del archivo o carpeta',
            'Asegúrate de tener acceso de lectura/escritura',
        ],
        'FileExistsError': [
            'El archivo o carpeta ya existe',
            'Usa un nombre diferente',
            'Elimina el archivo existente primero si quieres reemplazarlo',
        ],
        'NotADirectoryError': [
            'La ruta especificada no es un directorio',
            'Verifica que la ruta termine con / si es una carpeta',
        ],
        'IsADirectoryError': [
            'La ruta especificada es un directorio, no un archivo',
            'Usa una ruta de archivo específica',
        ],
        'CommandNotFoundError': [
            'El comando no está instalado',
            'Instala el paquete correspondiente con apt, pip o npm',
            'Verifica que el comando esté en tu PATH',
        ],
        'ConnectionError': [
            'No hay conexión a internet',
            'Verifica tu conexión de red',
            'Intenta de nuevo más tarde',
        ],
        'TimeoutError': [
            'La operación tardó demasiado',
            'Intenta con un timeout mayor',
            'Verifica que el sistema no esté sobrecargado',
        ],
    }

    COMMAND_CORRECTIONS = {
        'ls': ['lista', 'listar', 'muestra'],
        'cd': ['cambia directorio', 've a'],
        'mkdir': ['crea carpeta', 'crear directorio'],
        'rm': ['elimina', 'borra', 'delete'],
        'mv': ['mueve', 'mover'],
        'cp': ['copia', 'copiar'],
        'cat': ['lee', 'leer', 'muestra contenido'],
        'grep': ['busca', 'buscar'],
        'chmod': ['cambia permisos', 'cambiar permisos'],
        'chown': ['cambia propietario', 'cambiar dueño'],
    }

    @classmethod
    def get_suggestions(cls, error):
        """Get suggestions for a given error."""
        error_type = type(error).__name__
        suggestions = cls.ERROR_SUGGESTIONS.get(error_type, [])
        
        # Add specific suggestions based on error message
        error_msg = str(error).lower()
        
        if 'no such file' in error_msg or 'not found' in error_msg:
            suggestions.append('Verifica la ortografía de la ruta')
            suggestions.append('Usa tab completion para autocompletar rutas')
        
        if 'permission denied' in error_msg:
            suggestions.append('Intenta: sudo llmah "tu comando"')
            suggestions.append('Verifica que no seas root cuando no es necesario')
        
        if 'command not found' in error_msg:
            cmd_match = re.search(r"command '(\w+)' not found", error_msg)
            if cmd_match:
                cmd = cmd_match.group(1)
                suggestions.append(f'Para instalar {cmd}: sudo apt install {cmd}')
        
        return suggestions

    @classmethod
    def suggest_command(cls, command):
        """Suggest CLIBOT equivalents for shell commands."""
        for shell_cmd, clibot_cmds in cls.COMMAND_CORRECTIONS.items():
            if shell_cmd in command.lower():
                return f'Trata con: {", ".join(clibot_cmds)}'
        return None

    @classmethod
    def format_error(cls, error, context=None):
        """Format error with suggestions."""
        error_type = type(error).__name__
        error_msg = str(error)
        
        output = [f'Error: {error_type}']
        output.append(f'Detalles: {error_msg}')
        
        # Agregar explicación de qué pasó
        explanation = cls._get_explanation(error, error_msg)
        if explanation:
            output.append(f'\nQué pasó: {explanation}')
        
        suggestions = cls.get_suggestions(error)
        if suggestions:
            output.append('\nSugerencias:')
            for i, suggestion in enumerate(suggestions, 1):
                output.append(f'  {i}. {suggestion}')
        
        if context:
            cmd_suggestion = cls.suggest_command(context)
            if cmd_suggestion:
                output.append(f'\nAlternativa: {cmd_suggestion}')
        
        return '\n'.join(output)

    @classmethod
    def _get_explanation(cls, error, error_msg):
        """Get human-readable explanation of what happened."""
        error_type = type(error).__name__
        
        if 'FileNotFoundError' in error_type:
            return 'El archivo o directorio solicitado no existe en la ruta indicada.'
        if 'PermissionError' in error_type:
            return 'No tienes permisos suficientes para realizar esta operación. Intenta con sudo si es necesario.'
        if 'FileExistsError' in error_type:
            return 'Ya existe un archivo o directorio con ese nombre en la ubicación especificada.'
        if 'NotADirectoryError' in error_type:
            return 'La ruta especificada no es un directorio, pero se esperaba que lo fuera.'
        if 'IsADirectoryError' in error_type:
            return 'La ruta especificada es un directorio, pero se esperaba que fuera un archivo.'
        if 'RuntimeError' in error_type:
            if 'git' in error_msg.lower():
                return 'No se pudo ejecutar el comando de Git. Asegúrate de que Git esté instalado.'
            if 'docker' in error_msg.lower():
                return 'No se pudo ejecutar el comando de Docker. Asegúrate de que Docker esté instalado y corriendo.'
            return 'Ocurrió un error durante la ejecución de la operación.'
        if 'ValueError' in error_type:
            return 'El valor proporcionado no es válido para esta operación.'
        if 'TimeoutError' in error_type:
            return 'La operación tardó demasiado tiempo y fue cancelada.'
        if 'ConnectionError' in error_type or 'URLError' in error_type:
            return 'No se pudo conectar al servicio o servidor remoto. Verifica tu conexión a internet.'
        if 'HTTPError' in error_type:
            return 'El servidor remoto respondió con un error HTTP.'
        return None


def handle_error(error, context=None):
    """Handle an error with formatted output and suggestions."""
    return ErrorHandler.format_error(error, context)
