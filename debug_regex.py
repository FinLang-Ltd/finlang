import pandas as pd
import re
import sys
from finlang.engine.finlang_engine_v0_6_4 import _wildcard_to_regex, get_condition_mask

print(f"Python Version: {sys.version}")
print(f"Pandas Version: {pd.__version__}")

# 1. Check if the code update is actually live
raw_pattern = "*MARKS*SPENCER*"
regex = _wildcard_to_regex(raw_pattern)

print(f"\n--- Code Update Check ---")
print(f"Pattern: '{raw_pattern}'")
print(f"Result Type: {type(regex)}")
print(f"Result Value: {regex}")

if isinstance(regex, re.Pattern):
    print("❌ FAIL: You are running the OLD code (returns compiled object).")
    print("   Action: Save finlang_engine_v0_6_4.py and run 'pip install -e .' again.")
    sys.exit(1)
elif "(?s)" in regex:
    print("✅ PASS: You are running the NEW code (returns string with inline flags).")
else:
    print("⚠️ WARNING: Code is modified but might be missing '(?s)'.")

# 2. Test the Match Logic
print(f"\n--- Logic Check ---")
data_val = "M&S MARKS AND SPENCER LONDON"
df = pd.DataFrame({"counterparty": [data_val]})
cache = {}

# We simulate exactly what the engine does
mask = get_condition_mask(f'counterparty ~ "{raw_pattern}"', df, cache)
matched = mask.iloc[0]

print(f"Data: '{data_val}'")
print(f"Regex Used: '{regex}'")
print(f"Matched? {matched}")

if matched:
    print("✅ LOGIC WORKS. The issue was likely a previous caching/install glitch.")
else:
    print("❌ LOGIC FAILS. The regex is valid but does not match the data.")