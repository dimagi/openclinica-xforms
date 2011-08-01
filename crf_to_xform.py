from xml.etree import ElementTree
import sys
import collections

Choice = collections.namedtuple('Choice', ['label', 'value'])
ChoiceList = collections.namedtuple('ChoiceList', ['id', 'name', 'datatype', 'choices'])
Question = collections.namedtuple('Question', ['id', 'name', 'datatype', 'label', 'choices'])

def _(tag, ns_prefix=None):
    namespace_uri = {
        None: 'http://www.cdisc.org/ns/odm/v1.3',
        'oc': 'http://www.openclinica.org/ns/odm_ext_v130/v3.1',
        'ocr': 'http://www.openclinica.org/ns/rules/v3.1',
    }[ns_prefix]
    return '{%s}%s' % (namespace_uri, tag)

def get_forms(studyevents, formdefs):
    return [get_form(studyevent, formdefs) for studyevent in studyevents]

def get_form(studyevent, formdefs):
    form_id, version = form_info(studyevent)
    form_node = [n for n in formdefs if n.attrib['OID'] == version][0]
    return {'id': form_id, 'version': version, 'node': form_node}

def form_info(studyevent):
    id = studyevent.attrib['OID']
    versions = [fr.attrib['FormOID'] for fr in studyevent.findall(_('FormRef'))]
    latest_version = versions[0]

    return id, latest_version

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
    return filter(lambda e: e, (parse_item(item_node, code_lists) for item_node in root.findall(_('ItemDef'))))

def parse_item(item_node, code_lists):
    id = item_node.attrib['OID']
    name = item_node.attrib['Name']
    datatype = item_node.attrib['DataType']
    # maxlen?

    q_node = item_node.find(_('Question'))
    if q_node is None:
        #calculated field only?
        return None

    label = q_node.find(_('TranslatedText')).text.strip()

    choices_node = item_node.find(_('CodeListRef'))
    if choices_node is not None:
        datatype = 'choice'
        choices = code_lists[choices_node.attrib['CodeListOID']]
    else:
        choices = None

    return Question(id, name, datatype, label, choices)


doc = ElementTree.parse(sys.stdin)
root = doc.getroot()

node = root.find(_('Study')).find(_('MetaDataVersion'))




studyevents = node.findall(_('StudyEventDef'))
formdefs = node.findall(_('FormDef'))
itemgroupdefs = node.findall(_('ItemGroupDef'))
itemdefs = node.findall(_('ItemDef'))    

#forms = get_forms(studyevents, formdefs)
#print forms


codelists = parse_code_lists(node)
print parse_items(node, codelists)
