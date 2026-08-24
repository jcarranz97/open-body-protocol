"""Naming rules, checked off-target. Run: python3 tests/test_naming.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "host"))
from obp.naming import MAX_LEN, mcp_tool_name, sanitise  # noqa: E402

LEGAL = __import__("re").compile(r"^[a-zA-Z0-9_-]{1,64}$")
fails = 0


def check(cond, msg):
    global fails
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        fails += 1


print("the ordinary case")
n = mcp_tool_name("pico-3f5022", "set_brightness")
check(n == "pico-3f5022__set_brightness", f"{n}")
check(LEGAL.match(n) is not None, "matches the MCP name grammar")

print("illegal characters are replaced, not dropped")
check(sanitise("body.with.dots") == "body_with_dots", "dots become underscores")
check(mcp_tool_name("a.b", "c d") == "a_b__c_d", "both parts sanitised")

print("determinism")
a = mcp_tool_name("x" * 80, "wave")
b = mcp_tool_name("x" * 80, "wave")
check(a == b, "same input, same output")

print("the budget")
long_id, verb = "a-very-long-body-identifier-" * 3, "walk_forward"
n = mcp_tool_name(long_id, verb)
check(len(n) <= MAX_LEN, f"truncated to {len(n)} chars")
check(LEGAL.match(n) is not None, "still legal after truncation")
check(n.endswith(tuple("0123456789abcdef")), "ends in a hash")
check(verb in n, "the verb survives truncation intact")

print("collisions after truncation")
x = mcp_tool_name("body-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-1", "walk")
y = mcp_tool_name("body-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-2", "walk")
check(x != y, "two bodies sharing a prefix stay distinct")

print("a pathological verb")
n = mcp_tool_name("b", "v" * 90)
check(len(n) <= MAX_LEN and LEGAL.match(n) is not None, f"still legal ({len(n)} chars)")

print("\n" + ("FAILURES" if fails else "all passed"))
sys.exit(1 if fails else 0)
