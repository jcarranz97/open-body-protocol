/* Minimal lwIP configuration for a Pico W speaking MQTT.
 * Derived from the pico-examples defaults; MQTT-specific sizes at the end. */
#ifndef _LWIPOPTS_H
#define _LWIPOPTS_H

#define NO_SYS                      1
#define LWIP_SOCKET                 0
#define MEM_LIBC_MALLOC             0
#define MEM_ALIGNMENT               4
/* The MQTT client is allocated from this heap, and MQTT_OUTPUT_RINGBUF_SIZE
 * lives *inside* that allocation. At the vendor's default of 4000 with our
 * 2048-byte ring buffer, more than half the heap was gone before the first
 * packet and tcp_write failed with ERR_MEM while TCP had 11 KB of window
 * free — a 60-byte CONNECT that never left the board.
 *
 * A Pico W has 264 KB of RAM; being frugal here bought nothing. */
#define MEM_SIZE                    16000
#define MEMP_NUM_TCP_SEG            32
#define MEMP_NUM_ARP_QUEUE          10
#define PBUF_POOL_SIZE              32
#define LWIP_ARP                    1
#define LWIP_ETHERNET               1
#define LWIP_ICMP                   1
#define LWIP_RAW                    1
#define TCP_WND                     (8 * TCP_MSS)
#define TCP_MSS                     1460
#define TCP_SND_BUF                 (8 * TCP_MSS)
#define TCP_SND_QUEUELEN            ((4 * (TCP_SND_BUF) + (TCP_MSS - 1)) / (TCP_MSS))
#define LWIP_NETIF_STATUS_CALLBACK  1
#define LWIP_NETIF_LINK_CALLBACK    1
#define LWIP_NETIF_HOSTNAME         1
#define LWIP_NETCONN                0
#define MEM_STATS                   0
#define SYS_STATS                   0
#define MEMP_STATS                  0
#define LINK_STATS                  0
#define LWIP_CHKSUM_ALGORITHM       3
#define LWIP_DHCP                   1
#define LWIP_IPV4                   1
#define LWIP_TCP                    1
#define LWIP_UDP                    1
#define LWIP_DNS                    1
#define LWIP_TCP_KEEPALIVE          1
#define LWIP_NETIF_TX_SINGLE_PBUF   1
#define DHCP_DOES_ARP_CHECK         0
#define LWIP_DHCP_DOES_ACD_CHECK    0

/* MQTT allocates its own cyclic timeout, and lwIP sizes MEMP_SYS_TIMEOUT
 * from its *internal* modules only — so an application that adds timers
 * exhausts the pool and panics with
 *     sys_timeout: timeout != NULL, pool MEMP_SYS_TIMEOUT is empty
 * which is precisely how the second build of this firmware died, one line
 * after joining the network. */
#define MEMP_NUM_SYS_TIMEOUT        (LWIP_NUM_SYS_TIMEOUT_INTERNAL + 4)

/* MQTT: a describe response is ~1.4 KB, so give the client room for it. */
#define MQTT_OUTPUT_RINGBUF_SIZE    2048
#define MQTT_VAR_HEADER_BUFFER_LEN  512
#define MQTT_REQ_MAX_IN_FLIGHT      8

/* Debugging. The vendor's example config enables LWIP_DEBUG and we did not;
 * with MQTT_DEBUG on, lwIP narrates its own connect path over stdout, which
 * beats inferring it from a broker log. */
#define LWIP_DEBUG                  1
#define LWIP_STATS                  1
#define MQTT_DEBUG                  LWIP_DBG_ON
#define TCP_DEBUG                   LWIP_DBG_OFF
#define TCP_INPUT_DEBUG             LWIP_DBG_OFF
#define TCP_OUTPUT_DEBUG            LWIP_DBG_OFF
#define ETHARP_DEBUG                LWIP_DBG_OFF
#define DHCP_DEBUG                  LWIP_DBG_OFF
#define IP_DEBUG                    LWIP_DBG_OFF
#define MEM_DEBUG                   LWIP_DBG_OFF
#define MEMP_DEBUG                  LWIP_DBG_OFF
#define PBUF_DEBUG                  LWIP_DBG_OFF
#define NETIF_DEBUG                 LWIP_DBG_OFF
#define SYS_DEBUG                   LWIP_DBG_OFF

#endif
