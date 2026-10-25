"""Drop-in capability modules implementing ``register(registry)``."""
import importlib, pkgutil
_loaded=False
def load(registry):
    global _loaded
    if _loaded:return
    for item in pkgutil.iter_modules(__path__):
        if item.name.startswith('_'):continue
        module=importlib.import_module(f'{__name__}.{item.name}')
        register=getattr(module,'register',None)
        if not callable(register):raise TypeError(f'{module.__name__} must define register(registry)')
        register(registry)
    _loaded=True
