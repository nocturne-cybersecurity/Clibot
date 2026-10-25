"""JSON and Markdown reports from supplied observed evidence."""
import json
from pathlib import Path
from datetime import datetime, timezone
from security.redaction import redact_data
def report(title,scope,findings,output,format='json'):
    data=redact_data({'title':title,'scope':scope,'timestamp':datetime.now(timezone.utc).isoformat(),'findings':findings})
    p=Path(output)
    if p.exists():raise FileExistsError(p)
    if format=='json':p.write_text(json.dumps(data,indent=2,ensure_ascii=False,default=str))
    elif format=='markdown':p.write_text('# '+title+'\n\n- Scope: '+str(scope)+'\n- Generated: '+data['timestamp']+'\n\n## Observations\n\n'+'\n'.join(f'- {x}' for x in findings)+'\n')
    else:raise ValueError('format must be json or markdown')
    return {'path':str(p),'findings':len(findings)}
