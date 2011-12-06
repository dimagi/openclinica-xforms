from suds.client import Client
from suds.wsse import Security, UsernameToken
from suds.sax.text import Raw
from xml.etree import ElementTree as et
import hashlib
import urlparse
import re
from crf_to_xform import dump_xml
import logging

SUBJ_WSDL = 'ws/studySubject/v1/studySubjectWsdl.wsdl'
SE_WSDL = 'ws/event/v1/eventWsdl.wsdl'
DATA_WSDL = 'ws/data/v1/dataWsdl.wsdl'

def connect(base_url, wsdl, user, passwd):
    client = Client(urlparse.urljoin(base_url, wsdl))

    # this doesn't seem safe...
    endpoint = client.wsdl.services[0].ports[0].location[1:] # trim leading slash
    client.set_options(location=urlparse.urljoin(base_url, endpoint))

    if user and passwd:
        security = Security()
        token = UsernameToken(user, hashlib.sha1(passwd).hexdigest())
        security.tokens.append(token)
        client.set_options(wsse=security)

    return client

def lookup_subject(conn, subj_id, study_id):
    subj = conn.factory.create('ns0:studySubjectType')

    subj.label = subj_id
    subj.studyRef = conn.factory.create('ns0:studyRefType')
    subj.studyRef.identifier = study_id

    # suds chokes on the valid response for this service, so dig into the
    # raw xml response instead
    conn.set_options(retxml=True)
    resp = conn.service.isStudySubject(subj)
    root = et.fromstring(resp)
    xmlns = urlparse.urljoin('http://openclinica.org/', conn.wsdl.services[0].ports[0].location[1:])
    result = root.findall('.//{%s}result' % xmlns)[0].text

    if result.lower() == 'success':
        return {'x': 'x'}
    else:
        return None

def create_subject(conn, subj_id, enrolled_on, gender, study_id):
    subj = conn.factory.create('ns0:studySubjectType')

    subj.label = subj_id
    subj.enrollmentDate = enrolled_on.strftime('%Y-%m-%d')
    subj.subject = conn.factory.create('ns0:subjectType')
    subj.subject.uniqueIdentifier = subj_id
    #subject dob?
    subj.subject.gender = gender
    subj.studyRef = conn.factory.create('ns0:studyRefType')
    subj.studyRef.identifier = study_id

    resp = conn.service.create([subj])
    if resp.result.lower() != 'success':
        raise Exception([str(e) for e in resp.error])

def sched(conn, subj_id, event_type_oid, location, start, end, study_id):
    evt = conn.factory.create('ns0:eventType')

    evt.studySubjectRef = conn.factory.create('ns0:studySubjectRefType')
    evt.studySubjectRef.label = subj_id
    evt.studyRef = conn.factory.create('ns0:studyRefType')
    evt.studyRef.identifier = study_id
    evt.eventDefinitionOID = event_type_oid
    evt.startDate = start.strftime('%Y-%m-%d')
    evt.startTime = start.strftime('%H:%M')
    evt.endDate = end.strftime('%Y-%m-%d')
    evt.endTime = end.strftime('%H:%M')
    evt.location = location

    resp = conn.service.schedule([evt])
    if resp.result.lower() != 'success':
        raise Exception([str(e) for e in resp.error])
    return int(resp.studyEventOrdinal)

def submit(conn, f_inst):
    odm_raw = dump_xml(strip_namespaces(f_inst))

    resp = getattr(conn.service, 'import')(Raw(odm_raw))
    if resp.result.lower() != 'success':
        raise Exception([str(e) for e in resp.error])



def strip_namespaces(f_inst):
    def tag(qname):
        m = re.match(r'\{.+\}(?P<tag>.+)', qname)
        return m.group('tag')

    def strip_ns(node):
        node.tag = tag(node.tag)
        for child in node:
            strip_ns(child)

    root = et.parse(f_inst).getroot()
    strip_ns(root)
    return root



def init_logging():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('suds.client').setLevel(logging.DEBUG)
    logging.getLogger('suds.transport').setLevel(logging.DEBUG)
    logging.getLogger('suds.xsd.schema').setLevel(logging.DEBUG)
    logging.getLogger('suds.wsdl').setLevel(logging.DEBUG)

if __name__ == "__main__":
    
    SOAP_URL = 'https://64.119.157.114:8070/OpenClinica-ws/'
    USER = 'droos'
    PASS = 'password'

    init_logging()

    import random
    from datetime import datetime, date, timedelta

    SUBJ = 'K%06d' % random.randint(0, 999999)
#    SUBJ = 'K464347'

    conn = connect(SOAP_URL, SUBJ_WSDL, USER, PASS)
    print lookup_subject(conn, SUBJ, 'CPCS')
#    create_subject(conn, SUBJ, date.today(), 'f', 'CPCS')

#    conn = connect(SOAP_URL, SE_WSDL, USER, PASS)
#    offset = timedelta(hours=1)
#    event_num = sched(conn, SUBJ, 'SE_CPCS', 'burgdorf', datetime.now() - timedelta(minutes=5) + offset, datetime.now() + offset, 'CPCS')

#    conn = connect(SOAP_URL, DATA_WSDL, USER, PASS)
#    with open('/home/drew/tmp/crfinst.xml') as f:
#        submit(conn, f)

