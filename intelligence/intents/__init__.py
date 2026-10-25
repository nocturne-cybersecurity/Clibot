"""Drop-in natural-language intent plugins.

Add a module with ``register(router)`` here. It is imported once during parser
initialization; handlers should return a structured Plan or None.
"""
import importlib, pkgutil
_loaded=False
def load(router):
    global _loaded
    if _loaded:return router
    for module in pkgutil.iter_modules(__path__):
        if module.name.startswith('_'):continue
        plugin=importlib.import_module(f'{__name__}.{module.name}')
        register=getattr(plugin,'register',None)
        if not callable(register):raise TypeError(f'{plugin.__name__} must define register(router)')
        register(router)
    _loaded=True
    return router
