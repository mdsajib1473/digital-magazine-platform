"""
URL path converters for the magazines app.

Django's stock ``<slug:>`` converter is hardcoded to ASCII (regex
``[-a-zA-Z0-9_]+``), which silently fails to match the unicode slugs
produced by ``slugify(..., allow_unicode=True)``. This module registers
a permissive ``<uslug:>`` converter that accepts any unicode word
characters plus dashes, matching the SlugField(allow_unicode=True)
output format exactly.
"""
from django.urls import register_converter


class UnicodeSlugConverter:
    """Path converter for unicode slugs.

    In Python 3, ``\\w`` in a re pattern is unicode-aware by default,
    so this regex matches Bengali / CJK / Latin / digit characters
    plus the hyphen separator that slugify inserts between words.
    """

    regex = r"[-\w]+"

    def to_python(self, value: str) -> str:
        return value

    def to_url(self, value: str) -> str:
        return value


register_converter(UnicodeSlugConverter, "uslug")
