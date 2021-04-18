if __name__ == "__main__":
    from os import sys, path
    sys.path.insert(
        0, path.dirname(path.dirname(path.dirname(path.abspath(__file__)))))
    from hippolink.generation import hippogen
    hippogen.generate_python()
