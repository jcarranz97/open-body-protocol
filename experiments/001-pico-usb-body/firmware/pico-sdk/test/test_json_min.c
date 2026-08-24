/* Host-side tests for json_min. Build and run with plain gcc -- no pico-sdk,
 * no board. The parser is the only part of the C firmware with real logic in
 * it, so it is the part worth testing off-target.
 *
 *   cc -std=c11 -Wall -Wextra -o /tmp/t test/test_json_min.c json_min.c && /tmp/t
 */
#include "../json_min.h"

#include <stdio.h>
#include <string.h>

static int failures = 0;

#define CHECK(cond, msg) do {                                   \
    if (!(cond)) { printf("  FAIL: %s\n", msg); failures++; }   \
    else         { printf("  ok:   %s\n", msg); }               \
} while (0)

int main(void) {
    const char *req =
        "{\"jsonrpc\":\"2.0\",\"id\":7,\"method\":\"tools/call\","
        "\"params\":{\"name\":\"blink\",\"arguments\":{\"times\":5,\"interval_ms\":120}}}";
    size_t len = strlen(req);

    printf("top-level lookups\n");
    char method[32];
    CHECK(jm_get_str(req, len, "method", method, sizeof method) &&
          strcmp(method, "tools/call") == 0, "method == tools/call");
    long id = 0;
    CHECK(jm_get_int(req, len, "id", &id) && id == 7, "id == 7");
    CHECK(!jm_get_str(req, len, "nope", method, sizeof method), "missing key returns false");

    printf("nesting\n");
    jm_val params, args;
    CHECK(jm_get_obj(req, len, "params", &params), "params is an object");
    char name[32];
    CHECK(jm_get_str(params.start, params.len, "name", name, sizeof name) &&
          strcmp(name, "blink") == 0, "params.name == blink");
    CHECK(jm_get_obj(params.start, params.len, "arguments", &args), "arguments is an object");
    long times = 0;
    CHECK(jm_get_int(args.start, args.len, "times", &times) && times == 5, "arguments.times == 5");

    printf("shadowing -- a nested key must not be seen from the top level\n");
    const char *shadow = "{\"a\":1,\"params\":{\"a\":99}}";
    long a = 0;
    CHECK(jm_get_int(shadow, strlen(shadow), "a", &a) && a == 1, "top-level a wins over nested a");

    printf("types\n");
    const char *types =
        "{\"on\":true,\"off\":false,\"nul\":null,\"neg\":-42,\"s\":\"hi\",\"arr\":[1,2,3]}";
    size_t tl = strlen(types);
    bool b = false;
    CHECK(jm_get_bool(types, tl, "on", &b) && b, "on == true");
    CHECK(jm_get_bool(types, tl, "off", &b) && !b, "off == false");
    long neg = 0;
    CHECK(jm_get_int(types, tl, "neg", &neg) && neg == -42, "neg == -42");
    CHECK(!jm_get_int(types, tl, "s", &neg), "string is not an int");
    CHECK(!jm_get_bool(types, tl, "nul", &b), "null is not a bool");
    jm_val arr;
    CHECK(jm_get(types, tl, "arr", &arr) && arr.type == JM_ARRAY, "arr is an array");

    printf("strings with awkward contents\n");
    const char *esc = "{\"t\":\"a\\\"b\",\"u\":\"back\\\\slash\",\"v\":\"has:colon,and{brace}\"}";
    size_t el = strlen(esc);
    char out[32];
    CHECK(jm_get_str(esc, el, "t", out, sizeof out) && strcmp(out, "a\"b") == 0, "escaped quote");
    CHECK(jm_get_str(esc, el, "u", out, sizeof out) && strcmp(out, "back\\slash") == 0, "escaped backslash");
    CHECK(jm_get_str(esc, el, "v", out, sizeof out) &&
          strcmp(out, "has:colon,and{brace}") == 0, "punctuation inside a string");
    const char *after = "{\"s\":\"}\",\"after\":3}";
    long n = 0;
    CHECK(jm_get_int(after, strlen(after), "after", &n) && n == 3, "brace inside a string does not end the object");

    printf("malformed input must not crash or hang\n");
    const char *bad[] = {"", "{", "{\"a\"", "{\"a\":", "not json", "{\"a\":\"unterminated", "[]"};
    for (size_t i = 0; i < sizeof bad / sizeof bad[0]; i++) {
        jm_val v;
        (void)jm_get(bad[i], strlen(bad[i]), "a", &v);
    }
    CHECK(1, "survived malformed inputs");

    printf("whitespace\n");
    const char *ws = "{ \"a\" : 1 , \"b\" : { \"c\" : 2 } }";
    long c = 0;
    jm_val bobj;
    CHECK(jm_get_obj(ws, strlen(ws), "b", &bobj) &&
          jm_get_int(bobj.start, bobj.len, "c", &c) && c == 2, "whitespace tolerated");

    printf("\n%s\n", failures ? "FAILURES" : "all passed");
    return failures ? 1 : 0;
}
