"""Progress bars for long-running operations."""
import sys
import time
import threading


class ProgressBar:
    """Simple progress bar for terminal output."""

    def __init__(self, total=100, description='', width=40):
        self.total = total
        self.current = 0
        self.description = description
        self.width = width
        self.start_time = time.time()
        self._lock = threading.Lock()
        self._active = False

    def update(self, increment=1):
        """Update progress by increment."""
        with self._lock:
            self.current = min(self.current + increment, self.total)
            if self._active:
                self._draw()

    def set_progress(self, value):
        """Set progress to specific value."""
        with self._lock:
            self.current = min(value, self.total)
            if self._active:
                self._draw()

    def start(self):
        """Start displaying the progress bar."""
        with self._lock:
            self._active = True
            self._draw()

    def stop(self):
        """Stop displaying the progress bar."""
        with self._lock:
            self._active = False
            self._draw()  # Final draw at 100%
            sys.stdout.write('\n')
            sys.stdout.flush()

    def _draw(self):
        """Draw the progress bar."""
        if not sys.stdout.isatty():
            return

        percent = self.current / self.total if self.total > 0 else 0
        filled = int(self.width * percent)
        bar = '█' * filled + '░' * (self.width - filled)
        
        elapsed = time.time() - self.start_time
        if self.current > 0:
            eta = (elapsed / self.current) * (self.total - self.current)
            eta_str = f'{int(eta)}s'
        else:
            eta_str = '--'
        
        line = f'\r{self.description} [{bar}] {percent:.1%} ETA: {eta_str}'
        sys.stdout.write(line)
        sys.stdout.flush()


def with_progress(iterable, description='Procesando'):
    """Wrap an iterable with a progress bar."""
    total = len(iterable) if hasattr(iterable, '__len__') else None
    if total is None:
        return iterable
    
    bar = ProgressBar(total=total, description=description)
    bar.start()
    
    for item in iterable:
        yield item
        bar.update()
    
    bar.stop()
