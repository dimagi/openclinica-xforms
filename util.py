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

def dump_xml(root):
    tree = et.ElementTree(root)
    out = StringIO()
    tree.write(out, encoding='utf-8')
    return out.getvalue()

def split_tag(tag):
    m = re.match(r'\{(?P<xmlns>.+)\}(?P<tag>.+)', tag)
    return (m.group('xmlns'), m.group('tag'))
