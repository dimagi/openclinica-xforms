from crf_to_xform import _, pprintxml, convert_xform
from xml.etree import ElementTree as et
import sys
import re
from optparse import OptionParser
from StringIO import StringIO
import util

def parse_metadata(root):
    xmlns, tag = util.split_tag(root.tag)
    m = re.match(r'.+/(?P<study>[^/]+)/(?P<mdv>[^/]+)/(?P<studyevent>[^/]+)/?', xmlns)

    meta = {
        'xmlns': xmlns,
        'form': tag,
    }
    meta.update((k, m.group(k)) for k in ['study', 'mdv', 'studyevent'])
    return meta

def build_submission(root, ref_instance):
    metadata = parse_metadata(root)

    def _i(tag):
        return '{%s}%s' % (metadata['xmlns'], tag)

    subject = extract_subject(root, _i)
    crf_root = root.find(_i('crf'))
    crf_root = reconcile_instance(crf_root, ref_instance)

    odm = et.Element(_('ODM'))
    clindata = et.SubElement(odm, _('ClinicalData'))
    clindata.attrib['StudyOID'] = metadata['study']
    clindata.attrib['MetaDataVersionOID'] = metadata['mdv']

    subjdata = et.SubElement(clindata, _('SubjectData'))
    subjdata.attrib['SubjectKey'] = subject

    seevtdata = et.SubElement(subjdata, _('StudyEventData'))
    seevtdata.attrib['StudyEventOID'] = metadata['studyevent']

    convert_instance(crf_root, seevtdata, metadata['form'])

    return odm

def extract_subject(root, _):
    patient_info = root.find(_('subject'))
    pat_id = patient_info.find(_('pat_id')).text

    return 'SS_%s' % pat_id # is this reliable?

def reconcile_instance(inst_node, ref_node):
    """xforms hides non-relevant nodes, but ODM expects them with empty
    values. take the 'gold-standard' instance from the original form and
    populate it with the submitted data"""
    if inst_node is None:
        pass
    elif list(ref_node):
        for ref_child in ref_node:
            reconcile_instance(inst_node.find(ref_child.tag), ref_child)
    else:
        ref_node.text = inst_node.text
    return ref_node

def convert_instance(in_node, out_node, form_name=None):
    xmlns, name = util.split_tag(in_node.tag)

    if list(in_node):
        if form_name:
            group = et.SubElement(out_node, _('FormData'))
            group.attrib['FormOID'] = form_name
        else:
            group = et.SubElement(out_node, _('ItemGroupData'))
            group.attrib['ItemGroupOID'] = name
            group.attrib['ItemGroupRepeatKey'] = str(1)
            group.attrib['TransactionType'] = 'Insert'

        for child in in_node:
            convert_instance(child, group)
    else:
        q = et.SubElement(out_node, _('ItemData'))
        q.attrib['ItemOID'] = name
        q.attrib['Value'] = (in_node.text or '')

def convert_odm(f, source):
    doc = et.parse(f)
    return build_submission(doc.getroot(), list(source.find('.//%s' % _('instance', 'xf')))[0])

def process_instance(xfinst, xform_path):
    resp = {}

    f_inst = StringIO()
    f_inst.write(xfinst)

    f_inst.seek(0)
    inst = util.strip_namespaces(f_inst)
    contains_screening = not(int(inst.find('.//tmp/screening_complete').text))

    if contains_screening:
        f_inst.seek(0)
        resp['screening'] = convert_odm(f_inst, load_source(xform_path=xform_path))
    else:
        resp['screening'] = None

    return resp

def load_source(xform_path=None, crf_path=None):
    with open(xform_path or crf_path) as f:
        if xform_path:
            return et.parse(f).getroot()
        else:
            return convert_xform(f)

if __name__ == "__main__":
    
    parser = OptionParser()
    parser.add_option("-x", "--xform", dest="xform",
                      help="source xform", metavar="FILE")
    parser.add_option("-f", "--crf", dest="crf",
                      help="source CRF", metavar="FILE")

    (options, args) = parser.parse_args()
   
    inst = (sys.stdin if args[0] == '-' else open(args[0]))
    pprintxml(util.dump_xml(convert_odm(inst, load_source(options.xform, options.crf))))

