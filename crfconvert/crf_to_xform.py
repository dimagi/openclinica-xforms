import sys
import os.path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from xml.etree import ElementTree as et
from StringIO import StringIO
import itertools
import collections
import expr_parse
import hashlib
from subprocess import Popen, PIPE
import csv
from optparse import OptionParser
import util
import json

ChoiceList = collections.namedtuple('ChoiceList', ['id', 'name', 'datatype', 'choices'])
RuleDef = collections.namedtuple('RuleDef', ['id', 'expr'])

class Rule(object):
    def __init__(self, expr, action, target, set_val, trigger):
        self.expr = expr
        self.action = action
        self.target = target
        self.set_val = set_val
        self.trigger = trigger

    def xpath(self, oid_to_ref):
        return expr_to_xpath(self.expr, oid_to_ref)

class XRule(object):
    def __init__(self, action, _target, expr, *_refs):
        self.action = action
        self.target = self.oid_or_obj(_target)
        self.expr = expr
        self._refs = _refs

        self.constraint_msg = None

    def oid_or_obj(self, o):
        try:
            return o.id
        except AttributeError:
            return o

    def xpath(self, oid_to_ref):
        return self.expr % tuple(oid_to_ref(self.oid_or_obj(_r)) for _r in self._refs)

class Choice(object):
    def __init__(self, label, value):
        self.label = label
        self.value = value
        self.ref_id = None

class Question(object):
    def __init__(self, id, name, datatype, label, choices):
        self.id = id
        self.name = name
        self.datatype = datatype
        self.label = label
        self._ch = choices
        self.required = None

    def type(self):
        if self.datatype == 'choice':
            return 'select1' #can't handle multiselect yet
        else:
            try:
                return {
                    'integer': 'int',
                    'float': 'float',
                    'barcode': 'barcode',
                }[self.datatype]
            except KeyError:
                return 'str'

    def choices(self):
        if self._ch:
            for i, ch in enumerate(self._ch.choices):
                ch.ref_id = '%s#%d' % (self._ch.id, i + 1)
                yield ch

    def xf_control_type(self):
        if self.datatype == 'info':
            return 'trigger'

        try:
            return {
                'select1': 'select1',
                'selectmulti': 'select',
            }[self.type()]
        except KeyError:
            return 'input'

    def xf_datatype(self):
        if self.type() in ('str', 'select1', 'selectmulti'):
            return None
        else:
            return {'int': 'int', 'float': 'decimal', 'barcode': 'barcode'}[self.type()]

    def xpathname(self):
        return self.id

class QuestionGroup(object):
    def __init__(self, id, name, items, grouped=False):
        self.id = id
        self.name = name
        self.items = items
        self.grouped = grouped

    def xpathname(self):
        return self.id

class Form(object):
    def __init__(self, id, version, items):
        self.id = id
        self.version = version
        self.items = items

    def xpathname(self):
        return self.version

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

def parse_items(root, code_lists, units):
    questions = filter(lambda e: e, (parse_item(item_node, code_lists, units) for item_node in root.findall(_('ItemDef'))))
    return dict((q.id, q) for q in questions)

def parse_item(item_node, code_lists, units={}):
    id = item_node.attrib['OID']
    name = item_node.attrib['Name']
    datatype = item_node.attrib['DataType']
    # maxlen?

    mu_node = item_node.find(_('MeasurementUnitRef'))
    unit = units[mu_node.attrib['MeasurementUnitOID']] if mu_node is not None else None

    q_node = item_node.find(_('Question'))
    if q_node is None:
        #calculated field only?
        label = '[[ %s : calculate / preload?? ]]' % name
        #return None
    else:
        label = q_node.find(_('TranslatedText')).text.strip()
        if unit:
            label += ' (in %s)' % unit

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

    def get_child(itemrefnode):
        child = items[itemrefnode.attrib['ItemOID']]
        child.required = (itemrefnode.attrib['Mandatory'].lower() == 'yes')
        return child
    children = [get_child(c) for c in child_nodes]

    return QuestionGroup(id, name, children)

def parse_units(node):
    def parse_unit(unit):
        id = unit.attrib['OID']
        name = unit.find(_('Symbol')).find(_('TranslatedText')).text.strip()
        return (id, name)

    return dict(parse_unit(unit) for unit in node.findall('.//%s' % _('MeasurementUnit')))

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

def parse_study(docroot, options={}):
    study = docroot.find(_('Study'))
    study_id = study.attrib['OID']

    node = study.find(_('MetaDataVersion'))
    mdv = node.attrib['OID']

    mu = parse_units(study)
    codelists = parse_code_lists(node)
    questions = parse_items(node, codelists, mu)
    groups = parse_groups(node, questions)
    forms = parse_forms(node, groups)
    rules = parse_rules(node.find(_('Rules', 'ocr')))

    inject_structure(forms[0], rules, options)
    return (study_id, mdv), forms, rules

def _find_item(form, id):
    i = [n for n in _all_instance_nodes(form) if n.id == id][0]
    parent = [n for n in _all_instance_nodes(form, True) if hasattr(n, 'items') and i in n.items][0]
    return (i, parent)

def inject_structure(form, rules, options):
    crf_group = QuestionGroup('crf', None, form.items)

    pat_id = Question('pat_id', None, 'str', None, None)
    pat_inits = Question('initials', None, 'str', None, None)
    reg_group = QuestionGroup('subject', None, [pat_id, pat_inits])
    rules.extend([
        XRule('calculated', pat_id, "context('pat-id')"),
        XRule('calculated', pat_inits, "context('initials')"),
    ])

    tmp_group = QuestionGroup('tmp', None, [])

    # convert height question to feet/inches
    height_ids = options.get('height', 'I_CPCS_HEIGHT')
    if not hasattr(height_ids, '__iter__'):
        height_ids = [height_ids]
    for HEIGHT_ID in height_ids:
        INCH_SUFFIX = ' (in inches)' 
        q_height, height_parent = _find_item(form, HEIGHT_ID)
        if q_height.label.endswith(INCH_SUFFIX): #ghetto
            height_ft = Question('height_feet', None, 'integer', q_height.label[:-len(INCH_SUFFIX)] + '\n\n(feet)', None)
            height_in = Question('height_inches', None, 'integer', '(inches)', None)
            q_height.label = None

            qc_height = QuestionGroup('__%s' % HEIGHT_ID, None, [height_ft, height_in], True)
            height_parent.items.insert(height_parent.items.index(q_height), qc_height)
            rules.append(XRule('calculated', q_height, '12 * %s + %s', height_ft, height_in))

    # kill literacy section
    lit, parent = _find_item(form, 'IG_CPCS_LITERACY')
    parent.items.remove(lit)

    form.items = [reg_group, crf_group, tmp_group]

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
            action_type = 'relevancy' if not is_action(n_act, 'InsertAction') else 'calculated'
            if_true = {'true': True, 'false': False}[n_act.attrib['IfExpressionEvaluates']]
            if is_action(n_act, 'HideAction'):
                if_true = not if_true
            if not if_true:
                expr = ('not', expr)

            for n_dst in n_act.findall(_('DestinationProperty', 'ocr')):
                dst = n_dst.attrib['OID']
                set_val = n_dst.attrib['Value'] if is_action(n_act, 'InsertAction') else None

                yield Rule(expr, action_type, dst, set_val, _trigger)

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
    return (parent_prec > child_prec or (parent_prec == child_prec and side != 'unary' and assoc != side))

def expr_to_xpath(expr, oid_to_ref):

    def subexpr_to_xpath(side):
        parent_op = expr[0]
        subexpr = expr[{'left': 1, 'right': 2, 'unary': 1}[side]]
        return ('(%s)' if needs_parens(parent_op, subexpr[0], side) else '%s') % expr_to_xpath(subexpr, oid_to_ref)

    type = expr[0]
    if type == 'numlit':
        return expr[1]
    elif type == 'strlit':
        return "%s" % expr[1]
    elif type == 'oid':
        return oid_to_ref(expr[1])
    elif type == 'neg':
        return '-%s' % subexpr_to_xpath('unary')
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
        return '%s %s %s' % (subexpr_to_xpath('left'), op, subexpr_to_xpath('right'))

def build_xform(metadata, form, rules, options):
    #todo: namespaces; register_namespace only supported in py2.7

    root = et.Element(_('html', 'h'))
    head = et.SubElement(root, _('head', 'h'))
    body = et.SubElement(root, _('body', 'h'))

    title = et.SubElement(head, _('title', 'h'))
    title.text = '%s :: %s' % (form.id, form.version)
    model = et.SubElement(head, _('model', 'xf'))
    build_model(model, form, rules, metadata, options)

    build_body(body, form)

    return root

def build_model(node, form, rules, metadata, options):
    inst = et.SubElement(node, _('instance', 'xf'))
    _build_inst(inst, form, metadata)
    build_binds(node, form, rules)
    build_itext(node, form, options)

def build_binds(node, form, rules):
    for o in _all_instance_nodes(form):
        bind = et.Element(_('bind', 'xf'))
        bind.attrib['nodeset'] = xpathref(o.id, form)

        if isinstance(o, Question):
            if o.xf_datatype():
                bind.attrib['type'] = o.xf_datatype()

            if o.required:
                bind.attrib['required'] = 'true()'

        build_bind_rules(bind, o, rules, form)

        needs_bind = bool(set(bind.attrib.keys()) - set(['nodeset']))
        if needs_bind:
            node.append(bind)

def build_bind_rules(bind, o, rules, form):

    def oid_to_ref(oid):
        if '.' in oid:
            raise Exception('don\'t support compound oids yet')
        return xpathref(oid, form)

    matching_rules = [r for r in rules if r.target == o.id]

    if len(matching_rules) > 1:
        sys.stderr.write('item [%s] with more than one rule -- not supported yet\n' % o.id)
    rule = (matching_rules[0] if matching_rules else None)

    if not rule:
        return False

    #todo: warning if 'trigger' does not appear in expr

    attr = {
        'relevancy': 'relevant',
        'calculated': 'calculate',
        'constraint': 'constraint',
    }[rule.action]
    bind.attrib[attr] = rule.xpath(oid_to_ref)

    if rule.action == 'constraint' and rule.constraint_msg:
        bind.attrib[_('constraintMsg', 'jr')] = rule.constraint_msg

    return True

noderefs = {}
def xpathref(oid, form):
    if not noderefs:
        noderefs.update(gen_refs(form))

    return noderefs[oid]
    
def gen_refs(o, path=['']):
    path.append(o.xpathname())
    yield (o.id, '/'.join(path))
    if hasattr(o, 'items'):
        for child in o.items:
            for entry in gen_refs(child, list(path)):
                yield entry

def _all_instance_nodes(o, include_root=False):
    if include_root:
        yield o

    if hasattr(o, 'items'):
        for child in o.items:
            yield child
            for node in _all_instance_nodes(child):
                yield node

def _build_inst(inst_node, form, metadata):
    xmlns = 'http://openclinica.org/xform/%s/%s/%s/' % (metadata[0], metadata[1], form.id)
    build_inst(inst_node, form, xmlns)

def build_inst(parent_node, instance_item, xmlns):
    inst_node = et.SubElement(parent_node, '{%s}%s' % (xmlns, instance_item.xpathname()))
    if hasattr(instance_item, 'items'):
        for child in instance_item.items:
            build_inst(inst_node, child, xmlns)

DEFAULT_LANG = 'en'

def build_itext(parent_node, form, options):
    itext = et.SubElement(parent_node, _('itext', 'xf'))

    def gen_idict():
        for o in _all_instance_nodes(form):
            if isinstance(o, Question):
                if o.label:
                    yield (o.id, o.label)
                    for ch in o.choices():
                        yield (ch.ref_id, ch.label)
            else:
                if o.name:
                    yield (o.id, o.name)
    ref_idict = dict(gen_idict())
    build_itext_lang(itext, DEFAULT_LANG, ref_idict)

    # dump csv for manual translation
    if options['dumptx']:
        dumpfile = 'itext_dump.csv'
        sys.stderr.write('dumping text to %s\n' % dumpfile)
        with open(dumpfile, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(['KEY', DEFAULT_LANG.upper()])
            for k, v in sorted(ref_idict.iteritems()):
                writer.writerow([k, v.encode('utf-8')])
    
    # load in externally-supplied translations for other languages
    if options['translations']:
        with open(options['translations']) as f:
            reader = csv.DictReader(f)
            langs = [k.lower() for k in reader.fieldnames if k.lower() not in ('key', DEFAULT_LANG)]
            sys.stderr.write('additional locales: %s\n' % str(langs))
            data = list(reader)
            for lang in langs:
                idict = dict((row['KEY'], unicode(row[lang.upper()], 'utf-8')) for row in data)

                mapping_missing = set(ref_idict) - set(idict)
                mapping_addtl = set(idict) - set(ref_idict)
                if mapping_missing:
                    sys.stderr.write('locale %s does not define translations for %s\n' % (lang, str(sorted(mapping_missing))))
                if mapping_addtl:
                    sys.stderr.write('locale %s defines unknown translations for %s\n' % (lang, str(sorted(mapping_addtl))))

                build_itext_lang(itext, lang, idict)

def build_itext_lang(parent_node, lang, idict):
    node_lang = et.SubElement(parent_node, _('translation', 'xf'))
    node_lang.attrib['lang'] = lang
    if lang == DEFAULT_LANG:
        node_lang.attrib['default'] = ''

    for k, v in sorted(idict.iteritems()):
        build_itext_entry(node_lang, k, v)

def build_itext_entry(parent_node, ref, text):
    n = et.SubElement(parent_node, _('text', 'xf'))
    n.attrib['id'] = ref
    v = et.SubElement(n, _('value', 'xf'))
    v.text = text

    # temp
    vaud = et.SubElement(n, _('value', 'xf'))
    vaud.attrib['form'] = 'audio'
    vaud.text = 'jrtts://'

def _addnode(parent, node):
    if node:
        parent.append(node)

def build_body(node, form):
    for child in form.items:
        _addnode(node, build_body_item(child))

def build_body_item(item):
    if hasattr(item, 'items'):
        #group
        node = et.Element(_('group', 'xf'))
        node.attrib['ref'] = item.xpathname()
        if item.name:
            make_label(node, item.id)
        if item.grouped:
            node.attrib['appearance'] = 'field-list' #'full'
        for child in item.items:
            _addnode(node, build_body_item(child))

        if len(node) == 0:
            node = None  # empty group; don't generate
    else:
        node = build_question(item)
    return node

def build_question(item):
    if not item.label:
        return None

    q = et.Element(_(item.xf_control_type(), 'xf'))
    q.attrib['ref'] = item.xpathname()
    make_label(q, item.id)
    for choice in item.choices():
        ch = et.SubElement(q, _('item', 'xf'))
        make_label(ch, choice.ref_id, choice.label)
        val = et.SubElement(ch, _('value', 'xf'))
        val.text = str(choice.value)
    return q

def make_label(parent, key=None, inline=None):
    label = et.SubElement(parent, _('label', 'xf'))
    if key:
        label.attrib['ref'] = itext(key)
    if inline:
        label.text = inline

def itext(key):
    return 'jr:itext(\'%s\')' % key




# utility code
def create_audio(text, lang):
    MEDIA_DIR = '/home/drew/tmp/uconn_media'

    textbytes = text.encode('utf-8')
    filename = '%s.mp3' % hashlib.sha1(lang + ':' + textbytes).hexdigest()[:16]
    path = os.path.join(MEDIA_DIR, filename)
    if not os.path.exists(path):
        sys.stderr.write('generating audio for [%s]\n' % text[:30])
        p = Popen('text2wave | lame --quiet -V2 - %s' % path, shell=True, stdin=PIPE)
        p.communicate(textbytes)

    return 'jr://audio/%s' % filename

def convert_xform(f, options={'dumptx': False, 'translations': None}):
    doc = et.parse(f)
    study_id, forms, rules = parse_study(doc.getroot(), options)

#    util.pprint(forms)
#    util.pprint(rules)

    return build_xform(study_id, forms[0], rules, options)



    
if __name__ == "__main__":

    parser = OptionParser()
    parser.add_option("-t", "--translations", dest="translations",
                      help="load translations from FILE", metavar="FILE")
    parser.add_option("-d", "--dumptext", action="store_true", dest="dumptx", default=False,
                      help="dump english text to csv for translation")
    parser.add_option("-o", "--opts", dest="options", default='{}',
                      help="custom options as json string")

    (options, args) = parser.parse_args()

    opts = options.__dict__
    opts.update(json.loads(options.options))

    crf = (sys.stdin if args[0] == '-' else open(args[0]))
    print util.dump_xml(convert_xform(crf, opts), pretty=True)




