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

/* one inbound message, reassembled from lwIP's fragments */
static char in_topic[TOPIC_MAX];
static char in_data[PAYLOAD_MAX];
static uint32_t in_len;
static bool in_overflow;

/* ------------------------------------------------------------------ body */

static void led_set(bool on) {
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, on);
}

static const char *DESCRIBE_FMT =
    "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"result\":{\"v\":0,"
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

static void publish(const char *topic, const char *payload, uint8_t qos, uint8_t retain) {
    cyw43_arch_lwip_begin();
    mqtt_publish(client, topic, payload, strlen(payload), qos, retain, NULL, NULL);
    cyw43_arch_lwip_end();
}

static void reply_text(long id, const char *text, bool is_error) {
    static char buf[512];
    snprintf(buf, sizeof buf,
             "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"result\":{\"content\":"
             "[{\"type\":\"text\",\"text\":\"%s\"}],\"isError\":%s}}",
             id, text, is_error ? "true" : "false");
    publish(t_reply, buf, 1, 0);
}

static void tool_call(long id, const char *params, size_t plen) {
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
            led_set(true);  sleep_ms((uint32_t)interval);
            led_set(false); sleep_ms((uint32_t)interval);
        }
        char msg[48];
        snprintf(msg, sizeof msg, "blinked %ld times", times);
        reply_text(id, msg, false);
        return;
    }

    if (strcmp(name, "reboot") == 0) {
        /* Clear our own retained presence before going, so the host is not
         * left waiting for the broker to notice the will. */
        publish(t_presence, "", 1, 1);
        sleep_ms(200);
        watchdog_reboot(0, 0, 0);
        return;
    }

    char msg[64];
    snprintf(msg, sizeof msg, "no such tool: %s", name);
    reply_text(id, msg, true);
}

static void handle_request(const char *json, size_t len) {
    long id = 0;
    jm_get_int(json, len, "id", &id);
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
        snprintf(buf, sizeof buf, "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"result\":{}}", id);
        publish(t_reply, buf, 1, 0);
    } else {
        static char buf[160];
        snprintf(buf, sizeof buf,
                 "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"error\":{\"code\":-32601,"
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
    if (status != MQTT_CONNECT_ACCEPTED) {
        printf("mqtt connect failed: %d\n", status);
        return;
    }
    printf("mqtt connected\n");
    cyw43_arch_lwip_begin();
    mqtt_subscribe(client, t_rpc, 1, NULL, NULL);
    cyw43_arch_lwip_end();
    announce_presence();
    /* Three quick flashes: connected, subscribed, and announced. */
    for (int i = 0; i < 3; i++) {
        led_set(true);  sleep_ms(60);
        led_set(false); sleep_ms(60);
    }
}

int main(void) {
    stdio_init_all();
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

    printf("joining %s ...\n", WIFI_SSID);
    if (cyw43_arch_wifi_connect_timeout_ms(WIFI_SSID, WIFI_PASSWORD,
                                           CYW43_AUTH_WPA2_AES_PSK, 30000)) {
        printf("wifi failed\n");
        return 1;
    }
    printf("wifi ok, ip %s\n", ip4addr_ntoa(netif_ip4_addr(netif_default)));

    ip_addr_t broker;
    if (!ip4addr_aton(MQTT_BROKER, &broker)) {
        printf("bad broker address: %s\n", MQTT_BROKER);
        return 1;
    }

    /* The presence mechanism: a will with an EMPTY retained payload, which
     * clears the retained announcement when this body stops answering. */
    struct mqtt_connect_client_info_t ci = {0};
    ci.client_id = body_id;
    ci.keep_alive = 20;
    ci.will_topic = t_presence;
    ci.will_msg = "";
    ci.will_qos = 1;
    ci.will_retain = 1;

    client = mqtt_client_new();
    mqtt_set_inpub_callback(client, incoming_publish_cb, incoming_data_cb, NULL);

    cyw43_arch_lwip_begin();
    mqtt_client_connect(client, &broker, MQTT_PORT, connection_cb, NULL, &ci);
    cyw43_arch_lwip_end();

    while (true) {
        cyw43_arch_poll();
        sleep_ms(10);
    }
}
