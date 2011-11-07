from xml.etree import ElementTree as et
from StringIO import StringIO
import sys
import itertools
import collections
import expr_parse

Choice = collections.namedtuple('Choice', ['label', 'value'])
ChoiceList = collections.namedtuple('ChoiceList', ['id', 'name', 'datatype', 'choices'])
Question = collections.namedtuple('Question', ['id', 'name', 'datatype', 'label', 'choices'])
QuestionGroup = collections.namedtuple('QuestionGroup', ['id', 'name', 'items'])
Form = collections.namedtuple('Form', ['id', 'version', 'items'])
RuleDef = collections.namedtuple('RuleDef', ['id', 'expr'])
Rule = collections.namedtuple('Rule', ['expr', 'action', 'target', 'set_val', 'trigger'])

def _(tag, ns_prefix=None):
    namespace_uri = {
        None: 'http://www.cdisc.org/ns/odm/v1.3',
        'oc': 'http://www.openclinica.org/ns/odm_ext_v130/v3.1',
        'ocr': 'http://www.openclinica.org/ns/rules/v3.1',
        'xf': 'http://www.w3.org/2002/xforms',
        'h': 'http://www.w3.org/1999/xhtml',
        'jr': 'http://openrosa.org/javarosa',
    }[ns_prefix]
    return '{%s}%s' % (namespace_uri, tag)

def parse_code_lists(root):
    code_lists = [parse_code_list(cl_node) for cl_node in root.findall(_('CodeList'))]
    return dict((cl.id, cl) for cl in code_lists)

def parse_code_list(cl_node):
    id = cl_node.attrib['OID']
    name = cl_node.attrib['Name']
    datatype = cl_node.attrib['DataType']
    choices = [parse_code_list_item(cli_node, datatype) for cli_node in cl_node.findall(_('CodeListItem'))]
    return ChoiceList(id, name, datatype, choices)

def parse_code_list_item(cli_node, datatype):
    value = cli_node.attrib['CodedValue']
    label = cli_node.find(_('Decode')).find(_('TranslatedText')).text.strip()

    if datatype == 'integer':
        value = int(value)

    return Choice(label, value)

def parse_items(root, code_lists):
    questions = filter(lambda e: e, (parse_item(item_node, code_lists) for item_node in root.findall(_('ItemDef'))))
    return dict((q.id, q) for q in questions)

def parse_item(item_node, code_lists):
    id = item_node.attrib['OID']
    name = item_node.attrib['Name']
    datatype = item_node.attrib['DataType']
    # maxlen?

    q_node = item_node.find(_('Question'))
    if q_node is None:
        #calculated field only?
        label = '[[ %s : calculate / preload?? ]]' % name
        #return None
    else:
        label = q_node.find(_('TranslatedText')).text.strip()

    choices_node = item_node.find(_('CodeListRef'))
    if choices_node is not None:
        datatype = 'choice'
        choices = code_lists[choices_node.attrib['CodeListOID']]
    else:
        choices = None

    return Question(id, name, datatype, label, choices)

def parse_groups(root, items):
    groups = [parse_group(group_node, items) for group_node in root.findall(_('ItemGroupDef'))]
    return dict((g.id, g) for g in groups)    

def parse_group(group_node, items):
    id = group_node.attrib['OID']
    name = group_node.attrib['Name']

    child_nodes = sorted(group_node.findall(_('ItemRef')), key=lambda node: int(node.attrib['OrderNumber']))
    children = [items[c.attrib['ItemOID']] for c in child_nodes]

    return QuestionGroup(id, name, children)

def parse_form(form_info, groups):
    child_nodes = form_info['node'].findall(_('ItemGroupRef'))
    children = [groups[c.attrib['ItemGroupOID']] for c in child_nodes]
    return Form(form_info['id'], form_info['version'], children)

def parse_forms(node, groups):
    studyevents = node.findall(_('StudyEventDef'))
    formdefs = node.findall(_('FormDef'))
    return get_forms(studyevents, formdefs, groups)

def get_forms(studyevents, formdefs, groups):
    return [parse_form(form_info(studyevent, formdefs), groups) for studyevent in studyevents]

# my understanding was that StudyEvents contain FormDefs that are different revisions of
# the same form (and selects the first as the most recent). the latest CRF has a StudyEvent
# containing different forms. worry about this later.
def form_info(studyevent, formdefs):
    id = studyevent.attrib['OID']
    versions = [fr.attrib['FormOID'] for fr in studyevent.findall(_('FormRef'))]
    latest_version = versions[0]
    form_node = [n for n in formdefs if n.attrib['OID'] == latest_version][0]
    return {'id': id, 'version': latest_version, 'node': form_node}

def parse_study(docroot):
    node = docroot.find(_('Study')).find(_('MetaDataVersion'))

    codelists = parse_code_lists(node)
    questions = parse_items(node, codelists)
    groups = parse_groups(node, questions)
    forms = parse_forms(node, groups)

    rules = parse_rules(node.find(_('Rules', 'ocr')))

    return forms, rules

def parse_rules(node):
    ruledefs = parse_ruledefs(node)
    rules = list(itertools.chain(*(parse_ruleassn(n, ruledefs) for n in node.findall(_('RuleAssignment', 'ocr')))))
    return rules

def parse_ruledefs(node):
    ruledefs = [parse_ruledef(n) for n in node.findall(_('RuleDef', 'ocr'))]
    return dict((r.id, r) for r in ruledefs)

def parse_ruledef(node):
    id = node.attrib['OID']
    expr = node.find(_('Expression', 'ocr')).text
    return RuleDef(id, expr_parse.parse(expr))

def parse_ruleassn(node, ruledefs):
    def actions(n):
        return itertools.chain(*(n.findall(_(tag, 'ocr')) for tag in ['ShowAction', 'HideAction', 'InsertAction']))

    def is_action(n, type):
        return n.tag == _(type, 'ocr')

    _trigger = node.find(_('Target', 'ocr')).text
    for rr in node.findall(_('RuleRef', 'ocr')):
        expr = ruledefs[rr.attrib['OID']].expr
        for n_act in actions(rr):
            action_type = 'relevancy' if not is_action(n_act, 'InsertAction') else 'calculate'
            if_true = {'true': True, 'false': False}[n_act.attrib['IfExpressionEvaluates']]
            if is_action(n_act, 'HideAction'):
                if_true = not if_true
            if not if_true:
                expr = ('not', expr)

            for n_dst in n_act.findall(_('DestinationProperty', 'ocr')):
                dst = n_dst.attrib['OID']
                set_val = n_dst.attrib['Value'] if is_action(n_act, 'InsertAction') else None

                yield Rule(expr, action_type, dst, set_val, _trigger)

    """
rules
  ruleassignment
    target (trigger on...) (think this is useless)
    ruleref (oid -> ruledef)
      action (show, insert) (@ifexpressionevaluates)
        run (ignore?)
        destinationproperty (oid -> item?)
  ruledef
    expression (xpath-like)
"""

def op_prec(operator):
    """return (precedence level [higher == more-tightly bound], associativity) for an operator;
    non-terminals have a higher precedence than all operators"""
    prec = [
        ('right', ['or']),
        ('right', ['and']),
        ('left', ['eq', 'neq']),
        ('left', ['lt', 'lte', 'gt', 'gte']),
        ('left', ['add', 'subtr']),
        ('left', ['mult','div']),
        (None, ['neg']),
    ]
    info = dict(itertools.chain(*[[(op, (i, assoc)) for op in ops] for i, (assoc, ops) in enumerate(prec)]))

    try:
        return info[operator]
    except KeyError:
        return (999, None)

def needs_parens(parent_op, child_op, side):
    """determine whether parens are needed around a child sub-expression"""
    parent_prec, assoc = op_prec(parent_op)
    child_prec, _ = op_prec(child_op)
    return (parent_prec > child_prec or (parent_prec == child_prec and assoc != side))

def subexpr_to_xpath(parent_op, side, subexpr):
    return ('(%s)' if needs_parens(parent_op, subexpr[0], side) else '%s') % expr_to_xpath(subexpr)

def expr_to_xpath(expr):
    type = expr[0]
    if type == 'numlit':
        return expr[1]
    elif type == 'strlit':
        return "%s" % expr[1]
    elif type == 'oid':
        return '${%s}' % expr[1]
    elif type == 'neg':
        return '-%s' % subexpr_to_xpath(expr[0], None, expr[1])
    else:
        op = {
            'add': '+',
            'subtr': '-',
            'mult': '*',
            'div': 'div',
            'eq': '=',
            'neq': '!=',
            'lt': '<',
            'lte': '<=',
            'gt': '>',
            'gte': '>=',
            'and': 'and',
            'or': 'or',
        }[expr[0]]
        return '%s %s %s' % (subexpr_to_xpath(expr[0], 'left', expr[1]), op, subexpr_to_xpath(expr[0], 'right', expr[2]))



def build_xform(form, rules):
    #todo: namespaces; register_namespace only supported in py2.7

    root = et.Element(_('html', 'h'))
    head = et.SubElement(root, _('head', 'h'))
    body = et.SubElement(root, _('body', 'h'))

    title = et.SubElement(head, _('title', 'h'))
    title.text = form.id
    model = et.SubElement(head, _('model', 'xf'))
    build_model(model, form, rules)

    build_body(body, form)

    tree = et.ElementTree(root)
    out = StringIO()
    tree.write(out, encoding='utf-8')
    return out.getvalue()

def build_model(node, form, rules):
    inst = et.SubElement(node, _('instance', 'xf'))
    build_inst(inst, form)

def _instname(n):
    return '{inst}%s' % n.lower()

def build_inst(parent_node, instance_item):
    #todo: make a real instance xmlns
    nodename = ('data' if isinstance(instance_item, Form) else instance_item.id) # or use name? are names guaranteed unique?
    inst_node = et.SubElement(parent_node, _instname(nodename))
    if hasattr(instance_item, 'items'):
        for child in instance_item.items:
            build_inst(inst_node, child)

def build_body(node, form):
    for child in form.items:
        node.append(build_body_item(child))

def build_body_item(item):
    if hasattr(item, 'items'):
        #group
        node = et.Element(_('group', 'xf'))
        node.attrib['ref'] = item.id.lower()
        label = et.SubElement(node, _('label', 'xf'))
        label.text = item.name
        for child in item.items:
            node.append(build_body_item(child))
    else:
        node = build_question(item)
    return node

def build_question(item):
    q = et.Element(_('select1' if item.choices else 'input', 'xf'))
    q.attrib['ref'] = item.id.lower()
    label = et.SubElement(q, _('label', 'xf'))
    label.text = item.label
    if item.choices:
        for choice in item.choices.choices:
            ch = et.SubElement(q, _('item', 'xf'))
            lab = et.SubElement(ch, _('label', 'xf'))
            lab.text = choice.label
            val = et.SubElement(ch, _('value', 'xf'))
            val.text = str(choice.value)
    return q

def pprint(o):
    def convert(o):
        if hasattr(o, '__iter__'):
            if hasattr(o, '_asdict'):
                return convert(o._asdict())
            elif hasattr(o, 'iteritems'):
                return dict((k, convert(v)) for k, v in o.iteritems())
            else:
                return [convert(e) for e in o]
        else:
            return o

    import pprint
    pp = pprint.PrettyPrinter(indent=2)
    pp.pprint(convert(o))
    
def pprintxml(xmlstr):
    from lxml import etree as lx
    print lx.tostring(lx.fromstring(xmlstr), pretty_print=True)
    
if __name__ == "__main__":

    doc = et.parse(sys.stdin)

    forms, rules = parse_study(doc.getroot())

    #pprint(forms)
    #pprint(rules)

    pprintxml(build_xform(forms[0], rules))
