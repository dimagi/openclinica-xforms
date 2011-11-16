from crf_to_xform import _, dump_xml, pprintxml, convert_xform
from xml.etree import ElementTree as et
import sys
import re
from optparse import OptionParser

def parse_metadata(root):
    m = re.match(r'\{.+/(?P<study>[^/]+)/(?P<mdv>[^/]+)/(?P<studyevent>[^/]+)/?\}(?P<form>.+)', root.tag)
    return [m.group(k) for k in ['study', 'mdv', 'studyevent', 'form']]

def build_submission(root):
    metadata = parse_metadata(root)

    # need to reconcile instance

    #debug
    subject = ('SS_TESTSUBJ', 'test subject')

    odm = et.Element(_('ODM'))
    clindata = et.SubElement(odm, _('ClinicalData'))
    clindata.attrib['StudyOID'] = metadata[0]
    clindata.attrib['MetaDataVersionOID'] = metadata[1]

    subjdata = et.SubElement(clindata, _('SubjectData'))
    subjdata.attrib['SubjectKey'] = subject[0]
    subjdata.attrib[_('StudySubjectID', 'oc')] = subject[1]

    seevtdata = et.SubElement(subjdata, _('StudyEventData'))
    seevtdata.attrib['StudyEventOID'] = metadata[2]

    convert_instance(root, seevtdata, True)

    return odm

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
    print source.tag


    doc = et.parse(f)
    return build_submission(doc.getroot())

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

