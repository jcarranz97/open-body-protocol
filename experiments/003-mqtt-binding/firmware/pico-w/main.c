/* OBP body on a Raspberry Pi Pico W: the MQTT binding.
 *
 * Same contract as the USB bodies in experiments 001 and 002 — same verbs,
 * same descriptors, same result shape — carried over MQTT instead of a
 * cable. A host cannot tell which binding a body is behind, which is the
 * claim this experiment exists to test.
 *
 * Note the capability difference, and that it is real rather than
 * configured: a Pico W drives its LED through the wireless chip, which
 * cannot be PWM'd, so this body advertises no set_brightness and does not
 * claim "dimmable". The identical source on a non-W board would.
 */
#include <stdio.h>
#include <string.h>

#include "pico/stdlib.h"
#include "pico/unique_id.h"
#include "pico/stdio_usb.h"
#include "pico/cyw43_arch.h"
#include "lwip/apps/mqtt.h"
#include "lwip/ip_addr.h"
#include "lwip/netif.h"
#include "hardware/watchdog.h"

#include "json_min.h"

#define FW "obp-picow-0.1.0"

#ifndef WIFI_SSID
#error "Set -DWIFI_SSID=\"...\" and -DWIFI_PASSWORD=\"...\" at configure time"
#endif
#ifndef MQTT_BROKER
#define MQTT_BROKER "192.168.1.10"
#endif
#ifndef MQTT_PORT
#define MQTT_PORT 1883
#endif

#define TOPIC_MAX 96
#define PAYLOAD_MAX 2048

static char body_id[24];
static char t_presence[TOPIC_MAX], t_rpc[TOPIC_MAX], t_reply[TOPIC_MAX];
static mqtt_client_t *client;
static volatile bool mqtt_up = false;
/* True from the moment a connect is issued until the callback reports an
 * outcome. Without it a periodic retry starts a second TCP connection while
 * the first handshake is still in flight, abandoning it — the broker then
 * sees sockets that open and never send a CONNECT, and times them out. */
static volatile bool connect_pending = false;
static ip_addr_t broker_addr;

/* one inbound message, reassembled from lwIP's fragments */
static char in_topic[TOPIC_MAX];
static char in_data[PAYLOAD_MAX];
static uint32_t in_len;
static bool in_overflow;

/* The only output a bare Pico W has is its LED, so use it: slow pulse while
 * joining WiFi, fast pulse while reaching the broker, three flashes when
 * announced. A body that cannot say what is wrong is a body nobody can
 * debug. */
static void status_blink(uint32_t period_ms, uint32_t total_ms);

/* With the threadsafe-background arch lwIP runs from an interrupt, so a
 * plain sleep does not stall the network. Kept as a named function anyway:
 * a body that blocks while performing a verb is a real hazard, and this is
 * the place to fix it if the arch ever changes. */
static void poll_sleep(uint32_t ms) {
    sleep_ms(ms);
}

/* ------------------------------------------------------------------ body */

static void led_set(bool on) {
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, on);
}

static void status_blink(uint32_t period_ms, uint32_t total_ms) {
    uint32_t waited = 0;
    while (waited < total_ms) {
        led_set(true);  poll_sleep(period_ms / 2);
        led_set(false); poll_sleep(period_ms / 2);
        waited += period_ms;
    }
}

static const char *DESCRIBE_FMT =
    "{\"jsonrpc\":\"2.0\",\"id\":%s,\"result\":{\"v\":0,"
    "\"body\":{\"id\":\"%s\",\"name\":\"Raspberry Pi Pico W body\","
    "\"fw\":\"" FW "\",\"caps\":[\"led\"]},"
    "\"tools\":["
    "{\"name\":\"set_led\",\"description\":\"Turn the body's indicator light on or off.\","
    "\"inputSchema\":{\"type\":\"object\",\"properties\":{"
    "\"on\":{\"type\":\"boolean\",\"description\":\"True for on.\"}},"
    "\"required\":[\"on\"]}},"
    "{\"name\":\"blink\",\"description\":\"Blink the indicator light. Use to acknowledge something without speaking.\","
    "\"inputSchema\":{\"type\":\"object\",\"properties\":{"
    "\"times\":{\"type\":\"integer\",\"minimum\":1,\"maximum\":10,\"default\":3},"
    "\"interval_ms\":{\"type\":\"integer\",\"minimum\":50,\"maximum\":2000,\"default\":200}}}},"
    "{\"name\":\"reboot\",\"description\":\"Restart the body. Disconnects it briefly.\","
    "\"inputSchema\":{\"type\":\"object\",\"properties\":{}},\"userOnly\":true}"
    "]}}";

/* Every publish in this firmware happens inside an lwIP callback — the
 * connect callback, or a request arriving on the wire — so the lwIP lock is
 * already held and must NOT be taken again. Doing so is what froze the first
 * build of this firmware with its LED stuck on. The lock belongs around
 * calls made from the main loop, and nowhere else. */
/* Set by the reboot verb, acted on by the main loop -- see tool_call(). */
static volatile bool reboot_pending = false;
static absolute_time_t reboot_at;

static void publish(const char *topic, const char *payload, uint8_t qos, uint8_t retain) {
    mqtt_publish(client, topic, payload, strlen(payload), qos, retain, NULL, NULL);
}

/* A JSON-RPC id is a string *or* a number, and a response MUST echo the
 * request's verbatim -- it is the only thing correlating a reply with the call
 * that asked for it. Reading it as a long collapsed every string id to 0, so
 * this body answered every request correctly, in under a second, to a host
 * that could never match the answer to its question. The failure looked like
 * silence and was in fact a reply nobody could claim.
 *
 * The token is copied raw, so escapes inside a string id survive untouched. */
#define ID_MAX 96

static void copy_id(const char *json, size_t len, char *dst, size_t dst_size) {
    jm_val v;
    if (!jm_get(json, len, "id", &v) || v.type == JM_NULL) {
        snprintf(dst, dst_size, "null");
    } else if (v.type == JM_STRING && v.len + 3 <= dst_size) {
        snprintf(dst, dst_size, "\"%.*s\"", (int)v.len, v.start);
    } else if (v.type == JM_NUMBER && v.len + 1 <= dst_size) {
        snprintf(dst, dst_size, "%.*s", (int)v.len, v.start);
    } else {
        /* Truncating an id would be worse than admitting we cannot echo it:
         * a half-copied string id is invalid JSON, and a silently shortened
         * one matches the wrong call. */
        snprintf(dst, dst_size, "null");
    }
}

static void reply_text(const char *id, const char *text, bool is_error) {
    static char buf[512];
    snprintf(buf, sizeof buf,
             "{\"jsonrpc\":\"2.0\",\"id\":%s,\"result\":{\"content\":"
             "[{\"type\":\"text\",\"text\":\"%s\"}],\"isError\":%s}}",
             id, text, is_error ? "true" : "false");
    publish(t_reply, buf, 1, 0);
}

static void tool_call(const char *id, const char *params, size_t plen) {
    char name[32] = {0};
    if (!jm_get_str(params, plen, "name", name, sizeof name)) {
        reply_text(id, "missing tool name", true);
        return;
    }
    jm_val args;
    const char *a = "{}";
    size_t alen = 2;
    if (jm_get_obj(params, plen, "arguments", &args)) {
        a = args.start;
        alen = args.len;
    }

    if (strcmp(name, "set_led") == 0) {
        bool on;
        if (!jm_get_bool(a, alen, "on", &on)) {
            reply_text(id, "set_led requires 'on'", true);
            return;
        }
        led_set(on);
        reply_text(id, on ? "light on" : "light off", false);
        return;
    }

    if (strcmp(name, "blink") == 0) {
        long times = 3, interval = 200;
        jm_get_int(a, alen, "times", &times);
        jm_get_int(a, alen, "interval_ms", &interval);
        if (times < 1 || times > 10) {
            reply_text(id, "times must be between 1 and 10", true);
            return;
        }
        for (long i = 0; i < times; i++) {
            led_set(true);  poll_sleep((uint32_t)interval);
            led_set(false); poll_sleep((uint32_t)interval);
        }
        char msg[48];
        snprintf(msg, sizeof msg, "blinked %ld times", times);
        reply_text(id, msg, false);
        return;
    }

    if (strcmp(name, "reboot") == 0) {
        /* B8 applies to reboot like any other verb: the caller gets an answer.
         * The first version of this rebooted from inside the lwIP callback,
         * so the reply and the presence-clear were still sitting in the
         * output ring buffer when the core reset. The person who asked saw a
         * timeout, and the body came back as if nothing had been asked --
         * a verb that works perfectly and reports as broken.
         *
         * So: answer, clear our own retained presence rather than leaving the
         * host to wait out the broker's keep-alive, and let the main loop do
         * the resetting once lwIP has actually flushed both. */
        reply_text(id, "rebooting", false);
        publish(t_presence, "", 1, 1);
        reboot_at = make_timeout_time_ms(400);
        reboot_pending = true;
        return;
    }

    char msg[64];
    snprintf(msg, sizeof msg, "no such tool: %s", name);
    reply_text(id, msg, true);
}

static void handle_request(const char *json, size_t len) {
    char id[ID_MAX];
    copy_id(json, len, id, sizeof id);
    char method[32] = {0};
    if (!jm_get_str(json, len, "method", method, sizeof method)) return;

    if (strcmp(method, "body/describe") == 0) {
        static char buf[1600];
        snprintf(buf, sizeof buf, DESCRIBE_FMT, id, body_id);
        publish(t_reply, buf, 1, 0);
    } else if (strcmp(method, "tools/call") == 0) {
        jm_val params;
        if (jm_get_obj(json, len, "params", &params)) {
            tool_call(id, params.start, params.len);
        } else {
            reply_text(id, "tools/call requires params", true);
        }
    } else if (strcmp(method, "ping") == 0) {
        static char buf[96];
        snprintf(buf, sizeof buf, "{\"jsonrpc\":\"2.0\",\"id\":%s,\"result\":{}}", id);
        publish(t_reply, buf, 1, 0);
    } else {
        static char buf[160];
        snprintf(buf, sizeof buf,
                 "{\"jsonrpc\":\"2.0\",\"id\":%s,\"error\":{\"code\":-32601,"
                 "\"message\":\"method not found\"}}", id);
        publish(t_reply, buf, 1, 0);
    }
}

/* ------------------------------------------------------------ mqtt glue */

static void incoming_publish_cb(void *arg, const char *topic, u32_t tot_len) {
    (void)arg;
    strncpy(in_topic, topic, sizeof in_topic - 1);
    in_topic[sizeof in_topic - 1] = '\0';
    in_len = 0;
    in_overflow = tot_len >= PAYLOAD_MAX;
}

static void incoming_data_cb(void *arg, const u8_t *data, u16_t len, u8_t flags) {
    (void)arg;
    if (!in_overflow && in_len + len < PAYLOAD_MAX) {
        memcpy(in_data + in_len, data, len);
        in_len += len;
    } else {
        in_overflow = true;
    }
    if (flags & MQTT_DATA_FLAG_LAST) {
        if (in_overflow) {
            printf("dropped an oversized request (%lu bytes)\n", (unsigned long)in_len);
        } else {
            in_data[in_len] = '\0';
            handle_request(in_data, in_len);
        }
        in_len = 0;
        in_overflow = false;
    }
}

static void announce_presence(void) {
    static char buf[160];
    snprintf(buf, sizeof buf,
             "{\"id\":\"%s\",\"fw\":\"" FW "\",\"name\":\"Raspberry Pi Pico W body\"}",
             body_id);
    publish(t_presence, buf, 1, 1);          /* retained */
}

static void connection_cb(mqtt_client_t *c, void *arg, mqtt_connection_status_t status) {
    (void)c; (void)arg;
    connect_pending = false;
    if (status != MQTT_CONNECT_ACCEPTED) {
        printf("mqtt connect failed: %d\n", status);
        mqtt_up = false;
        return;
    }
    printf("mqtt connected\n");
    mqtt_up = true;
    /* No cyw43_arch_lwip_begin() here: this callback already runs in the
     * lwIP context. Taking the lock again deadlocks under the threadsafe
     * background arch, which is exactly how the first build of this firmware
     * froze with its LED stuck on. */
    mqtt_subscribe(client, t_rpc, 1, NULL, NULL);
    announce_presence();
    for (int i = 0; i < 3; i++) {
        led_set(true);  sleep_ms(60);
        led_set(false); sleep_ms(60);
    }
}

int main(void) {
    stdio_init_all();
    /* Give a terminal a moment to attach, so the boot log is not thrown
     * away. Bounded, because a body must come up with nobody watching. */
    for (int i = 0; i < 30 && !stdio_usb_connected(); i++) sleep_ms(100);
    if (cyw43_arch_init()) {
        printf("cyw43 init failed\n");
        return 1;
    }
    cyw43_arch_enable_sta_mode();

    pico_unique_board_id_t uid;
    pico_get_unique_board_id(&uid);
    snprintf(body_id, sizeof body_id, "picow-%02x%02x%02x",
             uid.id[5], uid.id[6], uid.id[7]);
    snprintf(t_presence, sizeof t_presence, "obp/body/%s/presence", body_id);
    snprintf(t_rpc, sizeof t_rpc, "obp/body/%s/rpc", body_id);
    snprintf(t_reply, sizeof t_reply, "obp/body/%s/rpc/reply", body_id);
    printf("body %s\n", body_id);

    if (!ip4addr_aton(MQTT_BROKER, &broker_addr)) {
        printf("bad broker address: %s\n", MQTT_BROKER);
        while (true) status_blink(1500, 3000);      /* very slow: misconfigured */
    }

    /* Retry rather than give up. A body on a desk outlives the router
     * rebooting, and a firmware that returns from main is a body that has to
     * be power-cycled by hand. */
    while (cyw43_arch_wifi_connect_timeout_ms(WIFI_SSID, WIFI_PASSWORD,
                                              CYW43_AUTH_WPA2_AES_PSK, 20000)) {
        printf("wifi join failed, retrying\n");
        status_blink(500, 3000);                    /* slow pulse: joining */
    }
    printf("wifi ok, ip %s\n", ip4addr_ntoa(netif_ip4_addr(netif_default)));

    /* The presence mechanism: a will with an EMPTY retained payload, which
     * clears the retained announcement when this body stops answering. */
    struct mqtt_connect_client_info_t ci = {0};
    ci.client_id = body_id;
    ci.keep_alive = 60;
    ci.will_topic = t_presence;
    ci.will_msg = "";
    ci.will_qos = 1;
    ci.will_retain = 1;

    client = mqtt_client_new();
    if (client == NULL) {
        printf("mqtt_client_new failed (out of memory)\n");
        while (true) status_blink(1500, 3000);
    }

    absolute_time_t next_report = get_absolute_time();
    while (true) {
        if (reboot_pending && absolute_time_diff_us(get_absolute_time(),
                                                    reboot_at) <= 0) {
            printf("rebooting on request\n");
            watchdog_reboot(0, 0, 0);
        }
        if (!mqtt_up) {
            if (!connect_pending && !mqtt_client_is_connected(client)) {
                printf("connecting to mqtt %s:%d ...\n", MQTT_BROKER, MQTT_PORT);
                cyw43_arch_lwip_begin();       /* main context: lock required */
                err_t e = mqtt_client_connect(client, &broker_addr, MQTT_PORT,
                                              connection_cb, NULL, &ci);
                /* Registered *after* connect and inside the lock, as the
                 * vendor's own example does. */
                mqtt_set_inpub_callback(client, incoming_publish_cb,
                                        incoming_data_cb, NULL);
                cyw43_arch_lwip_end();
                if (e == ERR_OK) {
                    connect_pending = true;
                } else {
                    printf("mqtt_client_connect: %d\n", e);
                }
            }
            /* Wait between attempts, and leave the radio alone while doing
             * it. On a Pico W the LED hangs off the wireless chip, so every
             * cyw43_arch_gpio_put() is an SPI transaction that takes the
             * driver lock — blinking it during a handshake is contending
             * with the very thing we are waiting for. One short flash per
             * cycle is enough to show a person what is happening. */
            led_set(true);
            sleep_ms(40);
            led_set(false);
            sleep_ms(2960);
            continue;
        }

        /* Say what state we are in even if nobody was listening at boot —
         * pico-sdk discards printf with no terminal attached, so a late
         * listener would otherwise see nothing at all. */
        if (absolute_time_diff_us(get_absolute_time(), next_report) <= 0) {
            printf("up: body=%s wifi=%s mqtt=%s\n", body_id,
                   ip4addr_ntoa(netif_ip4_addr(netif_default)),
                   mqtt_client_is_connected(client) ? "connected" : "dropped");
            if (!mqtt_client_is_connected(client)) mqtt_up = false;
            next_report = delayed_by_ms(get_absolute_time(), 5000);
        }
        sleep_ms(50);
    }
}
