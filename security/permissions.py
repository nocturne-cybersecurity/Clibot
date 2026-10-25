"""Least-privilege policy helpers."""
def requires_confirmation(risk): return getattr(risk,'value',risk) in {'moderate','high','destructive'}
def current_user_is_root():
    import os
    return hasattr(os,'geteuid') and os.geteuid()==0
