"""Bounded calculator for scalar arithmetic and common scientific functions."""
import ast, math, operator

_BINARY={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow}
_UNARY={ast.UAdd:operator.pos,ast.USub:operator.neg}
_FUNCTIONS={
    'sqrt':math.sqrt,'cbrt':lambda x:math.copysign(abs(x)**(1/3),x),'root':lambda x,n:math.copysign(abs(x)**(1/n),x),
    'sin':lambda x:math.sin(math.radians(x)),'cos':lambda x:math.cos(math.radians(x)),'tan':lambda x:math.tan(math.radians(x)),
    'asin':lambda x:math.degrees(math.asin(x)),'acos':lambda x:math.degrees(math.acos(x)),'atan':lambda x:math.degrees(math.atan(x)),
    'log':math.log,'log10':math.log10,'ln':math.log,'exp':math.exp,'abs':abs,'round':round,'floor':math.floor,'ceil':math.ceil,
}
_CONSTANTS={'pi':math.pi,'e':math.e,'tau':math.tau}

def evaluate(expression):
    expression=str(expression).strip().lower()
    
    # Convert natural language to math notation
    replacements = {
        'mas': '+',
        'menos': '-',
        'por': '*',
        'entre': '/',
        'dividido': '/',
        'elevado a': '**',
        'al cuadrado': '**2',
        'al cubo': '**3',
        'raiz de': 'sqrt(',
        'raiz cuadrada de': 'sqrt(',
        'raiz cubica de': 'cbrt(',
        'seno de': 'sin(',
        'coseno de': 'cos(',
        'tangente de': 'tan(',
        'logaritmo de': 'log(',
        'logaritmo natural de': 'ln(',
        'exponencial de': 'exp(',
        'valor absoluto de': 'abs(',
        'redondear': 'round(',
    }
    
    for word, symbol in replacements.items():
        expression = expression.replace(word, symbol)
    
    # Close parentheses for functions
    if 'sqrt(' in expression and expression.count('sqrt(') > expression.count(')'):
        expression += ')'
    if 'cbrt(' in expression and expression.count('cbrt(') > expression.count(')'):
        expression += ')'
    if 'sin(' in expression and expression.count('sin(') > expression.count(')'):
        expression += ')'
    if 'cos(' in expression and expression.count('cos(') > expression.count(')'):
        expression += ')'
    if 'tan(' in expression and expression.count('tan(') > expression.count(')'):
        expression += ')'
    if 'log(' in expression and expression.count('log(') > expression.count(')'):
        expression += ')'
    if 'ln(' in expression and expression.count('ln(') > expression.count(')'):
        expression += ')'
    if 'exp(' in expression and expression.count('exp(') > expression.count(')'):
        expression += ')'
    if 'abs(' in expression and expression.count('abs(') > expression.count(')'):
        expression += ')'
    if 'round(' in expression and expression.count('round(') > expression.count(')'):
        expression += ')'
    
    if not expression or len(expression)>256:raise ValueError('La expresión está vacía o es demasiado larga (máximo 256 caracteres).')
    try:tree=ast.parse(expression,mode='eval')
    except SyntaxError as exc:raise ValueError('No pude leer esa expresión matemática.') from exc
    if sum(1 for _ in ast.walk(tree))>64:raise ValueError('La expresión tiene demasiados elementos.')
    try:result=_visit(tree.body)
    except (ArithmeticError,OverflowError) as exc:raise ValueError(f'La operación no tiene un resultado real válido: {exc}') from exc
    if isinstance(result,bool) or not isinstance(result,(int,float)):raise ValueError('El resultado no es un número real finito dentro del rango admitido.')
    if isinstance(result,int) and result.bit_length()>1024:raise ValueError('El resultado entero excede el tamaño permitido.')
    try:finite=math.isfinite(result)
    except OverflowError:finite=False
    if not finite or abs(result)>1e300:
        raise ValueError('El resultado no es un número real finito dentro del rango admitido.')
    return {'expression':expression,'result':result}

def _visit(node):
    if isinstance(node,ast.Constant) and type(node.value) in (int,float):return node.value
    if isinstance(node,ast.Name) and node.id in _CONSTANTS:return _CONSTANTS[node.id]
    if isinstance(node,ast.UnaryOp) and type(node.op) in _UNARY:return _UNARY[type(node.op)](_visit(node.operand))
    if isinstance(node,ast.BinOp) and type(node.op) in _BINARY:
        left,right=_visit(node.left),_visit(node.right)
        if isinstance(node.op,ast.Pow) and (abs(right)>1000 or abs(left)>1e100):raise ValueError('Exponente fuera del límite permitido.')
        value=_BINARY[type(node.op)](left,right)
        if isinstance(value,complex):raise ValueError('Esta operación produce un resultado complejo; solo admito resultados reales.')
        return value
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in _FUNCTIONS and not node.keywords:
        args=[_visit(arg) for arg in node.args]
        if len(args) not in (1,2):raise ValueError('La función requiere uno o dos argumentos.')
        return _FUNCTIONS[node.func.id](*args)
    raise ValueError('Solo admito operaciones aritméticas y funciones matemáticas conocidas; no ejecuto código.')
