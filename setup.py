#!/usr/bin/env python3
"""Setup script for RTLReportLab.

RTLReportLab is a fork of ReportLab with first-class RTL / BiDi support
(Arabic shaping via arabic-reshaper, bidi reordering via python-bidi),
plus extra flowables such as Grid.

Install from a clone:
    pip install .

Install directly from GitHub:
    pip install git+https://github.com/nafeal3mri/RTLReportLab.git
"""
import os
from setuptools import setup, find_packages

HERE = os.path.abspath(os.path.dirname(__file__))


def _read(name):
    path = os.path.join(HERE, name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    return ""


def _version():
    # Pull __version__ out of the package without importing it
    # (importing would require the runtime deps to be present first).
    init = _read(os.path.join("RTLReportLab", "__init__.py"))
    for line in init.splitlines():
        if line.startswith("Version"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "0.0.0"


long_description = _read("README.md")

setup(
    name="RTLReportLab",
    version=_version(),
    description="ReportLab fork with RTL / BiDi (Arabic) text support and extra flowables.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="nafeal3mri",
    url="https://github.com/nafeal3mri/RTLReportLab",
    project_urls={
        "Source": "https://github.com/nafeal3mri/RTLReportLab",
        "Issues": "https://github.com/nafeal3mri/RTLReportLab/issues",
    },
    license="BSD-3-Clause",
    packages=find_packages(include=["RTLReportLab", "RTLReportLab.*"]),
    include_package_data=True,
    package_data={
        # Ship the bundled fonts and other binary assets inside the wheel.
        "RTLReportLab": [
            "*.txt", "*.xml", "*.dtd", "*.yml", "*.ttf",
            "fonts/*",
            "graphics/**/*",
            "pdfbase/*.txt", "pdfbase/*.xml",
        ],
    },
    python_requires=">=3.9",
    install_requires=[
        "pillow>=10.0.0",
        "python-bidi>=0.4.2",
        "arabic-reshaper>=3.0.0",
        "uharfbuzz>=0.30.0",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Printing",
        "Topic :: Text Processing :: Markup",
        "Topic :: Multimedia :: Graphics",
    ],
    keywords="reportlab pdf rtl bidi arabic reshaper",
    zip_safe=False,
)
