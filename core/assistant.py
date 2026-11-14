"""End-to-end assistant orchestration."""
import re
from datetime import datetime
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
from memory.persistent_memory import PersistentMemory

class Assistant:
    def __init__(self,confirm=input):
        import os
        self.config=load_config(); self.registry=registry; self.parser=Parser(); self.validator=Validator(registry); self.context=Context(); self.auto_open_terminal=False; self._input_confirm=confirm
        self.executor=Executor(registry,self._confirm,self.config['settings'].get('execution',{}).get('default_yes_operations',()),
                               self.config['policies'].get('risk',{}))
        # El usuario pidió ejecución directa: ninguna operación pide confirmación.
        # La única credencial que se solicita es la contraseña de sudo cuando un
        # comando la necesita (se pide dentro de development.execute_command).
        self.executor.confirmation_policy={key:False for key in self.executor.confirmation_policy}
        # Detect a local Ollama model automatically; remote providers still need
        # explicit configuration inside LLMIntegration.
        configured_llm=self.config['settings'].get('model',{}).get('enabled','auto')
        use_llm = os.environ.get('CLIBOT_USE_LLM',str(configured_llm)).strip().lower()
        self.llm = None if use_llm in {'false', '0', 'off', 'no'} else LLMIntegration()
        self.memory = PersistentMemory()
        self.audit_logger = AuditLogger()
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
        try:
            success=not response.get('error') and all(r.success for r in response.get('results',[]))
            self.memory.add_history_entry(request,{'message':response.get('message') or response.get('clarification') or '',
                                                   'operations':[{'capability':op.capability,'name':op.name}
                                                                 for op in (response.get('plan').operations if response.get('plan') else [])]},
                                       success=success)
        except Exception:
            pass
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

        if self._is_malicious_security_request(request):
            return {'request':request,'message':
                    'Eso es un ataque malicioso y no lo hago. En cambio puedo ayudarte con la defensa: '
                    '«auditoria ssh», «intentos de acceso fallidos», «postura del firewall», '
                    '«herramientas de seguridad», «pentest a <ip>», «bloquea la ip <ip>», «recopila evidencia», '
                    '«entrenamiento phishing», «cumplimiento iso 27001».'}

        if re.search(r'\b(?:que|cual)\b.*\b(?:semana|numero de semana)\b|\ben que semana estamos\b',phrase):
            iso=datetime.now().date().isocalendar()
            return {'request':request,'message':f'Estamos en la semana {iso.week} del año {iso.year} (semana ISO).'}

        if re.search(r'\b(?:recomiendas|recomienda|recomendarias)\b.*\bmodelo\b|\bmodelo\b.*\b(?:mas rapido|mas ligero)\b',phrase):
            return {'request':request,'message':
                    'Como prueba, consideraría `qwen2.5:1.5b`; `qwen2.5:0.5b` tiene aún menos parámetros, pero puede '
                    'ser menos capaz. Por tamaño podrían usar menos recursos que Phi-3 mini, pero no he medido su '
                    'velocidad en tu equipo y no puedo prometer que respondan más rápido: depende también de la '
                    'cuantización, la CPU y el prompt. Puedes probar sin borrar Phi-3: `/models pull qwen2.5:1.5b` '
                    'y luego `/models use qwen2.5:1.5b`. La descarga requiere Internet.'}

        if re.fullmatch(r'(?:si|sí)(?: se)? abrio|(?:si|sí) se abrio la aplicacion',phrase):
            event=self.context.last_operation_event
            if event and event['operations'] and event['results']:
                operation=event['operations'][-1]
                outcome=event['results'][-1]
                if operation['capability']=='browser' and operation['name'] in {'open_application','open_url'}:
                    if outcome['success']:
                        return {'request':request,'message':
                                f"Sí: {operation['description'].capitalize()}. La solicitud al sistema terminó bien, "
                                'aunque no puedo confirmar si la ventana quedó visible.'}
                    return {'request':request,'message':
                            f"No: {operation['description']} falló: {outcome['detail'] or 'sin más detalles'}"}

        offline_statement=bool(re.fullmatch(r'(?:no tengo|no hay|sin)\s+(?:internet|conexion)',phrase))
        offline_question=bool(re.search(r'\b(?:no tengo|no hay|sin)\b.{0,30}\b(?:internet|conexion)\b',phrase)
                              and re.search(r'\b(?:que puedes|que puedo|que sigue|que seguir|todavia|aun)\b',phrase))
        if offline_statement or offline_question:
            return {'request':request,'message':
                    'Sin Internet sigo pudiendo consultar el sistema, RAM, CPU, procesos, servicios, archivos locales, '
                    'hacer cálculos, abrir aplicaciones y ejecutar comandos explícitos de solo lectura. Las búsquedas '
                    'web, GitHub, Stack Overflow y las traducciones en línea sí necesitan conexión.'}

        storage_answer=self._answer_hypothetical_storage_question(request)
        if storage_answer:
            return {'request':request,'message':storage_answer}

        hardware_answer=self._answer_hardware_question(request)
        if hardware_answer:
            return {'request':request,'message':hardware_answer}

        if re.search(r'\b(?:borrar|eliminar|limpiar)\b.*\btemporales?\b',phrase) and re.search(
                r'\b(?:que|primero|antes|deberia|debo|comprobar|revisar)\b',phrase):
            return {'request':request,'message':
                    'Antes de borrar, identifica la ruta y el tamaño, confirma qué aplicación creó esos archivos, '
                    'comprueba que no haya procesos usándolos y revisa si son caché regenerable o datos temporales '
                    'de una tarea activa. No borres a ciegas /tmp ni carpetas del sistema; empieza por revisar y '
                    'elige solo archivos que reconozcas.'}

        if phrase in {'almacenamiento','espacio','disco'}:
            return {'request':request,'clarification':
                    '¿Quieres consultar el espacio libre del disco, ver qué carpetas ocupan más, o calcular un espacio hipotético?'}

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
        if self._is_code_generation_request(request):
            if re.fullmatch(r'(?:genera|generame|dame|escribe|crea|comparte)(?:\s+el)?\s+codigo',phrase):
                return {'request':request,'clarification':'¿Qué debe hacer el código y en qué lenguaje?'}
            if self.llm and self.llm.is_available():
                try:
                    answer=self.llm.generate_response(
                        'Responde en español. Entrega código completo y ejecutable para la petición; '
                        'incluye bloque de código, instrucciones mínimas para usarla y dependencias necesarias. '
                        'No afirmes que la probaste ni añadas enlaces o fuentes salvo que se pidan. '
                        'Si falta un requisito esencial, haz una pregunta breve. '
                        'No inventes funciones, APIs ni detalles internos que no conozcas. '
                        +self._recent_context()+'PETICIÓN: '+request[:500],
                        max_tokens=320,
                    ).strip()
                    if answer:
                        saved=self._maybe_save_generated_code(request,answer)
                        if saved is not None:
                            return saved
                        return {'request':request,'message':answer[:6000],'reasoning':'local_model_code'}
                except RuntimeError as exc:
                    return {'request':request,'message':f'No pude generar el código con el modelo local: {exc}'}
            return {'request':request,'message':
                    'Para generar y explicar código completo necesito un modelo de lenguaje activo. '
                    'No voy a sustituirlo por fragmentos de buscador. Activa Ollama con /models o configura un proveedor LLM.'}
        conversational=dialogue_response(request,self.context)
        if conversational:
            return {'request':request,'message':conversational}
        if self._is_troubleshooting_request(request):
            diagnostics=self._collect_diagnostics()
            if self.llm and self.llm.is_available():
                try:
                    answer=self.llm.generate_response(
                        'Ayuda a diagnosticar el problema en español con datos reales. Da una respuesta práctica: '
                        'causas probables ordenadas, comprobaciones concretas y comandos de diagnóstico no destructivos '
                        'cuando sean pertinentes. No des una explicación académica ni teoría general: centrate en '
                        'resolver el fallo concreto. No inventes el estado del equipo: usa los DATOS DE DIAGNÓSTICO '
                        'reales adjuntos; si no bastan, pide el mensaje de error exacto. '
                        'No busques en la web ni incluyas fuentes salvo que se soliciten. '
                        'No afirmes que ejecutaste comandos que no aparecen en los datos. '
                        +self._recent_context()+'DATOS DE DIAGNÓSTICO:\n'+diagnostics+'\nPROBLEMA: '+request[:900],
                        max_tokens=220,
                    ).strip()
                    if answer:
                        return {'request':request,'message':answer[:3500]+
                                '\n\nPuedo ejecutar comandos concretos por ti (por ejemplo «ejecuta ls -la»); dime cuál.',
                                'reasoning':'local_model_troubleshooting'}
                except RuntimeError as exc:
                    return {'request':request,'message':
                            f'No pude consultar el modelo local: {exc}. Comparte el error exacto, el comando usado '
                            'y qué esperabas que ocurriera; no he ejecutado ni buscado nada.'}
            return {'request':request,'message':
                    'Para diagnosticarlo sin adivinar, comparte el comando o acción, el mensaje de error completo '
                    'y qué esperabas que ocurriera. Sin un modelo activo puedo ayudarte con comprobaciones concretas, '
                    'pero no analizar automáticamente un problema abierto. No hice una búsqueda web.'}
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
        if self._is_educational_request(request):
            model_error=None
            if self.llm and self.llm.is_available():
                try:
                    answer=self.llm.generate_response(
                        'Responde en español con una explicación clara y práctica. '
                        'Usa ejemplos si ayudan. No hagas búsquedas, no añadas enlaces ni afirmes hechos dudosos. '
                        'No inventes agentes, módulos ni detalles internos del sistema: si no conoces cómo funciona '
                        'algo por dentro, dilo en lugar de especular. '
                        +self._recent_context()+'PETICIÓN: '+request[:700],
                        max_tokens=128,
                    ).strip()
                    if answer:return {'request':request,'message':answer[:1500],'reasoning':'local_model'}
                except RuntimeError as exc:
                    model_error=str(exc)
            if model_error:
                return {'request':request,'message':f'No pude generar una explicación con el modelo local: {model_error}'}
            return {'request':request,'message':
                    'No hay un modelo de lenguaje activo para elaborar una explicación completa. '
                    'Activa Ollama con /models; buscaré en la web solo si me lo pides expresamente.'}
        if self._is_security_question(request):
            if self.llm and self.llm.is_available():
                try:
                    answer=self.llm.generate_response(
                        'Eres un experto en ciberseguridad defensiva y pentesting autorizado. Responde en español '
                        'con conocimiento práctico y preciso: explica conceptos, compara opciones, da pasos '
                        'concretos de hardening, detección, respuesta a incidentes, auditoría y buenas prácticas. '
                        'Cuando sea útil, sugiere comandos reales que el usuario puede pedirme ejecutar (por '
                        'ejemplo «auditoria ssh», «intentos de acceso fallidos», «postura del firewall», '
                        '«herramientas de seguridad», «pentest a <ip>», «bloquea la ip <ip>», «recopila evidencia»). '
                        'No ayudes a crear ataques maliciosos; si el tema roza lo ofensivo, redirige a la defensa. '
                        'No inventes herramientas, CVEs ni datos: si no estás seguro, dilo. '
                        +self._recent_context()+'PREGUNTA: '+request[:700],
                        max_tokens=220,
                    ).strip()
                    if answer:return {'request':request,'message':answer[:4000],'reasoning':'local_model_security'}
                except RuntimeError as exc:
                    return {'request':request,'message':f'No pude consultar el modelo local: {exc}'}
            return {'request':request,'message':
                    'Para responder con profundidad sobre ciberseguridad necesito un modelo de lenguaje activo. '
                    'Activa Ollama con /models. Mientras tanto puedo ejecutar auditorías reales: «auditoria ssh», '
                    '«intentos de acceso fallidos», «postura del firewall», «herramientas de seguridad».'}
        plan=self.parser.parse(request,self.context)
        plan_message=getattr(plan,'message',None)
        if plan.reformat_last:
            return self._reformat_last(request)
        if plan.clarification and plan.clarification.startswith('No reconocí una tarea compatible'):
            code_result=self._llm_code_to_file(request)
            if code_result is not None:
                return code_result
        if plan.clarification and plan.clarification.startswith('No reconocí una tarea compatible') and self._is_open_ended_request(request):
            if self.llm and self.llm.is_available():
                try:
                    model_result=self._interpret_with_model(request)
                    if model_result is not None:
                        return model_result
                except RuntimeError:
                    pass
                except Exception as exc:
                    return {'request':request,'error':str(exc),'error_category':'model_error'}
                model_error=None
                try:
                    message=self.llm.generate_response(
                        'Responde en español, en menos de 70 palabras. '
                        'Puedes crear texto original. No afirmes que tienes sentimientos. '
                        'No inventes capacidades ni detalles internos del sistema. '
                        'No ejecutes acciones. '+self._recent_context()+'PETICIÓN: '+request[:700],
                    )
                    if message.strip():return {'request':request,'message':message.strip()[:1500],'reasoning':'local_model'}
                except RuntimeError as exc:
                    model_error=str(exc)
                if model_error:
                    return {'request':request,'error':model_error,'error_category':'model_error'}
            return {'request':request,'message':'Para inventar o desarrollar una respuesta abierta necesito un modelo de lenguaje activo. No voy a convertir esa petición creativa en una búsqueda web.'}
        if plan.clarification and plan.clarification.startswith('No reconocí una tarea compatible'):
            if self._is_general_question(request):
                if self.llm and self.llm.is_available():
                    try:
                        answer=self.llm.generate_response(
                            'Responde directamente en español a la pregunta. Da contexto suficiente para que la respuesta '
                            'sea útil, pero evita rodeos, enlaces y fuentes no solicitadas. Si no estás seguro o el dato '
                            'puede haber cambiado, indícalo y ofrece buscarlo solo si el usuario lo pide. '
                            'No ejecutes acciones. '+self._recent_context()+'PREGUNTA: '+request[:700],
                            max_tokens=128,
                        ).strip()
                        if answer:return {'request':request,'message':answer[:2200],'reasoning':'local_model'}
                    except RuntimeError as exc:
                        return {'request':request,'message':f'No pude consultar el modelo local: {exc}'}
                return {'request':request,'message':
                        'No hay un modelo de lenguaje activo para responder esa pregunta abierta. '
                        'Activa uno con /models o pídeme expresamente que busque en la web.'}
        if plan.clarification and plan.clarification.startswith('No reconocí una tarea compatible') and self.llm and self.llm.is_available():
            try:
                model_result=self._interpret_with_model(request)
                if model_result is not None:
                    return model_result
            except RuntimeError:
                pass
            except Exception as exc:
                return {'request':request,'error':str(exc),'error_category':'model_error'}
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
        response={'request':request,'plan':plan,'results':results}
        analysis=self._analyze_results(request,plan,results)
        if analysis:response['analysis']=analysis
        return response

    @staticmethod
    def _is_general_question(request):
        normalized=normalize(request).strip(' .!?¿¡')
        words=normalized.split()
        if len(words)<2:return False
        if re.match(r'^(?:averigua|investiga|busca|buscar|muestra|mostrar|consulta|haz|ejecuta|abre|cierra|borra|elimina|'
                    r'crea|instala|cambia|reinicia|deten|stop|run|search|find)\b',normalized):
            return False
        if Assistant._is_open_ended_request(normalized):return False
        return True

    def _llm_code_to_file(self,request):
        """If the user asks to program/develop something and save it to a file,
        have the local LLM write the code and store it via filesystem.write."""
        if not (self.llm and self.llm.is_available()):
            return None
        if not re.search(r'\b(programa|programar|desarrolla|desarrollar|implementa|implement\w*|codifica|escribe un (?:programa|script)|crea un (?:programa|script))\b',normalize(request)):
            return None
        path_match=re.search(r'(/[\w./~ -]+|[\w.-]+\.(?:py|js|sh|bash|c|cpp|h|java|rb|go|rs|php|html|css|sql|json|yaml|yml|toml|md|txt))',request)
        if not path_match:
            return None
        path=path_match.group(1).strip()
        try:
            code=self.llm.generate_response(
                'Genera SOLO el código fuente solicitado, completo y funcional, sin explicaciones ni markdown. '
                'Entrega únicamente el código.\nPETICIÓN: '+request[:600],
                max_tokens=600,
            )
            code=code.strip()
            code=re.sub(r'^```[a-zA-Z]*\s*','',code)
            code=re.sub(r'\s*```$','',code).strip()
            if not code or len(code)<20:
                return None
            plan=Plan([Operation('filesystem','write',{'path':path,'content':code},
                                 description=f'guardar el código generado en {path}',risk=Risk.MODERATE)],request)
            self.validator.validate(plan)
            results=self.executor.execute(plan)
            self.context.remember(request,results,plan)
            return {'request':request,'plan':plan,'results':results,'reasoning':'local_model_codegen'}
        except Exception:
            return None

    def _analyze_results(self,request,plan,results):
        """Ask the local LLM to interpret real operation output (security/data ops
        or explicit analysis requests). Returns a short Spanish analysis or None."""
        if not (self.llm and self.llm.is_available()):
            return None
        interesting=any(op.capability in {'cybersecurity','security_audit','monitoring'} for op in plan.operations)
        wants=bool(re.search(r'\b(analisis|analiza|analizar|resumen|informe|explica|por\s*que|qué significa|que significa)\b',normalize(request)))
        if not (interesting or wants):
            return None
        blob=[]
        for r in results[:4]:
            text=(r.stdout or '') or (str(r.data)[:800] if r.data else '') or (r.stderr or '')
            if text:
                blob.append(text[:1200])
        if not blob:
            return None
        try:
            from security.redaction import redact
            answer=self.llm.generate_response(
                'Eres un analista de ciberseguridad. Resume en español, en menos de 120 palabras, '
                'qué muestran estos resultados reales del sistema y qué acciones recomiendas. '
                'No inventes datos que no estén en el texto.\nRESULTADOS:\n'+redact('\n---\n'.join(blob))[:3000],
                max_tokens=220,
            )
            return answer.strip()[:2000] or None
        except Exception:
            return None

    def _recent_context(self):
        turns=[]
        for event in list(self.context.events)[-3:]:
            request=event.get('request','').strip()
            answer=event.get('message','').strip()
            if request and answer:
                turns.append(f'Usuario: {request[:140]}\nCLIBOT: {answer[:180]}')
        memory=self._memory_summary()
        if memory:
            turns.append('MEMORIA DE SESIONES ANTERIORES:\n'+memory)
        return 'CONTEXTO RECIENTE:\n'+'\n'.join(turns)+'\n' if turns else ''

    def _memory_summary(self,limit=8):
        try:
            entries=self.memory.get_history(limit)
        except Exception:
            return ''
        lines=[]
        for entry in entries:
            request=str(entry.get('request','')).strip()
            response=str(entry.get('response_summary','')).strip()
            if request:
                lines.append(f'- Usuario: {request[:160]}')
                if response:
                    lines.append(f'  CLIBOT: {response[:200]}')
        return '\n'.join(lines)

    @staticmethod
    def _is_educational_request(request):
        normalized=normalize(request).strip(' .!?¿¡')
        return bool(re.search(
            r'\b(?:explicame|explica|explain|que es|como funciona)\b.*'
            r'\b(?:como si|desde cero|para principiantes|estoy empezando|empezando|beginner|starting out)\b',
            normalized,
        ) and re.search(
            r'\b(?:proceso|linux|kernel|ram|cpu|archivo|sistema|programa|protocolo|red|dns|git|python)\b',
            normalized,
        ))

    @staticmethod
    def _is_code_generation_request(request):
        normalized=normalize(request).strip(' .!?¿¡')
        if re.search(r'\b(?:github|stack\s+overflow|stackoverflow|busca|buscar|encuentra)\b',normalized):
            return False
        asks_for_code=bool(re.search(
            r'\b(?:dame|genera|generame|escribe|crea|comparte|comparteme|implementa|necesito|quiero)\b',
            normalized,
        ))
        code_topic=bool(re.search(
            r'\b(?:codigo|script|funcion|programa|ejemplo|calculadora|aplicacion|app|bot|juego|'
            r'pagina|sitio web|cli|dashboard|herramienta)\b',normalized))
        return asks_for_code and code_topic

    @staticmethod
    def _is_troubleshooting_request(request):
        normalized=normalize(request).strip(' .!?¿¡')
        if re.match(r'^(?:busca|buscar|investiga|averigua|diagnostica|diagnosticar|revisa|revisar|'
                    r'ejecuta|corre|haz|ping|traceroute|nmap|escanea|scan)\b',normalized):
            return False
        problem=bool(re.search(
            r'\b(?:error|exception|traceback|fall[oa]|falla|problema|no funciona|no sirve|no responde|'
            r'no conecta|no puedo|se rompe|se cierra|atascad[oa]|troubleshoot|diagnostica|diagnosticar|'
            r'como arreglo|como soluciono|como resolver|ayudame a arreglar|fix)\b',
            normalized,
        ))
        context=bool(re.search(
            r'\b(?:porque|por que|ayuda|arregla|arreglo|arreglar|soluciona|soluciono|solucionar|resolver|diagnostico|diagnosticar|'
            r'error|problema|funciona|funcionar|conecta|conectar|instala|instalar)\b',
            normalized,
        ))
        return problem and context

    @staticmethod
    def _is_malicious_security_request(request):
        normalized=normalize(request)
        terms=r'(?:ransomware|ddos|denegaci[oó]n de servicio|malware|troyano|spyware|keylogger|botnet|rootkit|virus|gusano|phishing|smishing|vishing|zero-?day)'
        actions=r'\b(?:crea|crear|haz|hacer|lanza|lanzar|despliega|desplegar|instala|instalar|genera|generar|envia|enviar|manda|mandar|ejecuta|ejecutar|necesito|quiero|roba|robar|extrae|extraer|exfiltra|exfiltrar|cifra|cifrar|secuestra|secuestrar|filtra|filtrar|inyecta|inyectar)\b'
        defensive=r'\b(?:protege|proteger|protecci[oó]n|defensa|defender|detecta|detectar|detecci[oó]n|previene|prevenir|prevenci[oó]n|entrenamiento|concienciaci[oó]n|explica|qu[eé] es|c[oó]mo funciona|auditor[ií]a|an[aá]lisis|mitiga|mitigar|recupera|recuperar|defiende|bloquea)\b'
        if (re.search(actions+r'[^.]{0,80}'+terms,normalized)
                or re.search(terms+r'[^.]{0,80}'+actions,normalized)):
            return not re.search(defensive,normalized)
        return bool(re.search(
            r'\b(?:roba|extrae|exfiltra|cifra|secuestra|filtra|vaza)\b[^.]{0,60}'
            r'\b(?:datos|credenciales|tarjetas?|contraseñas|contrasenas|informaci[oó]n confidencial|bases? de datos)\b',
            normalized))

    @staticmethod
    def _is_security_question(request):
        normalized=normalize(request).strip(' .!?¿¡')
        if not re.search(
            r'\b(?:ciberseguridad|seguridad|pentest|vulnerabilidad|firewall|intruso|intrusi[oó]n|ataque|malware|'
            r'phishing|ransomware|encriptaci[oó]n|vpn|ids|ips|siem|cumplimiento|iso ?27001|nist|hackeo|hacker|'
            r'exploit|zero-?day|backdoor|botnet|hardening|fail2ban)\b',normalized):
            return False
        if re.search(r'\b(?:protege|proteger|protecci[oó]n|defiende|defender|blindar|endurecer|mitiga|mitigar|'
                     r'prevenir|prevenci[oó]n|refuerza|reforzar|audita|auditar)\b',normalized):
            return True
        return bool(re.search(
            r'^\s*(?:qu[eé]|c[oó]mo|por ?qu[eé]|cu[aá]l|cu[aá]les|diferencia|explica|ens[eé][nñ]a|what|how|why|'
            r'which|explain|dime|h[aá]blame|ayuda|ay[uú]dame)\b',normalized))

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

    @staticmethod
    def _answer_hypothetical_storage_question(request):
        from decimal import Decimal, InvalidOperation

        normalized=normalize(request)
        match=re.search(
            r'\b(?:si\s+)?(?:tengo|hay|dispongo de)\s+(\d+(?:[.,]\d+)?)\s*'
            r'(bytes?|kib|mib|gib|tib|kb|mb|gb|tb)\s+(?:libres?|disponibles?)\b'
            r'.{0,100}\b(?:archivo|fichero)\b.{0,50}\b(?:ocupa|pesa|usa|requiere)\s+'
            r'(\d+(?:[.,]\d+)?)\s*(bytes?|kib|mib|gib|tib|kb|mb|gb|tb)\b',
            normalized,
        )
        if not match or not re.search(r'\b(?:cuanto|cuanta|queda|resta|espacio)\b',normalized):
            return None
        units={'byte':1,'bytes':1,'kb':1000,'mb':1000**2,'gb':1000**3,'tb':1000**4,
               'kib':1024,'mib':1024**2,'gib':1024**3,'tib':1024**4}
        try:
            available=Decimal(match.group(1).replace(',','.'))
            required=Decimal(match.group(3).replace(',','.'))
        except InvalidOperation:
            return None
        available_bytes=available*units[match.group(2)]
        required_bytes=required*units[match.group(4)]
        remaining=available_bytes-required_bytes
        if remaining<0:
            amount=-remaining/units[match.group(2)]
            return f'No alcanza: faltarían {amount.normalize()} {match.group(2).upper()}.'
        amount=remaining/units[match.group(2)]
        return f'Te quedarían {amount.normalize()} {match.group(2).upper()}.'

    @staticmethod
    def _answer_hardware_question(request):
        normalized=normalize(request)
        has_ram=bool(re.search(r'\b\d+(?:[.,]\d+)?\s*(?:gb|gib|mb|mib)\s*(?:de\s+)?(?:ram|memoria)\b',normalized))
        asks_what=bool(re.search(r'\b(?:que puedo|que se puede|que puedo hacer|que se puede hacer|que recomiendas|que me recomiendas|que opciones|para que sirve|sirve para)\b',normalized))
        is_server=bool(re.search(r'\b(?:servidor|server|vps|nuc|mini pc|equipo|computadora|ordenador|pc|laptop)\b',normalized))
        if not (has_ram and asks_what) and not (is_server and asks_what and re.search(r'\b(?:ram|memoria|cpu|disco|hardware|recursos)\b',normalized)):
            return None
        return ('Con ese equipo puedo ayudarte a monitorear recursos (RAM, CPU, disco, procesos), diagnosticar '
                'problemas del sistema, revisar logs y servicios, gestionar archivos y ejecutar comandos concretos '
                'por ti. Dime qué quieres hacer: por ejemplo «analiza el directorio /var/log», «qué procesos comen '
                'más RAM» o «ejecuta df -h». Si el equipo tiene GPU, también puedo consultar nvidia-smi.')

    def _collect_diagnostics(self):
        plan=Plan([
            Operation('system','info',{},description='estado general del sistema',risk=Risk.READ_ONLY),
            Operation('system','ram',{},description='uso de memoria',risk=Risk.READ_ONLY),
            Operation('system','logs',{'lines':60},description='logs recientes del sistema',risk=Risk.READ_ONLY),
            Operation('processes','memory_top',{'limit':8},description='procesos que más memoria usan',risk=Risk.READ_ONLY),
        ],'diagnóstico automático')
        try:
            self.validator.validate(plan)
            results=self.executor.execute(plan)
        except Exception:
            return '(no se pudieron recopilar datos de diagnóstico)'
        chunks=[]
        for op,result in zip(plan.operations,results):
            if not result.success:
                continue
            value=result.data.get('value') if isinstance(result.data,dict) else None
            text=value if isinstance(value,str) else str(value)
            chunks.append(f'== {op.capability}.{op.name} ==\n{text[:3000]}')
        return '\n\n'.join(chunks)[:9000] or '(sin datos)'

    def _maybe_save_generated_code(self,request,answer):
        target=self._code_target_path(request) or self._infer_code_target(request)
        if not target:
            return None
        code=self._extract_code_block(answer)
        if not code:
            return None
        from pathlib import Path
        destination=Path(target).expanduser()
        if not destination.parent.is_dir():
            return {'request':request,'message':
                    f'Generé el código, pero la carpeta de destino no existe: {destination.parent}. '
                    'Dime dónde guardarlo o crea la carpeta primero.'}
        plan=Plan([Operation('filesystem','write',{'path':str(destination),'content':code},
                             description=f'guardar el código generado en {destination}',risk=Risk.MODERATE)],request)
        try:
            self.validator.validate(plan)
            results=self.executor.execute(plan)
        except Exception as exc:
            return {'request':request,'message':f'No pude guardar el archivo: {exc}'}
        self.context.remember(request,results,plan)
        explanation=re.sub(r'```[\w+-]*\n.*?```','',answer,flags=re.S).strip()
        message=f'Guardé el código en {destination}.'
        if explanation:
            message+='\n\n'+explanation[:2000]
        return {'request':request,'plan':plan,'results':results,
                'message':message,'reasoning':'local_model_code'}

    _CODE_LANGUAGE_EXTENSIONS={
        'python':'py','py':'py','javascript':'js','js':'js','node':'js','nodejs':'js',
        'typescript':'ts','ts':'ts','bash':'sh','shell':'sh','sh':'sh','zsh':'sh',
        'c':'c','cpp':'cpp','c++':'cpp','java':'java','go':'go','golang':'go',
        'rust':'rs','rs':'rs','ruby':'rb','rb':'rb','php':'php','html':'html',
        'css':'css','sql':'sql','json':'json','yaml':'yaml','yml':'yml',
    }

    @classmethod
    def _infer_code_target(cls,request):
        """Infer a filename like ``calculadora.py`` when the user asks to create
        code without giving an explicit path, so the result is saved to disk
        instead of only printed (and read aloud by TTS)."""
        normalized=normalize(request)
        creation=re.search(r'\b(?:crea|crear|escribe|escribir|genera|generar|generame|implementa|implementar|programa|programar|desarrolla|desarrollar|codifica|codificar|haz|hacer|quiero|necesito)\b',normalized)
        artifact=re.search(r'\b(?:calculadora|bot|juego|app|aplicacion|pagina|sitio|web|dashboard|cli|herramienta|programa|script|funcion|api|servicio|automatizacion|scraper|parser)\b',normalized)
        if not (creation and artifact):
            return None
        extension='txt'
        for language,ext in cls._CODE_LANGUAGE_EXTENSIONS.items():
            if re.search(r'\b'+re.escape(language)+r'\b',normalized):
                extension=ext
                break
        name=None
        match=re.search(r'\b(?:una?|el|la|los|las)\s+([a-záéíóúñ0-9]+(?:\s+[a-záéíóúñ0-9]+){0,2})',normalized)
        if match:
            candidate=match.group(1)
            stop={'un','una','el','la','los','las','con','en','para','de','del','que','y','usando','hecho','codigo','script','programa','funcion','app','aplicacion','bot','juego','pagina','sitio','web','dashboard','cli','herramienta','python','javascript','typescript','java','rust','ruby','php','bash','shell','html','css','sql','node','go'}
            words=[w for w in candidate.split() if w not in stop]
            if words:
                name=words[0]
        if not name:
            for fallback in ('calculadora','bot','juego','app','aplicacion','pagina','sitio','dashboard','cli','herramienta','programa','script'):
                if re.search(r'\b'+fallback+r'\b',normalized):
                    name=fallback
                    break
        if not name:
            name='programa'
        import unicodedata
        slug=unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode()
        slug=re.sub(r'[^a-z0-9_-]+','_',slug.lower()).strip('_') or 'programa'
        return f'{slug}.{extension}'

    @staticmethod
    def _code_target_path(request):
        normalized=normalize(request)
        match=re.search(r'(?i)\b(?:en|a|dentro de)\s+["\']?((?:~|/|\.{1,2}/)[\w./-]+|[\w.-]+/[\w./-]+)["\']?',normalized)
        if match:
            candidate=match.group(1).rstrip('.,;:')
            if re.search(r'\.(?:py|js|ts|sh|c|cpp|h|html|css|json|yaml|yml|md|txt|rs|go|java|rb|php)$',candidate,re.I):
                return candidate
        match=re.search(r'(?i)\b(?:archivo|fichero|file)\s+["\']?([\w.-]+\.(?:py|js|ts|sh|c|cpp|h|html|css|json|yaml|yml|md|txt|rs|go|java|rb|php))["\']?',normalized)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_code_block(answer):
        match=re.search(r'```[\w+-]*\n(.*?)```',answer,re.S)
        return match.group(1) if match else None

    def _resolve_model_operation(self,capability_name,operation_name):
        """Resolve a model-proposed capability/operation pair.

        Small local models sometimes swap the two fields or use an operation
        name as the capability (e.g. ``python_version`` instead of
        ``development``/``python_version``). Recover only unambiguous matches;
        otherwise raise a clear error instead of a raw ``KeyError``.
        """
        def canonical_capability(name):
            needle=name.strip().casefold()
            for capability in self.registry.list():
                if capability.name.casefold()==needle:
                    return capability
            return None

        def operation_owners(name):
            needle=name.strip().casefold()
            found=[]
            for capability in self.registry.list():
                for operation in capability.operations:
                    if operation.casefold()==needle:
                        found.append((capability.name,operation))
                        break
            return found

        capability=canonical_capability(capability_name)
        if capability is not None:
            needle=operation_name.strip().casefold()
            for operation in capability.operations:
                if operation.casefold()==needle:
                    return capability.name,operation
            owners=operation_owners(operation_name)
            if len(owners)==1:
                return owners[0]
            raise ValueError(f'El modelo propuso una operación no registrada: {capability_name}.{operation_name}.')
        owners=operation_owners(capability_name)
        if len(owners)==1:
            resolved_capability,resolved_operation=owners[0]
            needle=operation_name.strip().casefold()
            for operation in self.registry.get(resolved_capability).operations:
                if operation.casefold()==needle:
                    return resolved_capability,operation
            return resolved_capability,resolved_operation
        owners=operation_owners(operation_name)
        if len(owners)==1:
            return owners[0]
        raise ValueError(f'El modelo propuso una operación no registrada: {capability_name}.{operation_name}.')

    def _interpret_with_model(self,request):
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
            'entities':self.context.entities,
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
        if not self.llm or not hasattr(self.llm,'interpret_request'):
            return None
        choice = self.llm.interpret_request(request,catalog,summary)
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
            capability_name,operation_name=self._resolve_model_operation(capability_name,operation_name)
            capability=self.registry.get(capability_name)
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
