import sys
from tornado.ioloop import IOLoop
import tornado.web as web
from tornado.httpclient import HTTPError
from tornado.template import Template
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
from datetime import datetime, date
import os.path

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger('proxy')
logger.setLevel(logging.DEBUG)

DEFAULT_PORT = 8053
DEFAULT_SSL_CERT = os.path.join(os.path.dirname(__file__), 'ssl/debug.crt')
ODK_SUBMIT_PATH = 'submission'

class AuthenticationFailed(Exception):
    pass

def _async(callback, func):
    try:
        result = func()
        success = True
    except AuthenticationFailed:
        result = 'auth failed'
        success = False
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

    @util.basic_auth
    @web.asynchronous
    def get(self, auth_user, auth_pass):
        async(self, lambda: self.handle((auth_user, auth_pass)))

    @util.basic_auth
    @web.asynchronous
    def post(self, auth_user, auth_pass):
        async(self, lambda: self.handle((auth_user, auth_pass)))

    def _success(self, result):
        self.set_header('Content-Type', 'text/json')
        self.write(json.dumps(result))

    def _respond(self, success, result):
        if success:
            self._success(result)
            self.finish()
        else:
            if result == 'auth failed':
                self.set_status(401)
            else:
                # this doesn't seem to work
                # raise HTTPError(500, result)
                self.set_status(500)
            self.write(result)
            self.finish()

class RetrieveScreeningHandler(BaseHandler):
    def handle(self, auth):
        subj_id = self.get_argument('subject_id')
        study_id = self.get_argument('study_id')

        # right now, if patient exists, assume screening form filled out

        # in future, we'd also have to check if the form is complete and on file
        # within a certain historial time window

        # also TODO: cache patient demographic info in memcached

        result = self.conn.lookup_subject(auth, subj_id, study_id)
        if result is not None:
            # study event and ordinal are hard-coded for now
            url = report_url(self.conn.base_url, study_id=study_id, subject_id=subj_id, studyevent_id='SE_CPCS', event_ix=1)
        else:
            url = None

        return {'url': url}

class SubmitHandler(BaseHandler):
    def head(self):
        scheme = self.request.protocol #'http' # will need to support https eventually?
        host = self.request.host

        self.set_status(204)
        self.set_header('Location', '%s://%s/%s' % (scheme, host, ODK_SUBMIT_PATH))
        self.finish()

    def handle(self, auth):
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
            self.conn.create_subject(auth, resp['subject_id'], date.today(), resp['gender'], resp['name'], resp['study_id'])
            event_ix = self.conn.sched_event(auth, resp['subject_id'], resp['studyevent_id'],
                                            resp['location'], resp['start'], resp['end'], resp['study_id'])
            self.conn.submit(auth, resp['odm'])

            resp.update({'event_ix': event_ix})
            return report_url(self.conn.base_url, **resp)

    def _success(self, result):
        self.set_status(202)
        self.set_header('Content-Type', 'text/plain')
        self.write(result)

def report_url(base_url, **kwargs):
    kwargs.update({
        'study_oid': util.make_oid(kwargs['study_id'], 'study'),
        'subj_oid': util.make_oid(kwargs['subject_id'], 'subj'),
        'form_id': 'F_CPCS_RESULTS_1', # i can't find a way to not hard-code this at the moment
    })
    url_root = 'OpenClinica'.join(base_url.split('OpenClinica-ws'))
    url_rel = 'ClinicalData/html/view/%(study_oid)s/%(subj_oid)s/%(studyevent_id)s[%(event_ix)d]/%(form_id)s?&tabId=1' % kwargs
    return util.urlconcat(url_root, url_rel)



class DashboardHandler(web.RequestHandler):
    def initialize(self, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)

    def get(self):
        t = Template("""
<html>
<head>
<title>proxy dashboard</title>
</head>
<body>
<style>body{font-family: sans-serif;}</style>
<h1>ODK-UCONN&mdash;OpenClinica Proxy</h1>
<p>It's up! (since {{ boot.strftime('%Y-%m-%d %H:%M:%S UTC') }})</p>
{% if dev_mode %}
<p>Running in <b>development mode</b> using <b>{{ {'http': 'unencrypted http', 'https': 'secure http', 'https-debug': 'debug https (not secure)'}[encryption] }}</b></p>
{% end %}
WSDLs loaded:
<ul>
{% for wsdl in wsdls %}
<li>{{ wsdl }}</li>
{% end %}
</ul>
</body>
</html>
""")

        wsdls = sorted([v.options.location for k, v in self.conn.wsdl.iteritems()])

        self.set_status(200)
        self.set_header('Content-Type', 'text/html')
        self.write(t.generate(**{
            'wsdls': wsdls,
            'boot': self.boot,
            'dev_mode': self.dev_mode,
            'encryption': ('https-debug' if ssl_opts['certfile'] == DEFAULT_SSL_CERT else 'https') if ssl_opts else 'http',
        }))
        
        

class WSDL(object):
    def __init__(self, url):
        def conn(wsdl):
            return ws.connect(url, wsdl)

        self.base_url = url
        self.wsdl = {
            'subj': conn(ws.SUBJ_WSDL),
            'se': conn(ws.SE_WSDL),
            'data': conn(ws.DATA_WSDL),
        }

    def _func(self, f, wsdl, auth):
        conn = self.wsdl[wsdl]
        ws.authenticate(conn, auth)

        def _exec(*args, **kwargs):
            try:
                return f(self.wsdl[wsdl], *args, **kwargs)
            except Exception, e:
                msg = str(e).lower()
                if 'authentication' in msg and 'failed' in msg: #ghetto
                    raise AuthenticationFailed()
                else:
                    raise
        return _exec

    def lookup_subject(self, auth, *args, **kwargs):
        return self._func(ws.lookup_subject, 'subj', auth)(*args, **kwargs)
    def create_subject(self, auth, *args, **kwargs):
        return self._func(ws.create_subject, 'subj', auth)(*args, **kwargs)
    def sched_event(self, auth, *args, **kwargs):
        return self._func(ws.sched, 'se', auth)(*args, **kwargs)
    def submit(self, auth, *args, **kwargs):
        return self._func(ws.submit, 'data', auth)(*args, **kwargs)

def validate_ssl(certfile, dev_mode):
    if certfile == '-':
        # http only
        if dev_mode:
            logging.warn('using UNENCRYPTED HTTP')
            return None
        else:
            raise Exception('unencrypted http can only be used in development mode (--dev)')

    if not os.path.isfile(certfile):
        raise Exception('%s is not a file' % os.path.abspath(certfile))

    if os.path.samefile(certfile, DEFAULT_SSL_CERT):
        if dev_mode:
            certfile = DEFAULT_SSL_CERT # make paths match exactly
            logging.warn('using the debug ssl certificate, which is NOT SECURE')
        else:
            raise Exception('the debug certificate can only be used in development mode (--dev); it is not secure')

    return {
        'certfile': certfile,
    }

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-f", "--xform", dest="xform",
                      help="source xform")
    parser.add_option("--port", dest="port", default=DEFAULT_PORT, type='int',
                      help="http listen port")
    parser.add_option("--dev", dest="dev_mode", action="store_true",
                      help="enable dev mode")
    parser.add_option("--sslcert", dest="sslcert", default=DEFAULT_SSL_CERT,
                      help="path of ssl certificate for https; '-' to use only http")

    (options, args) = parser.parse_args()
    url = args[0]
    ssl_opts = validate_ssl(options.sslcert, options.dev_mode)

    conn = WSDL(url)

    application = web.Application([
        (r'/', DashboardHandler, {
            'conn': conn,
            'boot': datetime.utcnow(),
            'dev_mode': options.dev_mode,
            'encryption': ssl_opts,
        }),
        (r'/screening-report', RetrieveScreeningHandler, {'conn': conn}),
        (r'/%s' % ODK_SUBMIT_PATH, SubmitHandler, {'conn': conn, 'xform_path': options.xform}),
    ])
    application.listen(options.port, ssl_options=ssl_opts)
    logging.info('proxy initialized and ready to take requests')

    IOLoop.instance().start()
