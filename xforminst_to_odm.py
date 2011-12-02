from crf_to_xform import _, dump_xml, pprintxml, convert_xform
from xml.etree import ElementTree as et
import sys
import re
from optparse import OptionParser

def parse_metadata(root):
    m = re.match(r'\{.+/(?P<study>[^/]+)/(?P<mdv>[^/]+)/(?P<studyevent>[^/]+)/?\}(?P<form>.+)', root.tag)
    return [m.group(k) for k in ['study', 'mdv', 'studyevent', 'form']]

def build_submission(root, ref_instance):
    metadata = parse_metadata(root)
    root = reconcile_instance(root, ref_instance)
    subject = extract_subject(root)

    odm = et.Element(_('ODM'))
    clindata = et.SubElement(odm, _('ClinicalData'))
    clindata.attrib['StudyOID'] = metadata[0]
    clindata.attrib['MetaDataVersionOID'] = metadata[1]

    subjdata = et.SubElement(clindata, _('SubjectData'))
    subjdata.attrib['SubjectKey'] = subject
#    subjdata.attrib[_('StudySubjectID', 'oc')] = subject[1]

    seevtdata = et.SubElement(subjdata, _('StudyEventData'))
    seevtdata.attrib['StudyEventOID'] = metadata[2]

    convert_instance(root, seevtdata, True)

    return odm

def extract_subject(root):
    m = re.match(r'\{(?P<xmlns>.+)\}.+', root.tag)
    xmlns = m.group('xmlns')

    def _(tag):
        return '{%s}%s' % (xmlns, tag)

    patient_info = root.find(_('_subject'))
    pat_id = patient_info.find(_('pat_id')).text
    root.remove(patient_info)

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

def convert_instance(in_node, out_node, root=False):
    name = in_node.tag.split('}')[-1]

    if list(in_node):
        if root:
            group = et.SubElement(out_node, _('FormData'))
            group.attrib['FormOID'] = name
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

if __name__ == "__main__":
    
    parser = OptionParser()
    parser.add_option("-x", "--xform", dest="xform",
                      help="source xform", metavar="FILE")
    parser.add_option("-f", "--crf", dest="crf",
                      help="source CRF", metavar="FILE")

    (options, args) = parser.parse_args()
   
    with open(options.xform or options.crf) as f:
        if options.xform:
            source = et.parse(f).getroot()
        else:
            source = convert_xform(f)

    inst = (sys.stdin if args[0] == '-' else open(args[0]))
    pprintxml(dump_xml(convert_odm(inst, source)))

