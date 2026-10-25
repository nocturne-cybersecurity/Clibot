"""Natural language wrapper for the safe arithmetic capability."""
import re, unicodedata
from core.contracts import Operation, Plan, Risk

_SMALL = {
    'cero':0,'un':1,'uno':1,'una':1,'dos':2,'tres':3,'cuatro':4,'cinco':5,'seis':6,'siete':7,'ocho':8,'nueve':9,
    'diez':10,'once':11,'doce':12,'trece':13,'catorce':14,'quince':15,'dieciseis':16,'diecisiete':17,'dieciocho':18,
    'diecinueve':19,'veinte':20,'veintiuno':21,'veintiun':21,'veintidos':22,'veintitres':23,'veinticuatro':24,
    'veinticinco':25,'veintiseis':26,'veintisiete':27,'veintiocho':28,'veintinueve':29,
}
_TENS={'treinta':30,'cuarenta':40,'cincuenta':50,'sesenta':60,'setenta':70,'ochenta':80,'noventa':90}
_HUNDREDS={'cien':100,'ciento':100,'doscientos':200,'trescientos':300,'cuatrocientos':400,'quinientos':500,
           'seiscientos':600,'setecientos':700,'ochocientos':800,'novecientos':900}
_NUMBER_WORDS={**_SMALL,**_TENS,**_HUNDREDS,'mil':1000,'millon':1_000_000,'millones':1_000_000}
_NUMBER_TOKEN='(?:'+'|'.join(sorted(map(re.escape,_NUMBER_WORDS),key=len,reverse=True))+')'
_NUMBER_PHRASE=re.compile(r'(?<!\w)('+_NUMBER_TOKEN+r'(?:\s+(?:y\s+)?'+_NUMBER_TOKEN+r')*)(?!\w)',re.I)
_OPERATOR_WORDS=r'(?:mas|menos|multiplicado\s+por|dividido\s+entre|dividido\s+por|veces|\+|\-|\*|\/)'
_NUMBER_EXPRESSION=re.compile(
    r'(?<!\w)\d+(?:\.\d+)?\s*(?:'+_OPERATOR_WORDS+r'|\bpor\b|\bentre\b)\s*(?:\d+|'+_NUMBER_TOKEN+r')\b'
    r'|(?<!\w)'+_NUMBER_TOKEN+r'\s+(?:mas|menos|multiplicado\s+por|dividido\s+entre)\s+(?:\d+|'+_NUMBER_TOKEN+r')\b',
    re.I
)
_CALC=re.compile(r'\b(?:calcula|calcular|cuanto\s+es|cuanto\s+da|what\s+is|compute|raiz|rainz|raices|root|seno|sen|coseno|tangente|logaritmo|sqrt|cbrt|cos|tan|log|ln)\b|\bsin\(',re.I)

def _expression(text):
    value=text.strip().rstrip('?.!')
    value=''.join(char for char in unicodedata.normalize('NFKD',value) if not unicodedata.combining(char))
    value=re.sub(r'(?i)^\s*(?:por favor\s+)?(?:calcula(?:r)?|cuanto\s+(?:es|da)|what\s+is|compute)\s*','',value)
    value=re.sub(r'(?i)\brainz\b','raiz',value)
    value=_NUMBER_PHRASE.sub(lambda match:str(_parse_number_words(match.group(1))),value)
    value=re.sub(r'(?i)\b(?:la\s+)?raiz\s+cuadrada\s+de\s+(\d+(?:\.\d+)?|\([^()]*\))',r'sqrt(\1)',value)
    value=re.sub(r'(?i)\b(?:la\s+)?raiz\s+cubica\s+de\s+(\d+(?:\.\d+)?|\([^()]*\))',r'cbrt(\1)',value)
    value=re.sub(r'(?i)\braiz\s+de\s+(\d+(?:\.\d+)?|\([^()]*\))',r'sqrt(\1)',value)
    value=re.sub(r'(?i)\b(\d+(?:\.\d+)?)\s+elevad[oa]s?\s+a\s+(\d+(?:\.\d+)?)\b',r'(\1**\2)',value)
    value=re.sub(r'(?i)\b(\d+(?:\.\d+)?)\s+al\s+cuadrado\b',r'(\1**2)',value)
    value=re.sub(r'(?i)\b(\d+(?:\.\d+)?)\s+al\s+cubo\b',r'(\1**3)',value)
    aliases={'seno':'sin','sen':'sin','coseno':'cos','tangente':'tan','logaritmo':'log','logaritmo10':'log10'}
    for source,target in aliases.items():value=re.sub(r'(?i)\b'+source+r'\b',target,value)
    value=re.sub(r'(?i)\b(sin|cos|tan|sqrt|cbrt|log10|log|ln|exp|abs|floor|ceil)\s+de\s+(.+)$',r'\1(\2)',value)
    for phrase,symbol in [('multiplicado por','*'),('dividido entre','/'),('dividido por','/'),('dividido','/'),('veces','*'),('por','*'),('entre','/'),('mas','+'),('menos','-')]:
        value=re.sub(r'\b'+phrase+r'\b',symbol,value)
    value=value.replace('×','*').replace('÷','/').replace('−','-').replace('^','**').replace(',','.')
    return value.strip()


def _parse_number_words(phrase):
    total=current=0
    for word in re.findall(_NUMBER_TOKEN,phrase.casefold()):
        if word=='y':continue
        value=_NUMBER_WORDS[word]
        if word in {'mil','millon','millones'}:
            total+=(current or 1)*value
            current=0
        else:
            current+=value
    return total+current

def _handler(text,context=None):
    normalized=text.casefold()
    if 'descuento' in normalized or 'discount' in normalized:
        numbers=re.findall(r'(?<!\w)\d+(?:[.,]\d+)?%?',text)
        if len(numbers)<2:
            if context is not None:context.pending={'kind':'math_discount'}
            return Plan([],text,'¿Cuál es el monto total y qué porcentaje de descuento aplico? Por ejemplo: 1250 y 15%.')
        amount=float(numbers[0].replace(',','.').rstrip('%')); percent=float(numbers[1].replace(',','.').rstrip('%'))
        if not 0<=percent<=100:return Plan([],text,'El porcentaje de descuento debe estar entre 0 y 100%.')
        expression=f'{amount}*(1-{percent}/100)'
    else:expression=_expression(text)
    if not expression:return Plan([],text,'¿Qué operación quieres calcular? Puedes escribir, por ejemplo, «raíz cuadrada de 81» o «2 elevado a 8».')
    return Plan([Operation('calculator','evaluate',{'expression':expression},description='calcular '+expression,risk=Risk.READ_ONLY)],text)

def register(router):router.register('calculator',[_CALC.pattern,_NUMBER_EXPRESSION.pattern],_handler,priority=120)
