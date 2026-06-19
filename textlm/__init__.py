"""textlm - a generic text-LM project built on lloom.

The project-specific layer that lloom deliberately leaves out: data prep
(textlm.prep) and SFT prompt/response templating (textlm.sft). Kept minimal so
you can adapt it to any corpus - swap these two modules and the configs; the
scripts and lloom stay as-is.
"""
__version__ = "0.1.0"
