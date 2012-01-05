import sys
from tornado.ioloop import IOLoop
import tornado.web as web
from tornado.httpclient import HTTPError
import threading
import logging
import os
import time
import json
import webservices as ws
from optparse import OptionParser
from urlparse import urlparse, parse_qs
import email
from xforminst_to_odm import process_instance
import util

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger('proxy')
logger.setLevel(logging.DEBUG)

DEFAULT_PORT = 8053
ODK_SUBMIT_PATH = 'submission'

def _async(callback, func):
    try:
        result = func()
        success = True
    except Exception, e:
        logger.exception('exception in handler thread')
        result = '%s %s' % (type(e), str(e))
        success = False

    IOLoop.instance().add_callback(lambda: callback(success, result))

def async(request, func):
    threading.Thread(target=_async, args=[request._respond, func]).start()

class BaseHandler(web.RequestHandler):
    def initialize(self, conn, **kwargs):
        self.conn = conn
        for k, v in kwargs.iteritems():
            setattr(self, k, v)

    @web.asynchronous
    def get(self):
        async(self, lambda: self.handle())

    @web.asynchronous
    def post(self):
        async(self, lambda: self.handle())

    def _success(self, result):
        self.set_header('Content-Type', 'text/json')
        self.write(json.dumps(result))

    def _respond(self, success, result):
        if success:
            self._success(result)
            self.finish()
        else:
            # this doesn't seem to work
            # raise HTTPError(500, result)

            self.set_status(500)
            self.write(result)
            self.finish()

class NeedsScreeningHandler(BaseHandler):
    def handle(self):
        subj_id = self.get_argument('subject_id')
        study_id = self.get_argument('study_id')

        # right now, if patient exists, assume screening form filled out

        # in future, we'd also have to check if the form is complete and on file
        # within a certain historial time window

        # also TODO: cache patient demographic info in memcached

        result = self.conn.lookup_subject(subj_id, study_id)
        return (result is None)

class SubmitHandler(BaseHandler):
    def head(self):
        scheme = self.request.protocol #'http' # will need to support https eventually?
        host = self.request.host

        self.set_status(204)
        self.set_header('Location', '%s://%s/%s' % (scheme, host, ODK_SUBMIT_PATH))
        self.finish()        

    def handle(self):
        content_type = self.request.headers.get('Content-Type')
        payload = self.request.body

        if not content_type.startswith('multipart/form-data'):
            raise HTTPError(500, 'don\'t understand submission content type')

        m = email.message_from_string('Content-Type: %s\n\n%s' % (content_type, payload))
        form_part = [part for part in m.get_payload() if part.get('Content-Disposition').startswith('form-data')][0]
        xfinst = form_part.get_payload()
        logger.debug('received xform submission:\n%s' % util.dump_xml(xfinst, pretty=True))

        resp = process_instance(xfinst, self.xform_path)
        if resp['odm']:
            logger.debug('converted to odm:\n%s' % util.dump_xml(resp['odm'], pretty=True))

            # for now, assume that patient must be created
            self.conn.create_subject(resp['subject_id'], resp['birthdate'], resp['gender'], resp['study_id'])
            event_ix = self.conn.sched_event(resp['subject_id'], resp['studyevent_id'],
                                            resp['location'], resp['start'], resp['end'], resp['study_id'])
            self.conn.submit(resp['odm'])
        
        #TODO: return report url, e.g.
        # /OpenClinica/ClinicalData/html/view/S_CPCS/320999/SE_CPCS[1]/F_CPCS_1?&tabId=1&exitTo=ViewStudySubject
        return 'processed successfully'

    def _success(self, result):
        self.set_status(202)
        self.set_header('Content-Type', 'text/plain')
        self.write(result)
        

class WSDL(object):
    def __init__(self, url, user, password):
        def conn(wsdl):
            return ws.connect(url, wsdl, user, password)

        self.wsdl = {
            'subj': conn(ws.SUBJ_WSDL),
            'se': conn(ws.SE_WSDL),
            'data': conn(ws.DATA_WSDL),
        }

    def _func(self, f, wsdl):
        return lambda *args, **kwargs: f(self.wsdl[wsdl], *args, **kwargs)

    def lookup_subject(self, *args, **kwargs):
        return self._func(ws.lookup_subject, 'subj')(*args, **kwargs)
    def create_subject(self, *args, **kwargs):
        return self._func(ws.create_subject, 'subj')(*args, **kwargs)
    def sched_event(self, *args, **kwargs):
        return self._func(ws.sched, 'se')(*args, **kwargs)
    def submit(self, *args, **kwargs):
        return self._func(ws.submit, 'data')(*args, **kwargs)

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-u", "--user", dest="user",
                      help="SOAP auth username")
    parser.add_option("-p", "--password", dest="password",
                      help="SOAP auth passwordt")
    parser.add_option("-f", "--xform", dest="xform",
                      help="source xform")
    parser.add_option("--port", dest="port", default=DEFAULT_PORT, type='int',
                      help="http listen port")

    (options, args) = parser.parse_args()
    url = args[0]

    conn = WSDL(url, options.user, options.password)

    application = web.Application([
        (r'/needs-screening', NeedsScreeningHandler, {'conn': conn}),
        (r'/%s' % ODK_SUBMIT_PATH, SubmitHandler, {'conn': conn, 'xform_path': options.xform}),
    ])
    application.listen(options.port)
    logging.info('proxy initialized and ready to take requests')

    IOLoop.instance().start()
