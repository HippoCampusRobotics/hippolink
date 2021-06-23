import glob
import os
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py


def generate():
    from src.hippolink.generation import hippogen
    this_files_dir = os.path.dirname(os.path.realpath(__file__))
    rel_path = os.path.join("src", "hippolink", "definitions")
    abs_path = os.path.join(this_files_dir, rel_path)
    if not os.path.exists(abs_path):
        print("Could not find definitions at: '{}'".format(abs_path))
        exit(1)
    xmls = glob.glob(os.path.join(abs_path, "*.xml"))
    messages_dir = os.path.join(this_files_dir, "src", "hippolink")
    for xml in xmls:
        shutil.copy(xml, messages_dir)

    hippogen.generate_python()


class custom_build_py(build_py):
    def run(self):
        generate()
        build_py.run(self)


setup(
    name="hippolink",
    version="0.1",
    license="MIT",
    package_dir={"": "src"},
    packages=["hippolink", "hippolink.generation"],
    package_data={"hippolink": ["*.xml"]},
    # scripts=["scripts/hippogen.py"],
    install_requires=[
        "future",
        "pyserial"
    ],
    setup_requires=[
        "yapf",
    ],
    cmdclass={"build_py": custom_build_py},
)
