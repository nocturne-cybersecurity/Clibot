"""Current request and bounded conversational context."""
from collections import deque
import re
import unicodedata
from security.redaction import redact
class Context:
    def __init__(self,limit=50): self.requests=deque(maxlen=limit); self.events=deque(maxlen=limit); self.last_results=[]; self.last_plan=None; self.last_exchange=None; self.last_operation_event=None; self.entities={}; self.pending=None; self.dialogue_turn=0; self.last_question=None; self.last_search=None; self.last_answer=None; self.last_error=None; self.last_command=None; self.session_start=None; self.user_preferences={}; self.task_context={}
    def remember(self,request,results=(),plan=None): self.last_results=list(results); self.last_plan=plan
    def record_exchange(self,request,response):
        plan=response.get('plan')
        results=response.get('results',())
        operations=[]
        if plan:
            operations=[{'capability':op.capability,'name':op.name,'description':op.description} for op in plan.operations]
        outcomes=[{'success':r.success,'status':r.status.value,'error_category':r.error_category,'exit_code':r.exit_code,'duration':r.duration,'detail':redact(r.stderr or r.stdout)[:400]} for r in results]
        event={'request':redact(request)[:500],'operations':operations,'results':outcomes,'message':redact(response.get('message') or response.get('clarification') or response.get('error') or '')[:500]}
        self.requests.append(redact(request)[:500]);self.events.append(event);self.last_exchange=event
        if operations and outcomes:self.last_operation_event=event
        
        # Guardar último error si hubo
        if response.get('error'):
            self.last_error=response.get('error')
        
        # Guardar último comando ejecutado
        if operations and operations[0].get('capability') == 'development' and operations[0].get('name') == 'execute_command':
            self.last_command=operations[0].get('description')
        
        clean_request=redact(request)[:500]
        normalized_question=''.join(c for c in unicodedata.normalize('NFKD',clean_request.lower()) if not unicodedata.combining(c)).strip(' ¿¡')
        meaningful_question = len(normalized_question.split()) >= 3 and bool(re.match(
            r'(?i)^\s*(?:cual|que|quien|donde|cuando|como|cuanto|por que|what|who|where|when|how|why)\b', normalized_question
        ))
        capability_question = bool(re.search(r'(?i)\b(?:puedes|sabes)\b.*\b(?:buscar|google)\b', normalized_question))
        if meaningful_question and not capability_question:
            self.last_question=clean_request
        self.last_answer=event['message'] or None
        for result in results:
            value=result.data.get('value') if isinstance(result.data,dict) else None
            if isinstance(value,dict) and isinstance(value.get('results'),list) and isinstance(value.get('query'),str):
                self.last_search={'query':value['query'][:500],'results':value['results'][:5]}
                self.last_question=value['query'][:500]
    def clear(self): self.requests.clear(); self.events.clear(); self.last_results.clear(); self.last_plan=None; self.last_exchange=None; self.last_operation_event=None; self.entities.clear(); self.pending=None; self.dialogue_turn=0; self.last_question=None; self.last_search=None; self.last_answer=None; self.last_error=None; self.last_command=None; self.user_preferences.clear(); self.task_context.clear()
    def set_entity(self,key,value): self.entities[key]=value
    def get_entity(self,key,default=None): return self.entities.get(key,default)
    def set_preference(self,key,value): self.user_preferences[key]=value
    def get_preference(self,key,default=None): return self.user_preferences.get(key,default)
    def set_task_context(self,key,value): self.task_context[key]=value
    def get_task_context(self,key,default=None): return self.task_context.get(key,default)
    def get_summary(self):
        """Get a summary of the current session context."""
        return {
            'request_count': len(self.requests),
            'last_question': self.last_question,
            'last_answer': self.last_answer,
            'entities': dict(self.entities),
            'preferences': dict(self.user_preferences),
            'task_context': dict(self.task_context),
        }
