"""Optional future local inference adapter contract; no model is loaded by default."""
class LocalModel:
    def available(self):return False
    def interpret(self,text):raise RuntimeError('No local model adapter is configured; deterministic rules remain available')
