#!/usr/bin/env python3
"""Assemble index.html from head.part + body.part + engines + app.part.

index.html is GENERATED. Edit the .part files, never the output.
"""
import re
prev = open("index.html").read()
engine = re.search(r"const TAX_2026=[\s\S]*?function guardrails\(p,cfg\)\{[\s\S]*?return w;\}", prev).group(0) + "\n"
proj = open("web/projection.js").read()
# strip the node export line from the projection port
proj = proj[:proj.index('if(typeof module!=="undefined"')]

HEAD = open("head.part").read()
BODY = open("body.part").read()
APP  = open("app.part").read()

out = HEAD + BODY + "\n<script>\n/* ENGINE — ported from Python reference, parity-verified in CI */\n" \
    + engine + "\n" + proj + "\n" + APP + "\n</script>\n</body>\n</html>\n"
open("index.html","w").write(out)
print("built index.html:", len(out), "chars")
