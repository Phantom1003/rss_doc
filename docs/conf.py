# Configuration file for the Sphinx documentation builder.

import os
import sys

mode = os.environ.get("SYCURICON_SPHINX_MODE")
sys.path.append(os.path.abspath("./_ext"))

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
    # custom extensions
    'pdfview',
    'sphinxcontrib.bibtex',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'sphinx': ('https://www.sphinx-doc.org/en/master/', None),
}
intersphinx_disabled_domains = ['std']

templates_path = ['_templates']

# -- Options for Extensions

numfig = True
bibtex_bibfiles = ['refs.bib']

# -- Options for HTML output

html_theme = 'sphinx_nefertiti'

html_theme_options = {
    "style": "blue",
    "documentation_font": "Open Sans",
    "monospace_font": "Ubuntu Mono",
    "monospace_font_size": "1.1rem",
    "repository_url": "https://github.com/sycuricon/riscv-spike-sdk",
    "repository_name": "RSS SDK",
}

html_static_path = ['_static']

html_js_files = [
]

html_css_files = [
    "css/table.css",
]

if mode == "DEBUG":
    html_css_files.append('css/refresh.css')
    html_js_files.append('js/refresh.js')

# -- Options for EPUB output
epub_show_urls = 'footnote'

# -- Options for LaTeX output
latex_engine = 'xelatex'
