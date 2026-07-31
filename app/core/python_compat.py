import sys


def validate_python_version():
    if sys.version_info < (3, 10):
        raise RuntimeError("Python minimum version is 3.10")

