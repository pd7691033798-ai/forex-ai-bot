from setuptools import setup
import pybind11
from pybind11.setup_helpers import Pybind11Extension, build_ext

ext_modules = [
    Pybind11Extension(
        "hft_core",
        ["hft_engine.cpp"],
        include_dirs=[pybind11.get_include()],
        extra_compile_args=["-O3", "-std=c++20", "-pthread"],
    ),
]

setup(
    name="hft_core",
    version="1.0.0",
    description="C++ High-Performance Trading Core for Python",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
)
