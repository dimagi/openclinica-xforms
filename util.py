import re
from xml.etree import ElementTree as et
from StringIO import StringIO
import urlparse
import base64

def strip_namespaces(node):
    node.tag = split_tag(node.tag)[1]
    for child in node:
        strip_namespaces(child)
    return node

def dump_xml(xml, pretty=False):
    datatype = 'str' if isinstance(xml, type('')) else 'dom'

    if pretty:
        if datatype == 'dom':
            xml = dump_xml(xml)

        from lxml import etree as lx
        return lx.tostring(lx.fromstring(xml), pretty_print=True)
    else:
        if datatype == 'dom':
            tree = et.ElementTree(xml)
            out = StringIO()
            tree.write(out, encoding='utf-8')
            return out.getvalue()
        else:
            return xml

def split_tag(tag):
    m = re.match(r'\{(?P<xmlns>.+)\}(?P<tag>.+)', tag)
    return (m.group('xmlns'), m.group('tag'))

def pprint(o):
    def convert(o):
        if hasattr(o, '__iter__'):
            if hasattr(o, '_asdict'):
                return convert(o._asdict())
            elif hasattr(o, 'iteritems'):
                return dict((k, convert(v)) for k, v in o.iteritems())
            else:
                return [convert(e) for e in o]
        elif hasattr(o, '__dict__'):
            return convert(o.__dict__)
        else:
            return o

    import pprint
    pp = pprint.PrettyPrinter(indent=2)
    pp.pprint(convert(o))

def xmlfile(xmlstr):
    f = StringIO()
    f.write(xmlstr)
    f.seek(0)
    return f

def oid_prefix(type):
    return {
        'study': 'S',
        'studyevent': 'SE',
        'subj': 'SS',
    }[type]

def make_oid(id, type):
    return '%s_%s' % (oid_prefix(type), id)

def strip_oid(id, type):
    prefix = '%s_' % oid_prefix(type)
    assert id.startswith(prefix)
    return id[len(prefix):]

def urlconcat(base, tail):
    if not base.endswith('/'):
        base += '/'
    return urlparse.urljoin(base, tail)

def basic_auth(handler_method):
    def require_basic_auth(handler):
        auth_header = handler.request.headers.get('Authorization')
        if auth_header is None or not auth_header.startswith('Basic '):
            return None
        else:
            return base64.decodestring(auth_header[6:]).split(':', 2)

    def auth_wrapper(handler, *args, **kwargs):
        auth = require_basic_auth(handler)
        if auth is None:
            handler.set_status(401)
            handler.set_header('WWW-Authenticate', 'Basic realm=Restricted')
            handler.finish()
        else:
            kwargs['auth_user'], kwargs['auth_pass'] = auth
            handler_method(handler, *args, **kwargs)

    return auth_wrapper
