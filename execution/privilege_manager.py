"""Elevation is explicit; this helper never stores credentials or runs sudo itself."""
import shutil, os
def elevation_available():return os.geteuid()==0 or shutil.which('sudo') is not None
def explanation():return 'La operación requiere privilegios. Ejecútala desde un flujo sudo interactivo revisado; CLIBOT no almacena contraseñas.'
