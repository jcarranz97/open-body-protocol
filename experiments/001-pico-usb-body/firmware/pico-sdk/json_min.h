/* json_min -- just enough JSON for the OBP body contract, in C.
 *
 * Deliberately small: the body contract's messages are shallow and known in
 * advance, so a full DOM parser would be more code than the firmware it
 * serves. This reads values out of an object by key, respecting nesting, and
 * does not allocate.
 *
 * If a body outgrows this, swap in jsmn (MIT, single header) or cJSON. The
 * contract does not care which parser produced the values.
 */
#ifndef JSON_MIN_H
#define JSON_MIN_H

#include <stdbool.h>
#include <stddef.h>

typedef enum {
    JM_NONE = 0,
    JM_STRING,
    JM_NUMBER,
    JM_BOOL,
    JM_NULL,
    JM_OBJECT,
    JM_ARRAY
} jm_type;

typedef struct {
    jm_type type;
    const char *start; /* for strings: first char inside the quotes */
    size_t len;        /* for strings: length excluding the quotes   */
} jm_val;

/* Find `key` among the members of the object at `obj` (which must start with
 * '{'). Only depth-1 members are considered, so a nested "name" never shadows
 * a top-level one. Returns false when absent. */
bool jm_get(const char *obj, size_t obj_len, const char *key, jm_val *out);

/* Convenience accessors. Each returns false if the key is missing or the
 * value is of the wrong type. */
bool jm_get_str(const char *obj, size_t obj_len, const char *key,
                char *dst, size_t dst_size);
bool jm_get_int(const char *obj, size_t obj_len, const char *key, long *out);
bool jm_get_bool(const char *obj, size_t obj_len, const char *key, bool *out);
bool jm_get_obj(const char *obj, size_t obj_len, const char *key, jm_val *out);

/* True when the string value at `v` equals `s`. */
bool jm_str_eq(const jm_val *v, const char *s);

#endif /* JSON_MIN_H */
