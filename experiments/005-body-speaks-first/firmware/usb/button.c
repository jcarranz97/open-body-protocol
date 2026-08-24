#include "button.h"
#include "pico/stdlib.h"

#define DEBOUNCE_MS 20

static bool     stable_down = false;   /* debounced state */
static bool     last_raw    = false;
static uint32_t last_change = 0;
static uint32_t pressed_at  = 0;

void button_init(void) {
    gpio_init(BUTTON_PIN);
    gpio_set_dir(BUTTON_PIN, GPIO_IN);
    gpio_pull_up(BUTTON_PIN);          /* idles high; a press pulls it low */
}

bool button_poll(uint32_t *hold_ms) {
    uint32_t now = to_ms_since_boot(get_absolute_time());
    bool raw = !gpio_get(BUTTON_PIN);  /* active low */

    if (raw != last_raw) {             /* the contact moved; start the clock */
        last_raw = raw;
        last_change = now;
        return false;
    }
    if (now - last_change < DEBOUNCE_MS) return false;
    if (raw == stable_down) return false;

    stable_down = raw;
    if (stable_down) {
        pressed_at = now;
        return false;                  /* report on release, with a duration */
    }
    if (hold_ms) *hold_ms = now - pressed_at;
    return true;
}
