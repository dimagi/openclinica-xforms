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

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

DEFAULT_PORT = 8053

def _async(callback, func):
    try:
        result = func()
        success = True
    except Exception, e:
        result = '%s %s' % (type(e), str(e))
        success = False

    IOLoop.instance().add_callback(lambda: callback(success, result))

def async(request, func):
    threading.Thread(target=_async, args=[request._respond, func]).start()

class SimpleSOAPHandler(web.RequestHandler):
    def initialize(self, conn):
        self.conn = conn

    @web.asynchronous
    def get(self):
        async(self, self.handle())

    def _respond(self, success, result):
        if success:
            self.set_header('Content-Type', 'text/json')
            self.write(json.dumps(result))
            self.finish()
        else:
            # this doesn't seem to work
            raise HTTPError(500, result)

class LookupSubjectHandler(SimpleSOAPHandler):
    def handle(self):
        subj_id = self.get_argument('subject_id')
        study_id = self.get_argument('study_id')
        return lambda: self.conn.lookup_subject(subj_id, study_id)


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
    parser.add_option("--port", dest="port", default=DEFAULT_PORT, type='int',
                      help="http listen port")

    (options, args) = parser.parse_args()
    url = args[0]

    conn = WSDL(url, options.user, options.password)

    application = web.Application([
        (r'/lookup', LookupSubjectHandler, {'conn': conn}),
    ])
    application.listen(options.port)
    IOLoop.instance().start()

"""
#needs screening:

given: patid

return whether pat e
"""
