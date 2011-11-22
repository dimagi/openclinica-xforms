from suds.client import Client
from suds.wsse import Security, UsernameToken
import hashlib
import urlparse

SOAP_URL = 'https://64.119.157.114:8070/OpenClinica-ws/'
SE_WSDL = 'ws/studySubject/v1/studySubjectWsdl.wsdl'

USER = 'droos'
PASS = 'password'

import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('suds.client').setLevel(logging.DEBUG)
logging.getLogger('suds.transport').setLevel(logging.DEBUG)
logging.getLogger('suds.xsd.schema').setLevel(logging.DEBUG)
logging.getLogger('suds.wsdl').setLevel(logging.DEBUG)

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

if __name__ == "__main__":

    from datetime import date

    conn = connect(SOAP_URL, SE_WSDL, USER, PASS)

    create_subject(conn, 'WSSUBJ57', date.today(), 'f', 'CPCS')