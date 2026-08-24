#include "event_id.h"
#include "pico/stdlib.h"
#include "pico/rand.h"
#include <stdio.h>

static const char B32[] = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";  /* Crockford */

void ulid(char *dst, size_t dst_size) {
    if (dst_size < 27) { if (dst_size) dst[0] = '\0'; return; }
    uint64_t t = to_ms_since_boot(get_absolute_time());
    /* 48-bit time, high bits first, so ids sort in the order they happened. */
    for (int i = 9; i >= 0; i--) { dst[i] = B32[t & 31]; t >>= 5; }
    /* 80 bits of randomness. Without this, two events at the same
     * millisecond after two reboots would share an id, and a host
     * deduplicating across a reconnect would drop a real press. */
    uint64_t r1 = get_rand_64(), r2 = get_rand_64();
    for (int i = 25; i >= 18; i--) { dst[i] = B32[r2 & 31]; r2 >>= 5; }
    for (int i = 17; i >= 10; i--) { dst[i] = B32[r1 & 31]; r1 >>= 5; }
    dst[26] = '\0';
}

void uptime_iso(char *dst, size_t dst_size) {
    uint32_t ms = to_ms_since_boot(get_absolute_time());
    uint32_t s = ms / 1000;
    snprintf(dst, dst_size, "1970-01-01T%02u:%02u:%02u.%03uZ",
             (unsigned)(s / 3600) % 24, (unsigned)(s / 60) % 60,
             (unsigned)(s % 60), (unsigned)(ms % 1000));
}
