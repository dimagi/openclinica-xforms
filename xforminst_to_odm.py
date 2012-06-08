from crf_to_xform import _, convert_xform
from xml.etree import ElementTree as et
import sys
import re
from optparse import OptionParser
from StringIO import StringIO
import util
from datetime import date, datetime, timedelta
import settings
import logging

def parse_xmlns(xmlns):
    m = re.match(r'.+/(?P<study>[^/]+)/(?P<mdv>[^/]+)/(?P<studyevent>[^/]+)/(?P<form>[^/]+)/?', xmlns)
    return dict((k, m.group(k)) for k in ('study', 'mdv', 'studyevent', 'form'))

def parse_metadata(root):
    xmlns, tag = util.split_tag(root.tag)
    info = parse_xmlns(xmlns)

    assert info['form'] == tag

    info['xmlns'] = xmlns
    return info

def build_submission(context, root, ref_instance, reconcile=False):
    metadata = parse_metadata(root)
    resp, unwrap_instance = extract_data(context, root, metadata['xmlns'])

    odm, odm_data_root = odm_scaffold(metadata, resp)
    crf_root = unwrap_instance(ref_instance, reconcile)
    convert_instance(crf_root, odm_data_root, metadata['form'])

    resp.update({
        'odm': odm,
    })
    return resp

def odm_scaffold(metadata, resp):
    odm = et.Element(_('ODM'))
    clindata = et.SubElement(odm, _('ClinicalData'))
    clindata.attrib['StudyOID'] = metadata['study']
    clindata.attrib['MetaDataVersionOID'] = metadata['mdv']

    subjdata = et.SubElement(clindata, _('SubjectData'))
    subjdata.attrib['SubjectKey'] = resp['subject_id']

    seevtdata = et.SubElement(subjdata, _('StudyEventData'))
    seevtdata.attrib['StudyEventOID'] = metadata['studyevent']
    seevtdata.attrib['StudyEventRepeatKey'] = str(resp['event_ordinal'])

    return odm, seevtdata

def extract_data(context, instroot, xmlns):
    def _i(tag):
        return '{%s}%s' % (xmlns, tag)

    data = dict(context)
    data.update({
        'start': datetime.now(), #TODO link to TimeStart
        'end': datetime.now(), #TODO link to TimeEnd
    })

    def unwrap_inst(ref_instance, reconcile):
        def real_inst(root):
            return root #root.find(_i('crf'))
        crf_root = real_inst(instroot)
        trim_instance(crf_root)
        if reconcile:
            if ref_instance is None:
                raise Exception('source xform must be supplied during ODM conversion if using reconciliation mode')
            crf_root = reconcile_instance(crf_root, real_inst(ref_instance))
        return crf_root

    return data, unwrap_inst

#def extract_subject(root, _):
#    patient_info = root.find(_('subject'))
#    return patient_info.find(_('pat_id')).text

#def extract_field(root, nodename, _, mapping=None):
#    val = root.find('.//%s' % _(nodename)).text
#    return mapping[val] if mapping and val is not None else val

def trim_instance(inst_node):
    """remove temporary nodes from instance (starting with '__')"""
    for child in list(inst_node):
        _, tag = util.split_tag(child.tag)
        if tag.startswith('__'):
            inst_node.remove(child)
        else:
            trim_instance(child)

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
        value = (in_node.text or '')
        
        ALLOW_FORCE_COMPLETION = True  # if we allow form to be submitted in incomplete state -- required questions might be blank
        is_required = True # TODO figure out how to pull this from the crf definition; i think currently everything is required so doesn't matter

        if ALLOW_FORCE_COMPLETION and is_required and value == '':
            # strip this answer from the submission or OC will complain about data integrity
            return

        q = et.SubElement(out_node, _('ItemData'))
        q.attrib['ItemOID'] = name
        q.attrib['Value'] = (in_node.text or '')

def convert_odm(context, f, source):
    doc = et.parse(f)
    if source:
        ref_instance = list(source.find('.//%s' % _('instance', 'xf')))[0]
    else:
        ref_instance = None

    return build_submission(context, doc.getroot(), ref_instance)

def process_instance(context, xfinst, xform_path):
    inst = util.strip_namespaces(et.fromstring(xfinst))
    return convert_odm(context, util.xmlfile(xfinst), load_source(xform_path=xform_path))

def load_source(xform_path=None, crf_path=None):
    if not xform_path and not crf_path:
        return None

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
    submission = convert_odm(inst, load_source(options.xform, options.crf))
    print util.dump_xml(submission['odm'], pretty=True)
    del submission['odm']
    util.pprint(submission)

