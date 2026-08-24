/* A push button on a GPIO, debounced, reported as an OBP event.
 *
 * Wiring: one leg to physical pin 19 (GP14), the other to physical pin 18
 * (GND) -- the two are adjacent, so the switch spans them with no jumper.
 * The pull-up is internal, so the pin idles high and a press pulls it low.
 * No resistor, no external parts.
 *
 * The BOOTSEL button can be read at runtime instead, but doing so stalls
 * execution from flash while it samples the CS pin, on a board that is also
 * servicing USB. A GPIO costs one switch and none of that.
 */
#ifndef OBP_BUTTON_H
#define OBP_BUTTON_H

#include <stdbool.h>
#include <stdint.h>

#ifndef BUTTON_PIN
#define BUTTON_PIN 14
#endif

/* Configure the pin. Call once, after stdio. */
void button_init(void);

/* Poll. Returns true exactly once per completed press, writing how long the
 * button was held to *hold_ms.
 *
 * Debouncing is the body's job, not the host's: B13 says the body owns
 * timing and reflexes, and a contact that chatters for 5ms would otherwise
 * become five events on the wire and five turns of an agent's attention.
 * The press is reported on *release* so the duration is known -- which is
 * also what the specification's own example carries (`hold_ms: 120`).
 */
bool button_poll(uint32_t *hold_ms);

#endif /* OBP_BUTTON_H */
