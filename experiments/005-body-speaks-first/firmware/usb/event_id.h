/* ULIDs and timestamps for a body with no clock.
 *
 * The specification asks that an event id SHOULD be a ULID or UUID "so a host
 * can deduplicate across a reconnect", and that `ts` is the body's clock --
 * with `clock_confident: false` when that clock cannot be trusted, so the
 * host prefers arrival time instead.
 *
 * A Pico is exactly the case that field was written for. It has no RTC and no
 * network time: it knows how long it has been awake and nothing else. So this
 * emits an honest uptime-based timestamp, says plainly that it is not
 * confident, and puts the randomness a ULID needs into the low bits so ids
 * stay unique across a reboot -- when the uptime clock starts again at zero.
 */
#ifndef OBP_EVENT_ID_H
#define OBP_EVENT_ID_H

#include <stddef.h>

/* Write a 26-character Crockford base32 ULID into `dst` (needs 27 bytes). */
void ulid(char *dst, size_t dst_size);

/* Write an ISO-8601 timestamp for the current uptime into `dst`.
 * The epoch is boot, not 1970, which is what `clock_confident: false` warns
 * a host about. */
void uptime_iso(char *dst, size_t dst_size);

#endif /* OBP_EVENT_ID_H */
