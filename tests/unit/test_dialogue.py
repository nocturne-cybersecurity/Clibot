from intelligence.dialogue import respond
from core.context import Context

def test_common_conversation_is_not_treated_as_unknown_operation():
    assert respond('claro')
    assert respond('mmm no entiendo')
    assert 'LLMAH' in respond('como te llamas?')
    assert respond('perfecto! gracias')
    assert 'Me llamo LLMAH' in respond('como te llamas?')
    assert 'modelo de lenguaje' in respond('tus respuestas son predefinidas?')

def test_cybersecurity_scope_answer_is_honest():
    answer=respond('porque en ciberseguridad solo puedes escanear?')
    assert 'Nmap' in answer and 'DNS' in answer

def test_social_replies_vary_and_cover_small_talk():
    context=Context()
    assert respond('hola',context)!=respond('hola',context)
    assert 'Gracias' in respond('me gustas')
    assert 'pulsar Enter' in respond('quiero que por defecto sea Y al confirmar')

def test_unknown_reply_is_varied_and_honest():
    from intelligence.dialogue import unknown_reply
    context=Context()
    assert unknown_reply('blah',context)!=unknown_reply('blah',context)

def test_user_facing_common_questions():
    assert '¡Hola!' in respond('Hola LLMAH')
    assert 'archivo vacío' in respond('¿Puedes crear archivos?')
    assert 'No tengo edad' in respond('¿Cuántos años tienes?')
    assert 'No tengo permisos propios' in respond('¿Qué permisos tienes?')
    assert 'Sin un modelo local' in respond('no me gusta que tus respuestas sean predefinidas')

def test_common_acknowledgments_and_plain_language_repair():
    assert 'Excelente' in respond('excelente')
    assert 'Va' in respond('va')
    assert 'concretar' in respond('aterrizamos?')
    assert 'dejamos esa pregunta' in respond('no te pregunté eso').lower()
    assert 'dejamos eso' in respond('ninguno')

def test_common_chat_replies_are_short():
    for message in ('hola','gracias','excelente','ok','va'):
        assert len(respond(message))<=50

def test_user_phrases_from_terminal_feedback_are_understood():
    assert 'archivos' in respond('¿En qué me puedes ayudar?')
    assert 'alegra' in respond('Me encanta esta animación')
    assert 'sugiera' in respond('Mmmm no lo sé')
    assert 'qué necesitas' in respond('Necesito uqe')
    answer=respond('Me encanta el proyecto porque cada vez es más robusto y completo')
    assert 'añadimos pruebas' in answer and 'límites' in answer
