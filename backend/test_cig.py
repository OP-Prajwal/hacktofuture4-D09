"""Quick smoke test for the CIG engine modules."""

import json

print("=" * 60)
print("CIG ENGINE SMOKE TEST")
print("=" * 60)

# ── Test 1: Language Detector ─────────────────────────────────────────────
print("\n[1] Language Detector...")
from services.cig.language_detector import detect_language, get_parser_type

assert detect_language(".py") == "python"
assert detect_language(".js") == "javascript"
assert detect_language(".ts") == "typescript"
assert detect_language(".tsx") == "typescript"
assert get_parser_type(".py") == "ast"
assert get_parser_type(".js") == "treesitter"
assert get_parser_type(".ts") == "treesitter"
assert get_parser_type(".css") == "generic"
print("   ✓ All assertions passed")

# ── Test 2: Python Parser ────────────────────────────────────────────────
print("\n[2] Python Parser...")
from services.cig.python_parser import parse_python

with open("main.py", "r", encoding="utf-8") as f:
    src = f.read()

result = parse_python(src, "main.py")
print(f"   Functions: {len(result['functions'])}")
print(f"   Classes:   {len(result['classes'])}")
print(f"   Imports:   {len(result['imports'])}")
print(f"   Calls:     {len(result['calls'])}")

assert len(result["functions"]) > 0, "Should find functions in main.py"
assert len(result["imports"]) > 0, "Should find imports in main.py"

# Print first 3 functions
for fn in result["functions"][:3]:
    print(f"   → {fn['name']}({', '.join(fn['params'][:3])}) L{fn['start_line']}-{fn['end_line']}")

# ── Test 3: Python Parser on auth_service.py ─────────────────────────────
print("\n[3] Python Parser (auth_service.py)...")
with open("services/auth_service.py", "r", encoding="utf-8") as f:
    src2 = f.read()

result2 = parse_python(src2, "services/auth_service.py")
print(f"   Functions: {len(result2['functions'])}")
print(f"   Classes:   {len(result2['classes'])}")
print(f"   Imports:   {len(result2['imports'])}")
print(f"   Calls:     {len(result2['calls'])}")

for fn in result2["functions"]:
    print(f"   → {fn['name']}({', '.join(fn['params'][:3])}) L{fn['start_line']}-{fn['end_line']}")

# ── Test 4: Tree-sitter JS Parser ────────────────────────────────────────
print("\n[4] Tree-sitter JS Parser...")
from services.cig.universal_parser import parse_js_ts

js_code = """
import { Command } from 'commander';
import axios from 'axios';
const path = require('path');

const BACKEND_URL = 'http://localhost:8000';

function getConfigPath() {
  return path.join(process.cwd(), '.nexus', 'config.json');
}

const writeConfig = (config) => {
  fs.writeFileSync(getConfigPath(), JSON.stringify(config));
};

class RepoManager extends BaseManager {
  constructor(name) {
    super(name);
    this.name = name;
  }

  async push(files) {
    const result = await axios.post('/push', files);
    return result;
  }
}
"""

result3 = parse_js_ts(js_code, "test.js", ".js")
print(f"   Functions: {len(result3['functions'])}")
print(f"   Classes:   {len(result3['classes'])}")
print(f"   Imports:   {len(result3['imports'])}")
print(f"   Calls:     {len(result3['calls'])}")

for fn in result3["functions"]:
    print(f"   → {fn['name']} (async={fn['is_async']}, method={fn['is_method']}) L{fn['start_line']}-{fn['end_line']}")

for cls in result3["classes"]:
    print(f"   → class {cls['name']} extends {cls['bases']}")

for imp in result3["imports"]:
    print(f"   → import {imp['name']} from '{imp['module']}' ({imp['type']})")

assert len(result3["functions"]) >= 3, f"Expected >=3 functions, got {len(result3['functions'])}"
assert len(result3["classes"]) >= 1, f"Expected >=1 class, got {len(result3['classes'])}"
assert len(result3["imports"]) >= 2, f"Expected >=2 imports, got {len(result3['imports'])}"

# ── Test 5: Symbol Registry ──────────────────────────────────────────────
print("\n[5] Symbol Registry...")
from services.cig.symbol_registry import SymbolRegistry

registry = SymbolRegistry()
registry.register_file("main.py")
registry.register_file("services/auth_service.py")

for fn in result["functions"]:
    registry.register_function(fn)
for fn in result2["functions"]:
    registry.register_function(fn)
for cls in result["classes"]:
    registry.register_class(cls)
for cls in result2["classes"]:
    registry.register_class(cls)

stats = registry.get_stats()
print(f"   {stats}")

# Test lookup
matches = registry.lookup("register_user")
print(f"   lookup('register_user') → {len(matches)} match(es)")
if matches:
    print(f"   → {matches[0].qualified_name}")

# ── Test 6: Resolver ─────────────────────────────────────────────────────
print("\n[6] Resolver...")
from services.cig.resolver import Resolver

registry.register_imports("main.py", result["imports"])
registry.register_imports("services/auth_service.py", result2["imports"])

resolver = Resolver(registry)
resolved = resolver.resolve_all([result, result2])

resolved_calls = [c for c in resolved["calls"] if c.resolved]
total_calls = len(resolved["calls"])
print(f"   Calls:  {len(resolved_calls)}/{total_calls} resolved")
print(f"   Imports: {len([i for i in resolved['imports'] if i.resolved])}/{len(resolved['imports'])} resolved")
print(f"   Extends: {len([e for e in resolved['inheritance'] if e.resolved])}/{len(resolved['inheritance'])} resolved")

# Show some resolved calls
for c in resolved_calls[:5]:
    print(f"   → {c.caller_qualified} CALLS {c.callee_qualified}")

# ── Test 7: Semantic Enricher ────────────────────────────────────────────
print("\n[7] Semantic Enricher...")
from services.cig.semantic_enricher import enrich_function, enrich_class

for fn in result2["functions"][:3]:
    enriched = enrich_function(fn)
    print(f"   → {fn['name']}: tags={fn['tags']}")
    print(f"     summary: {fn['summary'][:80]}")

# ── Done ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("ALL SMOKE TESTS PASSED ✓")
print("=" * 60)
