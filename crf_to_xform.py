from xml.etree import ElementTree
import sys
import collections

Choice = collections.namedtuple('Choice', ['label', 'value'])
ChoiceList = collections.namedtuple('ChoiceList', ['id', 'name', 'datatype', 'choices'])
Question = collections.namedtuple('Question', ['id', 'name', 'datatype', 'label', 'choices'])
QuestionGroup = collections.namedtuple('QuestionGroup', ['id', 'name', 'items'])
Form = collections.namedtuple('Form', ['id', 'version', 'items'])

def _(tag, ns_prefix=None):
    namespace_uri = {
        None: 'http://www.cdisc.org/ns/odm/v1.3',
        'oc': 'http://www.openclinica.org/ns/odm_ext_v130/v3.1',
        'ocr': 'http://www.openclinica.org/ns/rules/v3.1',
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

def parse_forms(root, groups):
    studyevents = node.findall(_('StudyEventDef'))
    formdefs = node.findall(_('FormDef'))
    return get_forms(studyevents, formdefs, groups)

def get_forms(studyevents, formdefs, groups):
    return [parse_form(form_info(studyevent, formdefs), groups) for studyevent in studyevents]

def form_info(studyevent, formdefs):
    id = studyevent.attrib['OID']
    versions = [fr.attrib['FormOID'] for fr in studyevent.findall(_('FormRef'))]
    latest_version = versions[0]
    form_node = [n for n in formdefs if n.attrib['OID'] == latest_version][0]
    return {'id': id, 'version': latest_version, 'node': form_node}

def parse_rules(node):
    pass

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
    
    
if __name__ == "__main__":

    doc = ElementTree.parse(sys.stdin)
    root = doc.getroot()

    node = root.find(_('Study')).find(_('MetaDataVersion'))

    codelists = parse_code_lists(node)
    questions = parse_items(node, codelists)
    groups = parse_groups(node, questions)
    forms = parse_forms(node, groups)

    parse_rules(node.find(_('Rules', 'ocr')))

    pprint(forms)

