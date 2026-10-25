"""Verification helpers based on observed operation results."""
from pathlib import Path
class Verifier:
    def verify(self,operation,result):
        if not result.success:return False
        if operation.capability=='filesystem' and operation.name in {'create','mkdir','copy','move','extract','archive'}:
            target=operation.arguments.get('destination') or operation.arguments.get('path') or operation.arguments.get('archive')
            return Path(target).expanduser().exists() if target else False
        return result.verified is True
