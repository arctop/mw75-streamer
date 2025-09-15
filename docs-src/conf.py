"""Sphinx configuration file for MW75 EEG Streamer documentation."""

import os
import sys

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath('..'))

# Project information
project = 'MW75 EEG Streamer'
author = 'Arctop'
copyright = '2025, Arctop'
release = '1.0.2'
version = '1.0.2'

# Extensions
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx_autodoc_typehints',
    'myst_parser',
]

# Napoleon settings (for Google/NumPy docstring styles)
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# Autodoc settings
autodoc_member_order = 'bysource'
autodoc_typehints = 'description'
autodoc_typehints_description_target = 'documented'
autosummary_generate = True

# Define which members to exclude by default
autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'show-inheritance': True,
    'exclude-members': (
        # Exclude PyObjC/NSObject internal methods
        'bundleForClass,isNSArray__,isNSCFConstantString__,isNSData__,isNSDate__,'
        'isNSDictionary__,isNSNumber__,isNSObject__,isNSOrderedSet__,isNSSet__,'
        'isNSString__,isNSTimeZone__,isNSURL__,isNSValue__,'
        'newTaggedNSStringWithASCIIBytes__length__,'
        'swiftui_addRenderedSubview_positioned_relativeTo_,'
        'swiftui_insertRenderedSubview_atIndex_,'
        'CA_interpolateValues___interpolator_'
    )
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The theme to use for HTML and HTML Help pages
html_theme = 'sphinx_rtd_theme'

# Theme options
html_theme_options = {
    'canonical_url': 'https://arctop.github.io/mw75-streamer/',
    'analytics_id': '',
    'prev_next_buttons_location': 'bottom',
    'style_external_links': False,
    'vcs_pageview_mode': '',
    'style_nav_header_background': '#667eea',
    'collapse_navigation': False,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'includehidden': True,
    'titles_only': False
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Custom CSS files
html_css_files = [
    'custom.css',
]

# The master toctree document.
master_doc = 'index'

# HTML output options
html_title = f'{project} Documentation'
html_short_title = project
html_logo = None
html_favicon = '../docs/favicon.svg'

# Output file base name for HTML help builder.
htmlhelp_basename = 'MW75EEGStreamerdoc'

# Intersphinx mapping
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'bleak': ('https://bleak.readthedocs.io/en/latest/', None),
}

# Source file suffixes
source_suffix = {
    '.rst': None,
    '.md': 'myst_parser.sphinx_',
}

# MyST settings
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "linkify",
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist",
]

def autodoc_skip_member(app, what, name, obj, skip, options):
    """Skip PyObjC/NSObject internal methods and other irrelevant members"""
    # Skip PyObjC/NSObject internal methods
    pyobjc_methods = {
        'bundleForClass', 'isNSArray__', 'isNSCFConstantString__', 'isNSData__',
        'isNSDate__', 'isNSDictionary__', 'isNSNumber__', 'isNSObject__',
        'isNSOrderedSet__', 'isNSSet__', 'isNSString__', 'isNSTimeZone__',
        'isNSURL__', 'isNSValue__', 'newTaggedNSStringWithASCIIBytes__length__',
        'swiftui_addRenderedSubview_positioned_relativeTo_',
        'swiftui_insertRenderedSubview_atIndex_', 'CA_interpolateValues___interpolator_'
    }

    if name in pyobjc_methods:
        return True

    # Skip methods starting with common PyObjC patterns
    if name.startswith(('isNS', 'CA_', 'swiftui_', '_objc_')):
        return True

    return skip

def setup(app):
    app.connect('autodoc-skip-member', autodoc_skip_member)
