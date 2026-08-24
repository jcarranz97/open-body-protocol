#include "json_min.h"

#include <stdlib.h>
#include <string.h>

static const char *skip_ws(const char *p, const char *end) {
    while (p < end && (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')) p++;
    return p;
}

/* Advance past one complete JSON value, returning the position after it. */
static const char *skip_value(const char *p, const char *end, jm_val *out) {
    p = skip_ws(p, end);
    if (p >= end) return NULL;

    if (*p == '"') {
        const char *s = ++p;
        while (p < end && *p != '"') {
            if (*p == '\\' && p + 1 < end) p++;
            p++;
        }
        if (p >= end) return NULL;
        if (out) { out->type = JM_STRING; out->start = s; out->len = (size_t)(p - s); }
        return p + 1;
    }

    if (*p == '{' || *p == '[') {
        char open = *p, close = (open == '{') ? '}' : ']';
        const char *s = p;
        int depth = 0;
        bool in_str = false;
        while (p < end) {
            if (in_str) {
                if (*p == '\\') p++;
                else if (*p == '"') in_str = false;
            } else if (*p == '"') {
                in_str = true;
            } else if (*p == open) {
                depth++;
            } else if (*p == close) {
                depth--;
                if (depth == 0) {
                    p++;
                    if (out) {
                        out->type = (open == '{') ? JM_OBJECT : JM_ARRAY;
                        out->start = s;
                        out->len = (size_t)(p - s);
                    }
                    return p;
                }
            }
            p++;
        }
        return NULL;
    }

    {   /* literal: true / false / null / number */
        const char *s = p;
        while (p < end && *p != ',' && *p != '}' && *p != ']' &&
               *p != ' ' && *p != '\t' && *p != '\n' && *p != '\r') p++;
        size_t len = (size_t)(p - s);
        if (out) {
            out->start = s;
            out->len = len;
            if (len == 4 && strncmp(s, "true", 4) == 0) out->type = JM_BOOL;
            else if (len == 5 && strncmp(s, "false", 5) == 0) out->type = JM_BOOL;
            else if (len == 4 && strncmp(s, "null", 4) == 0) out->type = JM_NULL;
            else out->type = JM_NUMBER;
        }
        return p;
    }
}

bool jm_get(const char *obj, size_t obj_len, const char *key, jm_val *out) {
    if (obj == NULL || obj_len < 2) return false;
    const char *end = obj + obj_len;
    const char *p = skip_ws(obj, end);
    if (p >= end || *p != '{') return false;
    p++;

    size_t key_len = strlen(key);

    while (p < end) {
        p = skip_ws(p, end);
        if (p >= end || *p == '}') return false;

        if (*p != '"') return false;
        const char *k = ++p;
        while (p < end && *p != '"') {
            if (*p == '\\' && p + 1 < end) p++;
            p++;
        }
        if (p >= end) return false;
        size_t k_len = (size_t)(p - k);
        p++; /* closing quote */

        p = skip_ws(p, end);
        if (p >= end || *p != ':') return false;
        p++;

        jm_val v;
        const char *after = skip_value(p, end, &v);
        if (after == NULL) return false;

        if (k_len == key_len && strncmp(k, key, key_len) == 0) {
            if (out) *out = v;
            return true;
        }

        p = skip_ws(after, end);
        if (p < end && *p == ',') p++;
    }
    return false;
}

bool jm_str_eq(const jm_val *v, const char *s) {
    if (v == NULL || v->type != JM_STRING) return false;
    size_t n = strlen(s);
    return v->len == n && strncmp(v->start, s, n) == 0;
}

bool jm_get_str(const char *obj, size_t obj_len, const char *key,
                char *dst, size_t dst_size) {
    jm_val v;
    if (!jm_get(obj, obj_len, key, &v) || v.type != JM_STRING) return false;
    if (dst_size == 0) return false;
    size_t n = v.len < dst_size - 1 ? v.len : dst_size - 1;
    /* Unescape only what the contract can contain: \" and \\ */
    size_t o = 0;
    for (size_t i = 0; i < n && o < dst_size - 1; i++) {
        char c = v.start[i];
        if (c == '\\' && i + 1 < n) { i++; c = v.start[i]; }
        dst[o++] = c;
    }
    dst[o] = '\0';
    return true;
}

bool jm_get_int(const char *obj, size_t obj_len, const char *key, long *out) {
    jm_val v;
    if (!jm_get(obj, obj_len, key, &v) || v.type != JM_NUMBER) return false;
    char buf[32];
    size_t n = v.len < sizeof(buf) - 1 ? v.len : sizeof(buf) - 1;
    memcpy(buf, v.start, n);
    buf[n] = '\0';
    if (out) *out = strtol(buf, NULL, 10);
    return true;
}

bool jm_get_bool(const char *obj, size_t obj_len, const char *key, bool *out) {
    jm_val v;
    if (!jm_get(obj, obj_len, key, &v) || v.type != JM_BOOL) return false;
    if (out) *out = (v.len == 4);
    return true;
}

bool jm_get_obj(const char *obj, size_t obj_len, const char *key, jm_val *out) {
    jm_val v;
    if (!jm_get(obj, obj_len, key, &v) || v.type != JM_OBJECT) return false;
    if (out) *out = v;
    return true;
}
