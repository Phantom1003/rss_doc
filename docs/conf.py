# Configuration file for the Sphinx documentation builder.

import os

mode = os.environ.get("SYCURICON_SPHINX_MODE")

# -- Project information

project = 'RISC-V Spike SDK'
copyright = '2023, Sycuricon Group'
author = 'Jinyan Xu'

version = 'latest'
release = version

# -- General configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'sphinx': ('https://www.sphinx-doc.org/en/master/', None),
}
intersphinx_disabled_domains = ['std']

templates_path = ['_templates']

# -- Options for HTML output

html_theme = 'sphinx_rtd_theme'

html_static_path = ['_static']

html_js_files = [
    'js/refresh.js' if mode == "DEBUG" else None,
]

# -- Options for EPUB output
epub_show_urls = 'footnote'
