#!/usr/bin/env python3
"""Inline an explorer JSON into the explorer template -> standalone HTML page."""
import sys
tpl, data, out = sys.argv[1:4]
html = open(tpl).read()
js = open(data).read().replace("</", "<\\/")
assert "__DATA__" in html
open(out, "w").write(html.replace("__DATA__", js, 1))
print(f"wrote {out}")
