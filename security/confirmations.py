"""Interactive confirmation policy; non-interactive mode defaults to deny."""
def confirm(description,risk,input_fn=input):
    try:return input_fn(f'Confirm {description} ({risk})? [y/N] ').strip().lower() in {'y','yes','si','sí'}
    except (EOFError,KeyboardInterrupt):return False
