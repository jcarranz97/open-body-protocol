/* OBP body contract on a Raspberry Pi Pico, using the pico-sdk (C).
 *
 * Speaks the identical wire protocol as ../micropython/main.py: newline-
 * delimited JSON-RPC 2.0 over USB CDC. The host client cannot tell which
 * firmware is on the other end, which is the point -- the contract is the
 * product, the language is the builder's choice.
 *
 * Build: see README.md in this directory.
 */
#include <stdio.h>
#include <string.h>

#include "pico/stdlib.h"
#include "pico/unique_id.h"
#include "pico/stdio_usb.h"
#include "hardware/pwm.h"
#include "hardware/watchdog.h"

#include "json_min.h"

#ifdef CYW43_WL_GPIO_LED_PIN
#include "pico/cyw43_arch.h"
/* On W boards the LED hangs off the wireless chip: digital only, no PWM. */
#define LED_DIMMABLE 0
#elif defined(PICO_DEFAULT_LED_PIN)
#define LED_DIMMABLE 1
#else
#define LED_DIMMABLE 0
#endif

#define FW "pico-sdk-0.1.0"

/* Set to a GPIO number to attach a hobby servo; leave undefined on a bare
 * board and the servo verb is simply never advertised. */
/* #define SERVO_PIN 15 */

#define LINE_MAX 512

static char body_id[24];

/* ---------------------------------------------------------------- hardware */

static void led_init(void) {
#if defined(CYW43_WL_GPIO_LED_PIN)
    cyw43_arch_init();
#elif LED_DIMMABLE
    gpio_set_function(PICO_DEFAULT_LED_PIN, GPIO_FUNC_PWM);
    uint slice = pwm_gpio_to_slice_num(PICO_DEFAULT_LED_PIN);
    pwm_set_clkdiv(slice, 4.0f);      /* ~477 Hz: no visible flicker */
    pwm_set_wrap(slice, 65535);
    pwm_set_enabled(slice, true);
#endif
}

#if LED_DIMMABLE
/* The brain asks for a percentage; the body decides what that means in
 * hardware. Perceived brightness is roughly the square of duty cycle, so a
 * linear duty would make "50" look like 70-something. Squaring here is the
 * smallest possible example of the rule that intent belongs to the brain and
 * implementation belongs to the body. */
static void led_level(long pct) {
    if (pct < 0) pct = 0;
    if (pct > 100) pct = 100;
    uint16_t duty = (uint16_t)((pct * pct * 65535L) / 10000L);
    pwm_set_gpio_level(PICO_DEFAULT_LED_PIN, duty);
}
#endif

static void led_set(bool on) {
#if defined(CYW43_WL_GPIO_LED_PIN)
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, on);
#elif LED_DIMMABLE
    led_level(on ? 100 : 0);
#else
    (void)on;
#endif
}

#ifdef SERVO_PIN
static uint servo_slice;

static void servo_init(void) {
    gpio_set_function(SERVO_PIN, GPIO_FUNC_PWM);
    servo_slice = pwm_gpio_to_slice_num(SERVO_PIN);
    /* 125 MHz / 64 / 39062 ~= 50 Hz */
    pwm_set_clkdiv(servo_slice, 64.0f);
    pwm_set_wrap(servo_slice, 39062);
    pwm_set_enabled(servo_slice, true);
}

static void servo_set(long angle) {
    /* 0.5 ms .. 2.5 ms pulse inside a 20 ms frame */
    float pulse_ms = 0.5f + ((float)angle / 180.0f) * 2.0f;
    pwm_set_gpio_level(SERVO_PIN, (uint16_t)(39062.0f * pulse_ms / 20.0f));
}
#endif

/* ------------------------------------------------------------------- wire */

static void send_result_text(long id, const char *text, bool is_error) {
    /* The contract's result shape is MCP's: content[] plus isError. */
    printf("{\"jsonrpc\":\"2.0\",\"id\":%ld,\"result\":{\"content\":"
           "[{\"type\":\"text\",\"text\":\"%s\"}],\"isError\":%s}}\n",
           id, text, is_error ? "true" : "false");
}

static void send_describe(long id) {
    printf("{\"jsonrpc\":\"2.0\",\"id\":%ld,\"result\":{"
           "\"body\":{\"id\":\"%s\",\"name\":\"Raspberry Pi Pico body (pico-sdk)\","
           "\"fw\":\"%s\",\"caps\":[\"led\""
#if LED_DIMMABLE
           ",\"dimmable\""
#endif
#ifdef SERVO_PIN
           ",\"servo\""
#endif
           "]},\"tools\":["
           "{\"name\":\"set_led\",\"description\":\"Turn the body's indicator light on or off.\","
           "\"inputSchema\":{\"type\":\"object\",\"properties\":{"
           "\"on\":{\"type\":\"boolean\",\"description\":\"True for on.\"}},"
           "\"required\":[\"on\"]}},"
           "{\"name\":\"blink\",\"description\":\"Blink the indicator light. Use to acknowledge something without speaking.\","
           "\"inputSchema\":{\"type\":\"object\",\"properties\":{"
           "\"times\":{\"type\":\"integer\",\"minimum\":1,\"maximum\":10,\"default\":3},"
           "\"interval_ms\":{\"type\":\"integer\",\"minimum\":50,\"maximum\":2000,\"default\":200}}}},"
#if LED_DIMMABLE
           "{\"name\":\"set_brightness\",\"description\":\"Set how brightly the indicator light glows, as a percentage. Use for mood: dim when calm, bright when alert.\","
           "\"inputSchema\":{\"type\":\"object\",\"properties\":{"
           "\"level\":{\"type\":\"integer\",\"minimum\":0,\"maximum\":100,\"description\":\"0 is off, 100 is full.\"}},"
           "\"required\":[\"level\"]}},"
#endif
           "{\"name\":\"move\",\"description\":\"Move the body in a direction. Distances are approximate; the body decides how.\","
           "\"inputSchema\":{\"type\":\"object\",\"properties\":{"
           "\"direction\":{\"type\":\"string\",\"enum\":[\"forward\",\"back\",\"left\",\"right\"]},"
           "\"distance_cm\":{\"type\":\"number\",\"minimum\":1,\"maximum\":50,\"default\":10}},"
           "\"required\":[\"direction\"]}},"
#ifdef SERVO_PIN
           "{\"name\":\"servo_angle\",\"description\":\"Point the servo at an absolute angle in degrees.\","
           "\"inputSchema\":{\"type\":\"object\",\"properties\":{"
           "\"angle\":{\"type\":\"integer\",\"minimum\":0,\"maximum\":180}},"
           "\"required\":[\"angle\"]}},"
#endif
           "{\"name\":\"reboot\",\"description\":\"Restart the body. Disconnects it briefly.\","
           "\"inputSchema\":{\"type\":\"object\",\"properties\":{}},\"userOnly\":true}"
           "]}}\n",
           id, body_id, FW);
}

/* ------------------------------------------------------------------ tools */

static void tool_call(long id, const char *params, size_t params_len) {
    char name[32] = {0};
    if (!jm_get_str(params, params_len, "name", name, sizeof name)) {
        send_result_text(id, "missing tool name", true);
        return;
    }

    jm_val args;
    const char *a = "{}";
    size_t a_len = 2;
    if (jm_get_obj(params, params_len, "arguments", &args)) {
        a = args.start;
        a_len = args.len;
    }

    if (strcmp(name, "set_led") == 0) {
        bool on;
        if (!jm_get_bool(a, a_len, "on", &on)) {
            send_result_text(id, "set_led requires 'on'", true);
            return;
        }
        led_set(on);
        send_result_text(id, on ? "light on" : "light off", false);
        return;
    }

#if LED_DIMMABLE
    if (strcmp(name, "set_brightness") == 0) {
        long level;
        if (!jm_get_int(a, a_len, "level", &level)) {
            send_result_text(id, "set_brightness requires 'level'", true);
            return;
        }
        if (level < 0 || level > 100) {
            send_result_text(id, "level must be 0..100", true);
            return;
        }
        led_level(level);
        char msg[48];
        snprintf(msg, sizeof msg, "brightness %ld%%", level);
        send_result_text(id, msg, false);
        return;
    }
#endif

    if (strcmp(name, "blink") == 0) {
        long times = 3, interval = 200;
        jm_get_int(a, a_len, "times", &times);
        jm_get_int(a, a_len, "interval_ms", &interval);
        if (times < 1 || times > 10) {
            send_result_text(id, "times must be between 1 and 10", true);
            return;
        }
        for (long i = 0; i < times; i++) {
            led_set(true);  sleep_ms((uint32_t)interval);
            led_set(false); sleep_ms((uint32_t)interval);
        }
        char msg[48];
        snprintf(msg, sizeof msg, "blinked %ld times", times);
        send_result_text(id, msg, false);
        return;
    }

    if (strcmp(name, "move") == 0) {
        char dir[16] = {0};
        if (!jm_get_str(a, a_len, "direction", dir, sizeof dir)) {
            send_result_text(id, "move requires 'direction'", true);
            return;
        }
        if (strcmp(dir, "forward") && strcmp(dir, "back") &&
            strcmp(dir, "left") && strcmp(dir, "right")) {
            char msg[64];
            snprintf(msg, sizeof msg, "unknown direction: %s", dir);
            send_result_text(id, msg, true);
            return;
        }
        long dist = 10;
        jm_get_int(a, a_len, "distance_cm", &dist);
        /* No drivetrain on a bare board. Acknowledge visibly, and say so --
         * an honest tool result is what lets the brain tell the truth. */
        for (int i = 0; i < 2; i++) {
            led_set(true);  sleep_ms(80);
            led_set(false); sleep_ms(80);
        }
        char msg[96];
        snprintf(msg, sizeof msg,
                 "acknowledged move %s %ldcm (simulated: no drivetrain attached)", dir, dist);
        send_result_text(id, msg, false);
        return;
    }

#ifdef SERVO_PIN
    if (strcmp(name, "servo_angle") == 0) {
        long angle;
        if (!jm_get_int(a, a_len, "angle", &angle)) {
            send_result_text(id, "servo_angle requires 'angle'", true);
            return;
        }
        if (angle < 0 || angle > 180) {
            send_result_text(id, "angle must be 0..180", true);
            return;
        }
        servo_set(angle);
        char msg[48];
        snprintf(msg, sizeof msg, "servo at %ld degrees", angle);
        send_result_text(id, msg, false);
        return;
    }
#endif

    if (strcmp(name, "reboot") == 0) {
        printf("{\"jsonrpc\":\"2.0\",\"method\":\"notifications/body/offline\","
               "\"params\":{\"id\":\"%s\",\"reason\":\"reboot\"}}\n", body_id);
        sleep_ms(100);
        watchdog_reboot(0, 0, 0);
        return; /* not reached */
    }

    char msg[64];
    snprintf(msg, sizeof msg, "no such tool: %s", name);
    send_result_text(id, msg, true);
}

/* ------------------------------------------------------------------- main */

static void handle_line(char *line, size_t len) {
    long id = 0;
    jm_get_int(line, len, "id", &id);

    char method[32] = {0};
    if (!jm_get_str(line, len, "method", method, sizeof method)) return;

    if (strcmp(method, "body/describe") == 0) {
        send_describe(id);
    } else if (strcmp(method, "tools/call") == 0) {
        jm_val params;
        if (jm_get_obj(line, len, "params", &params)) {
            tool_call(id, params.start, params.len);
        } else {
            send_result_text(id, "tools/call requires params", true);
        }
    } else if (strcmp(method, "ping") == 0) {
        printf("{\"jsonrpc\":\"2.0\",\"id\":%ld,\"result\":{}}\n", id);
    } else {
        printf("{\"jsonrpc\":\"2.0\",\"id\":%ld,\"error\":"
               "{\"code\":-32601,\"message\":\"method not found\"}}\n", id);
    }
}

int main(void) {
    stdio_init_all();
    /* Keep the framing exactly one '\n' per message; the default stdio
     * translation would turn it into "\r\n". */
    stdio_set_translate_crlf(&stdio_usb, false);

    led_init();
#ifdef SERVO_PIN
    servo_init();
#endif

    pico_unique_board_id_t uid;
    pico_get_unique_board_id(&uid);
    snprintf(body_id, sizeof body_id, "pico-%02x%02x%02x",
             uid.id[5], uid.id[6], uid.id[7]);

    /* Presence, announced rather than polled. Over USB the equivalent of
     * MQTT's retained message is simply "the port is open". */
    printf("{\"jsonrpc\":\"2.0\",\"method\":\"notifications/body/online\","
           "\"params\":{\"id\":\"%s\",\"fw\":\"%s\"}}\n", body_id, FW);

    static char line[LINE_MAX];
    size_t n = 0;

    for (;;) {
        int c = getchar_timeout_us(200000);
        if (c == PICO_ERROR_TIMEOUT) continue;
        if (c == '\r') continue;
        if (c == '\n') {
            if (n > 0) {
                line[n] = '\0';
                handle_line(line, n);
                n = 0;
            }
            continue;
        }
        if (n < LINE_MAX - 1) line[n++] = (char)c;
        else n = 0; /* overlong line: drop it rather than truncate into garbage */
    }
}
