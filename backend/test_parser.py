"""
Diagnostic script: test _parse_context() against all known LightRAG context formats.
Run from the backend/ directory:  python test_parser.py
"""
import sys
sys.path.insert(0, ".")

from app.services.lightrag_service import _parse_context

# ── Format 1: Old dash + CSV (LightRAG ≤ 1.x) ──
ctx_dash_csv = """-----Entities-----
id,entity,type,description,rank
0,"Transformer","CONCEPT","A neural network architecture",5
1,"Positional Encoding","CONCEPT","Encoding that adds position info",4
-----Relationships-----
id,source,target,description,keywords,weight,rank
0,"Transformer","Positional Encoding","Uses positional encoding","encoding position",0.9,5
-----Sources-----
id,content
0,"The Transformer model dispenses with recurrence..."
"""

# ── Format 2: New bracket + pipe tuples (current Docker image) ──
ctx_bracket_pipe = """[Entities]
("entity"<|>Transformer<|>CONCEPT<|>A neural network architecture<|>5)
("entity"<|>Positional Encoding<|>CONCEPT<|>Adds position info to embeddings<|>4)

[Relationships]
("relationship"<|>Transformer<|>Positional Encoding<|>Uses PE to encode positions<|>encoding,position<|>0.9<|>5)

[Sources]
The Transformer model dispenses with recurrence...
"""

# ── Format 3: XML-wrapped bracket format (some server versions) ──
ctx_xml_wrapped = """<context>
[Entities]
("entity"<|>Transformer<|>CONCEPT<|>Neural network architecture<|>5)
("entity"<|>Attention<|>MECHANISM<|>Self-attention mechanism<|>4)

[Relationships]
("relationship"<|>Transformer<|>Attention<|>Uses attention mechanism<|>attention<|>0.95<|>5)

[Sources]
Source text here...
</context>
"""

# ── Format 4: Single-quoted or backtick-wrapped tuples ──
ctx_single_quote = """[Entities]
('entity'<|>Transformer<|>CONCEPT<|>A model architecture<|>5)

[Relations]
('relationship'<|>Transformer<|>Attention<|>Uses attention<|>attention<|>0.9<|>5)
"""

print("=" * 60)
for label, ctx in [
    ("Dash+CSV (old format)", ctx_dash_csv),
    ("Bracket+pipe (new format)", ctx_bracket_pipe),
    ("XML-wrapped bracket", ctx_xml_wrapped),
    ("Single-quoted / [Relations]", ctx_single_quote),
]:
    entities, rels = _parse_context(ctx)
    ok_e = "OK" if entities else "FAIL"
    ok_r = "OK" if rels else "FAIL"
    print(f"\n{label}")
    print(f"  Entities ({ok_e}): {len(entities)} -> {[e['name'] for e in entities]}")
    print(f"  Relations ({ok_r}): {len(rels)} -> {[(r['source'], r['target']) for r in rels]}")

print("\n" + "=" * 60)
print("If any format shows FAIL, that's the format your LightRAG is using.")
print("Check your backend logs for [DIAG] lines to see the actual format.")
