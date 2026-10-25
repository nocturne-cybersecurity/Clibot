"""Small append-only JSONL audit records with restrictive permissions."""
import json, os
from pathlib import Path
from datetime import datetime, timezone
from .redaction import redact_data
class AuditLog:
    def __init__(self,path): self.path=Path(path).expanduser()
    def record(self,event):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        payload={'timestamp':datetime.now(timezone.utc).isoformat(),'event':redact_data(event)}
        fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        try:
            os.fchmod(fd,0o600)
            os.write(fd,(json.dumps(payload,ensure_ascii=False)+'\n').encode())
        finally:os.close(fd)
