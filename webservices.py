from suds.client import Client
from suds.wsse import Security, UsernameToken
from suds.sax.text import Raw
from suds.plugin import *
from xml.etree import ElementTree as et
import hashlib
import urlparse
import re
import logging
import util
from contextlib import contextmanager

SUBJ_WSDL = 'ws/studySubject/v1/studySubjectWsdl.wsdl'
SE_WSDL = 'ws/event/v1/eventWsdl.wsdl'
DATA_WSDL = 'ws/data/v1/dataWsdl.wsdl'
STUDY_WSDL = 'ws/study/v1/studyWsdl.wsdl'

class ODMResponsePlugin(MessagePlugin):
    # FML!!!
    def parsed(self, context):
        resp = context.reply.getChild('Envelope').getChild('Body').getChild('createResponse')
        if resp is None:
            # do nothing if payload is not a 'createResponse' type
            return

        result = resp.getChild('result')
        export = resp.getChild('odm')
        resp.remove(export)

        if result.getText().lower() == 'success':
            result.setText(export.getText())
        else:
            result.setText('')

def connect(base_url, wsdl):
    wsdl_url = util.urlconcat(base_url, wsdl)

    logging.info('fetching wsdl %s' % wsdl_url)
    kwargs = {}
    if wsdl == STUDY_WSDL:
        kwargs['plugins'] = [ODMResponsePlugin()]
    client = Client(wsdl_url, **kwargs)

    # this doesn't seem safe...
    endpoint = client.wsdl.services[0].ports[0].location
    if endpoint.startswith('/'):
        endpoint = endpoint[1:]
    if not endpoint.startswith('http'):
        endpoint = util.urlconcat(base_url, endpoint)
    client.set_options(location=endpoint)

    return client

def authenticate(client, (user, passwd)):
    security = Security()
    token = UsernameToken(user, hashlib.sha1(passwd).hexdigest())
    security.tokens.append(token)
    client.set_options(wsse=security)

def lookup_subject(conn, subj_id, study_id):
    subj = conn.factory.create('ns0:studySubjectType')

    subj.label = subj_id
    subj.studyRef = conn.factory.create('ns0:studyRefType')
    subj.studyRef.identifier = study_id

    # suds chokes on the valid response for this service, so dig into the
    # raw xml response instead
    with raw_xml(conn):
        resp = conn.service.isStudySubject(subj)
    root = et.fromstring(resp)
    xmlns = urlparse.urljoin('http://openclinica.org/', conn.wsdl.services[0].ports[0].location[1:])
    result = root.findall('.//{%s}result' % xmlns)[0].text

    if result.lower() == 'success':
        return {'x': 'x'}
    else:
        return None

def create_subject(conn, subj_id, enrolled_on, birthdate, gender, name, study_id):
    subj = conn.factory.create('ns0:studySubjectType')

    subj.label = subj_id
    subj.secondaryLabel = name
    subj.enrollmentDate = enrolled_on.strftime('%Y-%m-%d')
    subj.subject = conn.factory.create('ns0:subjectType')
    subj.subject.uniqueIdentifier = subj_id
    subj.subject.dateOfBirth = birthdate.strftime('%Y-%m-%d')  # don't care about collecting dob
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

def submit(conn, instnode):
    odm_raw = util.dump_xml(util.strip_namespaces(instnode))

    resp = getattr(conn.service, 'import')(Raw(odm_raw))
    if resp.result.lower() != 'success':
        raise Exception([str(e) for e in resp.error])

def study_export(conn, study_name):
    study = conn.factory.create('ns0:siteRefType')
    study.identifier = 'default-study'

    resp = conn.service.getMetadata(study)
    if resp.result:
        # debugging
        with open('/tmp/exportdump', 'w') as f:
            f.write(resp.result)
        return et.fromstring(resp.result)
    else:
        return None

def list_studies(conn):
    resp = conn.service.listAll()
    if resp.result.lower() == 'success':
        def get_study(s):
            data = s[1][0]
            return {'identifier': data.identifier, 'oid': data.oid, 'name': data.name}
        return [get_study(s) for s in resp.studies]
    else:
        return None

@contextmanager
def raw_xml(conn):
    conn.set_options(retxml=True)
    yield
    conn.set_options(retxml=False)


def init_logging():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('suds.client').setLevel(logging.DEBUG)
    logging.getLogger('suds.transport').setLevel(logging.DEBUG)
    logging.getLogger('suds.xsd.schema').setLevel(logging.DEBUG)
    logging.getLogger('suds.wsdl').setLevel(logging.DEBUG)
#init_logging()

if __name__ == "__main__":
    
    SOAP_URL = 'https://jikan.eclinicalhosting.com/OpenClinica-test-ws/'
    USER = 'root'
    PASS = 'password'
    STUDY = 'default-study'

    init_logging()

    def auth(conn):
        authenticate(conn, (USER, PASS))
        return conn

    conn = auth(connect(SOAP_URL, STUDY_WSDL))

    print list_studies(conn)

    """
    import random
    from datetime import datetime, date, timedelta

#    SUBJ = 'K%06d' % random.randint(0, 999999)
    SUBJ = '10175'

    conn = auth(connect(SOAP_URL, SUBJ_WSDL))
#    print lookup_subject(conn, SUBJ, 'CPCS')
    create_subject(conn, SUBJ, date.today(), 'f', 'mike', 'CPCS')

    conn = auth(connect(SOAP_URL, SE_WSDL))
    offset = timedelta(hours=1)
    event_num = sched(conn, SUBJ, 'SE_CPCS', 'burgdorf', datetime.now() - timedelta(minutes=5) + offset, datetime.now() + offset, 'CPCS')

    conn = auth(connect(SOAP_URL, DATA_WSDL))
    with open('/home/drew/tmp/crfinst.xml') as f:
        submit(conn, et.parse(f).getroot())
"""
