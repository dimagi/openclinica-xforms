import re
from xml.etree import ElementTree as et
from StringIO import StringIO

def strip_namespaces(f_inst):
    def strip_ns(node):
        node.tag = split_tag(node.tag)[1]
        for child in node:
            strip_ns(child)

    root = et.parse(f_inst).getroot()
    strip_ns(root)
    return root

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

