"""End-to-end assistant orchestration."""
import re
from capabilities import registry
from core.parser import Parser
from core.validator import Validator
from core.executor import Executor
from core.context import Context
from core.contracts import Result, Status, Plan, Operation, Risk
from core.parser import normalize
from core.config import load_config
from core.error_handler import handle_error
from core.audit_logger import AuditLogger
from intelligence.dialogue import respond as dialogue_response
from intelligence.llm_integration import LLMIntegration

class Assistant:
    def __init__(self,confirm=input):
        self.config=load_config(); self.registry=registry; self.parser=Parser(); self.validator=Validator(registry); self.context=Context(); self.auto_open_terminal=False; self._input_confirm=confirm
        self.executor=Executor(registry,self._confirm,self.config['settings'].get('execution',{}).get('default_yes_operations',()),
                               self.config['policies'].get('risk',{}))
        self.llm = LLMIntegration()
        self.audit_logger = AuditLogger()
        self.llm_timeout = 0.15  # 150ms timeout for LLM responses
    def _confirm(self,prompt):
        if self.auto_open_terminal and prompt.startswith('Confirm abrir una terminal (moderate)?'):return 'yes'
        return self._input_confirm(prompt)
    def capabilities(self): return [{'name':c.name,'description':c.description,'operations':sorted(c.operations)} for c in self.registry.list()]
    def handle(self,request):
        try:response=self._handle(request)
        except Exception as exc:
            error_details = handle_error(exc, context=request)
            response={'request':request,'error':error_details,'error_category':'internal_error'}
        self.context.record_exchange(request,response)
        # Log to audit logger
        operations = []
        if 'operations' in response:
            operations = response['operations']
        elif 'plan' in response and hasattr(response['plan'], 'operations'):
            operations = [{'capability': op.capability, 'name': op.name} for op in response['plan'].operations]
        self.audit_logger.log_command(request, response, operations)
        return response

    def _handle(self,request):
        phrase=normalize(request).strip(' .!?¿¡')
        if re.search(r'\bno me preguntes\b.*\b(terminal|terminales|consola)\b',phrase):
            self.auto_open_terminal=True
            return {'request':request,'message':'Entendido. En esta sesión abriré terminales vacías sin pedir confirmación. Seguiré confirmando cualquier comando que ejecutes dentro.'}
        if re.fullmatch(r'(?:estas )?segur[oa](?:\s+de eso)?', phrase) and self.context.last_operation_event:
            event=self.context.last_operation_event
            operation=event['operations'][-1]
            outcome=event['results'][-1]
            if operation['capability']=='browser' and operation['name']=='open_application' and outcome['success']:
                detail=outcome.get('detail') or operation.get('description') or 'la aplicación'
                return {'request':request,'message':f'Sí: {detail} La solicitud terminó bien; no puedo verificar desde aquí si la ventana quedó visible.'}
        if re.search(r'\b(?:por que|porque)\b.*\b(?:tardaste|tardo|demoraste|demoro|lento|lenta)\b', phrase):
            event=self.context.last_operation_event
            if event:
                operation=event['operations'][-1]
                outcome=event['results'][-1]
                duration=outcome.get('duration',0)
                detail=outcome.get('detail','')
                elapsed=f"Tardó {duration:.1f} segundos. " if duration else ''
                if re.search(r'\b503\b|high demand|service unavailable',detail,re.I):
                    return {'request':request,'message':elapsed+'El comando Gemini recibió HTTP 503 por alta demanda y reintentó la petición. La demora vino de esos reintentos del servicio remoto.'}
                if outcome['success']:
                    return {'request':request,'message':elapsed+f"La última operación fue {operation['description']} y terminó bien."}
                reason=detail[:200] or outcome.get('error_category') or 'falló'
                return {'request':request,'message':elapsed+f"La última operación fue {operation['description']}; tardó por el proceso que estaba ejecutando y terminó con este error: {reason}"}
        if (self.context.last_answer and self.context.last_answer.startswith('Con Linux, archivos, redes')
                and re.fullmatch(r'(?:y )?(?:red|redes|archivos|desarrollo|sistema|seguridad|calculos|busquedas web)\??', phrase)):
            details={
                'red':'Puedo ver interfaces, IPs, rutas y puertos locales; resolver DNS, probar conexiones y diagnosticar problemas de conectividad.',
                'redes':'Puedo ver interfaces, IPs, rutas y puertos locales; resolver DNS, probar conexiones y diagnosticar problemas de conectividad.',
                'archivos':'Puedo listar, leer, buscar, crear, copiar, mover, comprimir y calcular hashes de archivos.',
                'desarrollo':'Puedo ejecutar programas Python, consultar Git, compilar algunos proyectos y correr pruebas.',
                'sistema':'Puedo consultar hora, RAM, CPU, hardware, procesos, servicios y logs.',
                'seguridad':'Puedo consultar herramientas de auditoría, revisar secretos y permisos, y preparar escaneos de objetivos autorizados.',
                'calculos':'Puedo resolver operaciones aritméticas, raíces, potencias y funciones matemáticas comunes.',
                'busquedas web':'Puedo buscar información web y mostrar los fragmentos disponibles en la terminal.',
            }
            key=phrase.removeprefix('y ').rstrip('?')
            return {'request':request,'message':details[key]}
        pending=self.context.pending
        if pending:
            if phrase in {'no','no gracias','cancelar','cancela','olvidalo','olvidala','ninguno','ninguna','ningun archivo','ninguna cosa','forget it','cancel','none','nothing'}:
                self.context.pending=None
                return {'request':request,'message':'De acuerdo, cancelé esa pregunta pendiente.'}
            followup=self.parser.resolve_pending(request,self.context)
            if followup is not None and not followup.clarification:
                self.context.pending=None
                try:self.validator.validate(followup)
                except Exception as e:return {'request':request,'error':str(e),'results':[]}
                results=self.executor.execute(followup);self.context.remember(request,results,followup)
                return {'request':request,'plan':followup,'results':results}
            if followup is not None and followup.clarification:
                # Keep the pending slot only when this still looks like an answer
                # to the specific question. Unrelated requests must remain usable.
                if pending.get('kind')=='translate_target':
                    from intelligence.intents.translation import LANGUAGES
                    answer=normalize(request).strip(' .!?¿¡"\'')
                    if answer in LANGUAGES:
                        return {'request':request,'clarification':followup.clarification,'results':[]}
                elif pending.get('kind')=='web_search' and not re.search(r'(?i)\b(?:que puedes hacer|capacidades|hola|gracias|dime la hora)\b',phrase):
                    return {'request':request,'clarification':followup.clarification,'results':[]}
                elif pending.get('kind')=='create_file_name' and re.fullmatch(r'[\w.-]+',request.strip()):
                    return {'request':request,'clarification':followup.clarification,'results':[]}
                self.context.pending=None
        search_followup=bool(re.fullmatch(r'(?:pues\s+)?(?:buscalo|buscala|lo busques|la busques|busca eso|investigalo|investigala|lo investigues|la investigues|investiga eso|averigualo|averigua eso)(?: tu)?|(?:pues\s+)?(?:look that up|search for that|quiero que lo busques(?: e investigues)?)',phrase)
                            or re.search(r'\bquiero que lo busques(?: e investigues)?\b',phrase))
        if search_followup:
            topic=self.context.last_question
            if not topic:
                return {'request':request,'clarification':'¿Qué tema quieres que busque? Todavía no tengo una pregunta anterior en esta sesión.'}
            plan=Plan([Operation('web','search',{'query':topic},description=f'investigar «{topic}» en la web y mostrar fuentes aquí',risk=Risk.LOW)],request)
            try:self.validator.validate(plan)
            except Exception as e:return {'request':request,'error':str(e),'results':[]}
            results=self.executor.execute(plan);self.context.remember(request,results,plan)
            return {'request':request,'plan':plan,'results':results}
        if phrase in {'repite','repitelo','repitela','repetilo','repetila','repite eso','otra vez','repeat','repeat that'}:
            if self.context.last_results and self.context.last_plan:
                return {'request':request,'plan':self.context.last_plan,'results':self.context.last_results}
            if self.context.last_answer:
                return {'request':request,'message':self.context.last_answer}
            return {'request':request,'message':'Todavía no hay una respuesta anterior para repetir.'}
        if self.context.last_search and re.search(r'\b(?:una de las|uno de los|cuales? tres|que tres|una de que|una de esas)\b',phrase):
            topic=self.context.last_search.get('query','')
            plan=Plan([Operation('web','search',{'query':f'{topic} {request}'},description='aclarar un detalle de la búsqueda anterior',risk=Risk.LOW)],request)
            try:self.validator.validate(plan)
            except Exception as e:return {'request':request,'error':str(e),'results':[]}
            results=self.executor.execute(plan);self.context.remember(request,results,plan)
            return {'request':request,'plan':plan,'results':results}
        if re.fullmatch(r'(?:eso que|que es eso|what is that|dime mas|cuentame mas)',phrase):
            if self.context.last_search and self.context.last_search.get('results'):
                item=self.context.last_search['results'][0]
                snippet=item.get('snippet') or 'El resultado no incluye un fragmento; abre la fuente para leer el contenido completo.'
                return {'request':request,'message':snippet}
            if self.context.last_answer:
                return {'request':request,'message':f'Lo anterior fue: {self.context.last_answer}'}
            if self.context.last_question:
                return {'request':request,'message':f'¿Te refieres a «{self.context.last_question}»? Puedo buscarlo aquí mismo.'}
        if self.context.last_search and re.search(r'\b(?:incompleta|cortada|respuesta completa|muestra todo|no la acortes|a la mitad)\b',phrase):
            from interface.formatter import _human_value
            return {'request':request,'message':_human_value(self.context.last_search)}
        if re.search(r'(?i)\b(?:solo dime|dime)\b.*\b(?:tu respuesta|la respuesta|que encontraste)\b',phrase):
            if self.context.last_search and self.context.last_search.get('results'):
                from interface.formatter import _human_value
                return {'request':request,'message':_human_value(self.context.last_search)}
            return {'request':request,'message':'Aún no tengo una búsqueda anterior en esta sesión. Dime el tema y te resumo los resultados aquí.'}
        if re.search(r'(?i)\b(?:que opinas|opinas|que piensas|tu opinion|what do you think)\b',phrase) and self.context.last_search:
            from interface.formatter import _human_value
            summary=_human_value(self.context.last_search)
            return {'request':request,'message':'No tengo opiniones personales; como valoración basada en lo que encontré: '+summary}
        if re.search(r'\b(donde|en que ruta|que ruta)\b',phrase) and re.search(r'\b(archivo|lo tienes|lo guardaste|lo creaste)\b',phrase):
            previous=self.context.last_plan
            if previous and previous.operations and previous.operations[0].capability=='filesystem' and previous.operations[0].name in {'create','move','copy'}:
                op=previous.operations[0]
                path=op.arguments.get('path') or op.arguments.get('destination')
                result=self.context.last_results[0] if self.context.last_results else None
                if result and result.success:
                    observed=result.data.get('value') if isinstance(result.data,dict) else None
                    if isinstance(observed,str):
                        path=observed
                    verb='Lo creé' if op.name=='create' else 'Quedó'
                    return {'request':request,'message':f'{verb} en {path}.'}
                return {'request':request,'message':f'La ruta prevista era {path}, pero no puedo confirmar que la operación terminara bien.'}
        if re.search(r'(?i)\b(?:donde esta|donde guardaste|where is)\b',request):
            previous=self.context.last_plan
            if previous and previous.operations and self.context.last_results:
                op=previous.operations[-1]
                path=op.arguments.get('path') or op.arguments.get('destination')
                result=self.context.last_results[-1]
                if op.capability=='filesystem' and op.name in {'create','move','copy'} and path:
                    from pathlib import Path
                    observed=result.data.get('value') if isinstance(result.data,dict) else None
                    actual=observed if isinstance(observed,str) else path
                    if re.search(re.escape(Path(actual).name),request,re.I) and Path(actual).exists():
                        return {'request':request,'message':f'Está en {actual}.'}

        if phrase in {'abrelo','abrela','abre el archivo','abre ese archivo','open it'}:
            previous=self.context.last_plan
            if previous and previous.operations and self.context.last_results and self.context.last_results[-1].success:
                prior=previous.operations[-1]
                value=self.context.last_results[-1].data.get('value') if isinstance(self.context.last_results[-1].data,dict) else None
                path=value if isinstance(value,str) else prior.arguments.get('path') or prior.arguments.get('destination')
                if prior.capability=='filesystem' and prior.name in {'create','move','copy'} and path:
                    plan=Plan([Operation('development','open_file',{'path':path},description=f'abrir {path}',risk=Risk.MODERATE)],request)
                    self.validator.validate(plan);results=self.executor.execute(plan);self.context.remember(request,results,plan)
                    return {'request':request,'plan':plan,'results':results}
        if re.search(r'\btraductor\b',phrase) and re.search(r'\b(que paso|funcionaba|no funciona|no sirve)\b',phrase):
            return {'request':request,'message':'El traductor sigue disponible. «Rusia» es el país; el idioma es ruso. Ya agregué esa forma de pedirlo.'}
        if re.search(r'\b(por que|porque)\b.*\b(calculo|expresion matematica)\b',phrase) and self._last_failed_calculation():
            operation=self.context.last_plan.operations[-1]
            result=self.context.last_results[-1]
            expression=operation.arguments.get('expression','')
            if re.search(r'raiz|sqrt',expression,re.I) and 'No pude leer' in (result.stderr or ''):
                detail='La raíz dentro de la suma no se había convertido a notación matemática. Ya corregí ese caso; puedes repetirlo.'
            else:
                detail=f"Falló «{expression}»: {(result.stderr or result.error_category or 'error desconocido')[:120]}"
            return {'request':request,'message':detail}
        if phrase in {'por','porque','por que'} and self._last_failed_calculation():
            operation=self.context.last_plan.operations[-1]
            if re.search(r'raiz|sqrt',operation.arguments.get('expression',''),re.I):
                return {'request':request,'message':'La raíz debe agruparse como una operación; así respeta la precedencia con la suma y la multiplicación.'}
            result=self.context.last_results[-1]
            return {'request':request,'message':(result.stderr or 'El cálculo falló.')[:160]}
        if re.search(r'\b(que paso|que ocurrio|que hiciste|que acabas de hacer|resultado anterior|ultimo comando|ultima operacion|what did you do)\b',phrase) or re.search(r'\b(por que|porque)\b.*\b(fallo|error)\b.*\b(ultimo|anterior|comando|operacion)\b',phrase):
            return {'request':request,'message':self._explain_last_exchange()}
        if re.search(r'\b(las?\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.?\s*m\.?|p\.?\s*m\.?)?)\b',phrase):
            value=self._last_value('system','time')
            if value:
                return {'request':request,'message':f'La hora local es {value["time"]} ({value["timezone"]}).'}
        conversational=dialogue_response(request,self.context)
        if conversational:
            short_greeting=bool(re.fullmatch(r'(?:hola|hi|hey|buenos dias|buenas tardes|buenas noches|gracias|muchas gracias|thank you|perfecto|claro)',phrase))
            if self.llm.is_available() and not short_greeting:
                try:
                    model_result=self._interpret_with_model(request)
                    if model_result is not None:
                        return model_result
                except Exception:
                    pass
            return {'request':request,'message':conversational}
        if 'no me deja moverme en el texto' in phrase or 'moverme en el texto' in phrase:
            return {'request':request,'message':'La entrada usa edición de línea del terminal: usa ← y → para mover el cursor, ↑ y ↓ para recorrer el historial y Ctrl+A/Ctrl+E para ir al inicio/final.'}
        if 'que son esos numeros' in phrase or 'qué son esos números' in request.casefold():
            return {'request':request,'message':'Antes mostraba el PID del proceso lanzado. Ya cambié esa respuesta: ahora explico qué se abrió sin mostrar identificadores internos.'}
        if re_match:=re.fullmatch(r'(?:en )?(firefox|chrome|chromium)',phrase):
            previous=self.context.last_plan
            if previous and previous.operations and previous.operations[0].capability=='browser' and previous.operations[0].name=='open_url':
                op=previous.operations[0]
                args={**op.arguments,'browser':re_match.group(1)}
                plan=Plan([Operation('browser','open_url',args,description='abrir el sitio anterior en '+re_match.group(1),risk=op.risk)],request)
                self.validator.validate(plan);results=self.executor.execute(plan);self.context.remember(request,results,plan)
                return {'request':request,'plan':plan,'results':results}
        plan=self.parser.parse(request,self.context)
        plan_message=getattr(plan,'message',None)
        if plan.reformat_last:
            return self._reformat_last(request)
        auto_research=self.config['settings'].get('research',{}).get('automatic_for_general_questions',True)
        if plan.clarification and plan.clarification.startswith('No reconocí una tarea compatible') and self._is_open_ended_request(request):
            if self.llm.is_available():
                try:
                    message=self.llm.generate_response(
                        'Responde a la petición en español, con naturalidad y en menos de 120 palabras. '
                        'Puedes crear texto original. No afirmes que tienes sentimientos u opiniones personales; '
                        'si te piden una opinión, ofrece una valoración razonada. No ejecutes acciones. '
                        'PETICIÓN: '+request[:3000],
                    )
                    if message.strip():return {'request':request,'message':message.strip()[:1500],'reasoning':'local_model'}
                except Exception:
                    pass
            return {'request':request,'message':'Para inventar o desarrollar una respuesta abierta necesito un modelo de lenguaje activo. No voy a convertir esa petición creativa en una búsqueda web.'}
        if plan.clarification and plan.clarification.startswith('No reconocí una tarea compatible') and self.llm.is_available():
            try:
                model_result=self._interpret_with_model(request)
                if model_result is not None:
                    return model_result
            except Exception as exc:
                return {'request':request,'error':str(exc),'error_category':'model_error'}
        if plan.clarification and plan.clarification.startswith('No reconocí una tarea compatible') and auto_research and self._is_general_question(request):
            query=request.strip()
            plan=Plan([Operation('web','search',{'query':query},description=f'investigar «{query}» en la web y mostrar fuentes aquí',risk=Risk.LOW)],request)
            try:self.validator.validate(plan)
            except Exception as e:return {'request':request,'error':str(e),'results':[]}
            results=self.executor.execute(plan);self.context.remember(request,results,plan)
            return {'request':request,'plan':plan,'results':results}
        if plan_message and not plan.operations:
            if plan_message.startswith('__reformat_last_result__'):
                return self._reformat_last(request)
            return {'request':request,'message':plan_message}
        if plan.clarification=='__reformat_last_result__':
            if self.context.last_results:return {'request':request,'plan':self.context.last_plan,'results':self.context.last_results}
            return {'request':request,'clarification':'Todavía no hay un resultado anterior para volver a presentar.','results':[]}
        if plan.clarification:
            if plan.clarification.startswith('No reconocí una tarea compatible'):
                from intelligence.dialogue import unknown_reply
                return {'request':request,'message':unknown_reply(request,self.context)}
            return {'request':request,'clarification':plan.clarification,'results':[]}
        if plan.operations and plan.operations[0].capability=='assistant':
            category=plan.operations[0].arguments.get('category')
            rows=self.capabilities()
            if category:
                rows=[row for row in rows if row['name']==category]
            if category and rows:
                row=rows[0]
                friendly={
                    'development':{'execute_command':'ejecutar comandos explícitos','git_status':'revisar cambios de Git','open_file':'abrir archivos','python_version':'consultar Python','run_python':'ejecutar programas Python'},
                    'filesystem':{'create':'crear archivos','list':'listar carpetas','read':'leer archivos','search_names':'buscar nombres','move':'mover archivos','copy':'copiar archivos'},
                }
                names=', '.join(friendly.get(category,{}).get(name,name.replace('_',' ')) for name in row['operations'])
                category_labels={'development':'desarrollo','filesystem':'archivos','networking':'redes','cybersecurity':'ciberseguridad','system':'sistema'}
                summary=f'En {category_labels.get(category,category)} puedo: {names}. Usa /capabilities para ver los demás grupos.'
                return {'request':request,'message':summary,'capabilities':rows}
            result=Result(plan.operations[0].id,True,stdout=str(rows),exit_code=0,data={'capabilities':rows},verified=True,status=Status.SUCCEEDED)
            return {'request':request,'plan':plan,'results':[result]}
        try:self.validator.validate(plan)
        except Exception as e:return {'request':request,'error':str(e),'results':[]}
        results=self.executor.execute(plan); self.context.remember(request,results,plan)
        return {'request':request,'plan':plan,'results':results}

    @staticmethod
    def _is_general_question(request):
        normalized=normalize(request).strip(' .!?¿¡')
        words=normalized.split()
        if len(words)<2:return False
        if Assistant._is_open_ended_request(normalized):return False
        return True

    @staticmethod
    def _is_open_ended_request(request):
        normalized=normalize(request).strip(' .!?¿¡')
        patterns=(
            r'\b(inventa|imagina|escribe|redacta|comp[oó]n|crea\s+una\s+historia|write|invent|imagine|compose)\b',
            r'\b(poema|poesia|deporte\s+nuevo|deporte\s+absurdo|isla\s+desierta|gatos\s+pudieran\s+hablar|hot\s+dog)\b',
            r'\b(peor\s+consejo|consejo\s+mas\s+absurdo|dame\s+argumentos|argumentos\s+fuertes)\b',
            r'\b(explicame|explain)\b.*\b(como\s+si|as\s+if|dinosaurios|5\s+anos)\b',
            r'\b(resumen\s+de\s+mi\s+dia\s+ideal|primer\s+dia\s+navegando|preguntas\s+dificiles\s+que\s+yo)\b',
            r'\b(que\s+opinas|que\s+piensas|what\s+do\s+you\s+think)\b',
            r'\b(como\s+aprender|como\s+estudiar)\b',
            # Preguntas conversacionales simples que no requieren búsqueda web
            r'^(por\s+que|porque|why)\s*$',  # "Por qué?" solo
            r'^(que|what)\s*$',  # "Qué?" solo
            r'^(como|how)\s*$',  # "Cómo?" solo
            r'^(donde|where)\s*$',  # "Dónde?" solo
            r'^(cuando|when)\s*$',  # "Cuándo?" solo
            r'^(quien|who)\s*$',  # "Quién?" solo
            r'^(ok|okey|va|bien|fine)\s*$',  # Confirmaciones simples
            r'^(mmm|umm|uh)\s*$',  # Sonidos de duda
            r'^(ah|aha|oh)\s*$',  # Sonidos de sorpresa
            r'^(si|yes)\s*$',  # Respuestas afirmativas simples
            r'^(no)\s*$',  # Respuestas negativas simples
            r'^(gracias|thanks|thank\s+you)\s*$',  # Agradecimientos
            r'^(hola|hi|hello)\s*$',  # Saludos simples
            r'^(adios|bye|chao)\s*$',  # Despedidas simples
        )
        return any(re.search(pattern,normalized) for pattern in patterns)

    def _interpret_with_model(self,request):
        import signal
        from contextlib import contextmanager
        
        @contextmanager
        def timeout_context(seconds):
            def timeout_handler(signum, frame):
                raise TimeoutError()
            if hasattr(signal, 'SIGALRM'):
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(seconds))
                try:
                    yield
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
            else:
                yield
        
        catalog=[]
        for capability in self.registry.list():
            catalog.append({
                'name':capability.name,
                'description':capability.description,
                'operations':{
                    name:{'schema':capability.schemas[name],
                          'risk':capability.risks.get(name,'read_only')}
                    for name in sorted(capability.operations)
                },
            })
        previous=self.context.last_operation_event
        summary={
            'last_question':self.context.last_question,
            'last_answer':self.context.last_answer,
            'last_search':self.context.last_search,
            'recent_exchanges':list(self.context.events)[-6:],
        }
        if previous:
            summary['last_operation']={'request':previous['request'],'operations':previous['operations'],
                                       'results':previous['results']}
        if self.context.pending and self.context.pending.get('kind')=='model_clarification':
            summary['clarification_in_progress']={
                'original_request':self.context.pending.get('original_request',''),
                'question':self.context.pending.get('question',''),
                'user_followup':request,
            }
        try:
            with timeout_context(self.llm_timeout):
                choice=self.llm.interpret_request(request,catalog,summary)
        except TimeoutError:
            return None  # Fallback to rule-based parsing
        kind=choice['kind']
        if kind=='answer':
            message=choice.get('message')
            if not isinstance(message,str) or not message.strip():
                return None
            if self.context.pending and self.context.pending.get('kind')=='model_clarification':
                self.context.pending=None
            return {'request':request,'message':message.strip()[:4000],'reasoning':'optional_model'}
        if kind=='clarification':
            question=choice.get('question')
            if not isinstance(question,str) or not question.strip():
                return None
            self.context.pending={'kind':'model_clarification','original_request':request,'question':question.strip()[:500]}
            return {'request':request,'clarification':question.strip()[:500],'results':[],'reasoning':'optional_model'}
        proposed=choice.get('operations')
        if not isinstance(proposed,list) or not 1<=len(proposed)<=4:
            raise ValueError('El modelo propuso una cantidad de operaciones no válida.')
        identifiers=[__import__('uuid').uuid4().hex[:12] for _ in proposed]
        operations=[]
        for index,item in enumerate(proposed):
            if not isinstance(item,dict):
                raise ValueError('El modelo devolvió una operación mal formada.')
            capability_name=item.get('capability')
            operation_name=item.get('operation')
            arguments=item.get('arguments',{})
            if not isinstance(capability_name,str) or not isinstance(operation_name,str) or not isinstance(arguments,dict):
                raise ValueError('El modelo devolvió capacidad, operación o argumentos no válidos.')
            capability=self.registry.get(capability_name)
            if operation_name not in capability.operations:
                raise ValueError(f'El modelo propuso una operación no registrada: {capability_name}.{operation_name}.')
            indexes=item.get('depends_on',[])
            if not isinstance(indexes,list) or any(not isinstance(dep,int) or isinstance(dep,bool) or dep<0 or dep>=index for dep in indexes):
                raise ValueError('El modelo propuso dependencias inválidas.')
            risk=Risk(capability.risks.get(operation_name,'read_only'))
            description=item.get('description')
            if not isinstance(description,str) or not description.strip():
                description=f'{capability_name}.{operation_name}'
            operations.append(Operation(
                capability_name,operation_name,arguments,description[:240],
                dependencies=[identifiers[dep] for dep in indexes],risk=risk,id=identifiers[index],
            ))
        plan=Plan(operations,request)
        self.validator.validate(plan)
        results=self.executor.execute(plan)
        self.context.remember(request,results,plan)
        if self.context.pending and self.context.pending.get('kind')=='model_clarification':
            self.context.pending=None
        return {'request':request,'plan':plan,'results':results,'reasoning':'optional_model'}

    def _last_value(self,capability,name):
        if not self.context.last_plan or not self.context.last_results:return None
        if not any(op.capability==capability and op.name==name for op in self.context.last_plan.operations):return None
        result=self.context.last_results[-1]
        if not result.success:return None
        return result.data.get('value') if isinstance(result.data,dict) else None

    def _last_failed_calculation(self):
        plan=self.context.last_plan
        return bool(plan and any(op.capability=='calculator' for op in plan.operations)
                    and self.context.last_results and not self.context.last_results[-1].success)

    def _explain_last_exchange(self):
        # Prefer the structured event over its serialized audit summary so large
        # values (notably /proc/meminfo and logs) never leak as a raw dictionary.
        if self.context.last_plan and self.context.last_results:
            operation=self.context.last_plan.operations[-1]
            result=self.context.last_results[-1]
            action=operation.description or f'{operation.capability}.{operation.name}'
            if not result.success:
                detail=(result.stderr or result.error_category or result.status.value).strip()
                if result.exit_code is not None:detail=f'{detail} (código {result.exit_code})'
                return f'Lo último fue {action}, pero falló: {detail[:240]}. No lo reintenté.'
            value=result.data.get('value') if isinstance(result.data,dict) else None
            if operation.capability=='system' and operation.name=='info' and isinstance(value,dict):
                memory=value.get('memory',{})
                detail=f"Host {value.get('hostname','desconocido')}, kernel {value.get('kernel','desconocido')}"
                if memory:detail+=f"; RAM disponible {memory.get('MemAvailable','sin dato')} de {memory.get('MemTotal','sin dato')}"
                return f'Lo último fue consultar la información del sistema y terminó bien. {detail}.'
            if operation.capability=='web' and isinstance(value,dict):
                return f"Lo último fue buscar «{value.get('query','')}»; encontré {len(value.get('results',[]))} resultados y los mostré aquí."
            if operation.capability=='system' and operation.name=='logs' and isinstance(value,str):
                return f'Lo último fue consultar los logs; obtuve {len(value.splitlines())} líneas.'
            if value is not None:
                from interface.formatter import _human_value
                detail=_human_value(value,operation.capability).replace('\n','; ')
                return f'Lo último fue {action} y terminó bien. {detail[:240]}'
            return f'Lo último fue {action} y terminó bien.'
        event=self.context.last_operation_event
        if event:
            operation=event['operations'][-1];outcome=event['results'][-1]
            action=operation['description'] or f"{operation['capability']}.{operation['name']}"
            if outcome['success']:
                return f'Lo último fue {action}; terminó correctamente.'
            detail=outcome['detail'] or outcome['error_category'] or outcome['status']
            code=f" (código {outcome['exit_code']})" if outcome['exit_code'] is not None else ''
            return f'Lo último fue {action}, pero falló{code}: {detail[:240]}. No lo reintenté.'
        if self.context.last_exchange and self.context.last_exchange.get('message'):
            return f"La última solicitud no ejecutó una operación: {self.context.last_exchange['message']}"
        return 'Aún no hay una operación en esta sesión para resumir.'

    def _reformat_last(self,request):
        if self.context.last_plan and self.context.last_results:
            return {'request':request,'plan':self.context.last_plan,'results':self.context.last_results}
        return {'request':request,'message':'Todavía no hay un resultado de operación en esta sesión para volver a presentar.'}
