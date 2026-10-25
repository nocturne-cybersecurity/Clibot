"""Bounded local JSON history summaries."""
import json, os
from pathlib import Path
from security.redaction import redact
class OperationHistory:
    def __init__(self,path,limit=100):self.path=Path(path).expanduser();self.limit=max(1,limit)
    def add(self,request,results):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        rows=self.search(); rows.append({'request':redact(request)[:500],'results':[{'success':r.success,'status':r.status.value,'error':r.error_category,'summary':redact(r.stdout)[:500]} for r in results]})
        rows=rows[-self.limit:]; fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as f:json.dump(rows,f,ensure_ascii=False)
    def search(self,query=''):
        if not self.path.exists():return []
        try: rows=json.loads(self.path.read_text())
        except (OSError,ValueError):return []
        return [x for x in rows if query.casefold() in x.get('request','').casefold()][-self.limit:]
    def clear(self):
        if self.path.exists():self.path.unlink()
