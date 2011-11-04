import ply.lex as lex
import ply.yacc as yacc

tokens = (
    'OID',
    'NUM',
    'STR',
    'LPAREN',
    'RPAREN',
    'PLUS',
    'MINUS',
    'MULT',
    'DIV',
    'EQ',
    'NEQ',
    'LT',
    'LTE',
    'GT',
    'GTE',
    'AND',
    'OR',
)

t_LPAREN = r'\('
t_RPAREN = r'\)'
t_PLUS = r'\+'
t_MINUS = r'-'
t_MULT = r'\*'
t_DIV = r'/'
t_EQ = r'eq'
t_NEQ = r'ne'
t_LT = r'lt'
t_LTE = r'lte'
t_GT = r'gt'
t_GTE = r'gte'
t_AND = r'and'
t_OR = r'or'

def t_OID(t):
    r'[A-Z_][A-Z0-9_]*(\.[A-Z_][A-Z0-9_]*)*'
    t.value = ('oid', t.value)
    return t

def t_NUM(t):
    r'([0-9]+(\.[0-9]*)?)|(\.[0-9]+)'
    t.value = ('numlit', float(t.value))
    return t

def t_STR(t):
    r'"[^"]*"'
    t.value = ('strlit', t.value[1:-1])
    return t

t_ignore = " \t\n"

lexer = lex.lex()

precedence = (
    ('right', 'OR'),
    ('right', 'AND'),
    ('left', 'EQ', 'NEQ'),
    ('left', 'LT', 'LTE', 'GT', 'GTE'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'MULT','DIV'),
    ('nonassoc', 'UMINUS'),
)

def p_expr(t):
    """expr : base_expr
            | op_expr
    """
    t[0] = t[1]

def p_base_expr(t):
    """base_expr : LPAREN expr RPAREN
                 | OID
                 | NUM
                 | STR
    """
    if len(t) > 2:
        t[0] = t[2]
    else:
        t[0] = t[1]

def p_op_expr(t):
    """op_expr : expr OR expr
               | expr AND expr
               | expr EQ expr
               | expr NEQ expr
               | expr LT expr
               | expr LTE expr
               | expr GT expr
               | expr GTE expr
               | expr PLUS expr
               | expr MINUS expr
               | expr MULT expr
               | expr DIV expr
               | MINUS expr %prec UMINUS
    """
    if len(t) == 3:
        t[0] = ('uminus', t[2])
    else:
        try:
            op = {
                '+': 'add',
                '-': 'subtr',
                '*': 'mult',
                '/': 'div',
                'ne': 'neq',
            }[t[2]]
        except KeyError:
            op = t[2]
        t[0] = (op, t[1], t[3])

parser = yacc.yacc()

def parse(raw):
    return parser.parse(raw, lexer=lexer)

