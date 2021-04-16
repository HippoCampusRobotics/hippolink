from pyhippolink.generation.hippoparse import HippoXml
from pyhippolink.generation import python

if __name__ == "__main__":
    m = HippoXml("definitions/hippolink.xml")
    python.generate([m])