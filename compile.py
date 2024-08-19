from setuptools import setup, Extension
from Cython.Build import cythonize

cython_extensions = [
    Extension("resources.utils", ["./resources/utils.py"]),
    Extension("resources.svm", ["./resources/svm.py"]),
    Extension("resources.features", ["./resources/features.py"]),
]

setup(
    name="MyCompiledModules",
    ext_modules=cythonize(cython_extensions, compiler_directives={'language_level': "3"}),
)