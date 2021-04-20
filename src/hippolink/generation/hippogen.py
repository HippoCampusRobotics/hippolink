from . import hippoparse
from . import hippogen_python

import os


def generate_python():
    this_files_dir = os.path.dirname(os.path.realpath(__file__))
    def_path = os.path.join(this_files_dir, "..", "definitions")
    xml_path = os.path.join(def_path, "hippolink.xml")
    messages_dir = os.path.join(this_files_dir, "..")
    m = hippoparse.HippoXml(xml_path)
    hippogen_python.generate([m], os.path.join(messages_dir, "msgs.py"))
