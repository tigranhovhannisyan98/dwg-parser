import itertools
import ezdxf
from collections import Counter

ezdxf.options.load_proxy_graphics = False
ezdxf.options.seed_entity_space = False

doc = ezdxf.readfile("out/MEL_5152_EG_ELT.dxf")
msp = doc.modelspace()

print(doc.dxfversion)
print("TEXT:", len(msp.query("TEXT")))
print("MTEXT:", len(msp.query("MTEXT")))
print("INSERT:", len(msp.query("INSERT")))

# sample 40 block names
ins_q = msp.query("INSERT")
sample_names = {e.dxf.name for e in itertools.islice(ins_q, 40)}
print("Sample block names:", sorted(sample_names))

# top layers for INSERTs (first 10k only to keep it fast)
layer_counts = Counter(e.dxf.layer for e in itertools.islice(msp.query("INSERT"), 10_000))
print("Top INSERT layers:", layer_counts.most_common(15))

# peek a few MTEXT strings
for e in itertools.islice(msp.query("MTEXT"), 8):
    print(repr(e.plain_text()), e.dxf.layer, tuple(e.dxf.insert))

