"""Every text on screen must exist in both English and Hindi.

Runs the real frontend/js/i18n.js in Node (skipped if Node is not installed) and checks:
- English and Hindi have the same keys;
- every data-i18n key in the HTML pages and every t("...") key in the scripts exists;
- every planner gap code and every server message mapped in api.js has a text.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FRONT = ROOT / "frontend"
NODE = shutil.which("node")

SCRIPT = r"""
const fs = require("fs"), path = require("path");
const dir = process.argv[1];
global.window = {}; global.document = { documentElement: {}, addEventListener() {}, querySelectorAll: () => [] };
global.localStorage = { getItem() { return null; }, setItem() {} };
const src = fs.readFileSync(path.join(dir, "js/names.js"), "utf8") + "\n" + fs.readFileSync(path.join(dir, "js/i18n.js"), "utf8") + "\n;module.exports = { TEXT };";
const m = { exports: {} };
new Function("module", "exports", "require", src)(m, m.exports, require);
console.log(JSON.stringify({ en: Object.keys(m.exports.TEXT.en), hi: Object.keys(m.exports.TEXT.hi) }));
"""


@pytest.fixture(scope="module")
def keys():
    if not NODE:
        pytest.skip("Node.js is not installed")
    out = subprocess.run([NODE, "-e", SCRIPT, str(FRONT)], capture_output=True, text=True, check=True, timeout=60)
    data = json.loads(out.stdout)
    return set(data["en"]), set(data["hi"])


def test_english_and_hindi_have_same_keys(keys):
    en, hi = keys
    assert en - hi == set(), f"missing in Hindi: {sorted(en - hi)}"
    assert hi - en == set(), f"missing in English: {sorted(hi - en)}"


def test_every_used_key_exists(keys):
    en, _ = keys
    used = set()
    for page in FRONT.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        used |= set(re.findall(r'data-i18n(?:-aria|-placeholder|-title)?="([^"]+)"', text))
        used |= set(re.findall(r'data-title-key="([^"]+)"', text))
    for script in (FRONT / "js").glob("*.js"):
        if script.name == "names.js":
            continue
        used |= set(re.findall(r'\btf?\(\s*"([a-z0-9_]+)"', script.read_text(encoding="utf-8")))
    assert used - en == set(), f"texts used but not defined: {sorted(used - en)}"


def test_planner_codes_and_server_messages_have_texts(keys):
    en, _ = keys
    advisor = (ROOT / "backend/app/services/crop_advisor.py").read_text(encoding="utf-8")
    gap_codes = set(re.findall(r'gaps\.add\("([a-z_]+)"', advisor)) | {"district_missing", "season_missing"}
    assert {f"gap_{c}" for c in gap_codes} - en == set()
    for prefix, values in {
        "water_need_": ["high", "medium_high", "medium", "low_medium", "low", "unknown"],
        "rotation_": ["same_group_as_current", "legume_after_non_legume", "different_group", "unknown"],
        "planner_interp_": ["no_farmer_yield", "below_local_benchmark", "near_or_above_local_benchmark", "insufficient_yield_data"],
        "excluded_": ["water_constraint", "high_water_need_caution"],
        "doc_reason_": ["not_leaf_like", "invalid_or_unknown", "low_confidence", "close_call"],
        "st_": ["available", "sold", "expired", "withdrawn"],
    }.items():
        assert {prefix + v for v in values} - en == set(), prefix
    api = (FRONT / "js/api.js").read_text(encoding="utf-8")
    mapped = set(re.findall(r'\["[^"]+", "([a-z0-9_]+)"\]', api))
    assert mapped and mapped - en == set()
