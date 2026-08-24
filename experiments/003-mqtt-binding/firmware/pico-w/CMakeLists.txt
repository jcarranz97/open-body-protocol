# OBP body on a Raspberry Pi Pico W — the MQTT binding.
#
#   export PICO_SDK_PATH=~/repos/pico-sdk
#   cmake -B build -DPICO_BOARD=pico_w \
#         -DWIFI_SSID="your-ssid" -DWIFI_PASSWORD="your-password" \
#         -DMQTT_BROKER="192.168.1.x"
#   cmake --build build          # -> build/obp_body_mqtt.uf2
#
# Nothing secret is committed: the credentials live on your command line and
# are baked into the binary, which is fine for an experiment on a desk and
# not how a real body should be provisioned.
cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD pico_w CACHE STRING "pico_w or pico2_w — this body needs wireless")

include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)
project(obp_body_mqtt C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()

if(NOT DEFINED WIFI_SSID OR NOT DEFINED WIFI_PASSWORD)
    message(FATAL_ERROR
        "Set -DWIFI_SSID=\"...\" and -DWIFI_PASSWORD=\"...\" when configuring.")
endif()
if(NOT DEFINED MQTT_BROKER)
    message(FATAL_ERROR
        "Set -DMQTT_BROKER=\"192.168.1.x\" — the IP of the machine running the broker.")
endif()

add_executable(obp_body_mqtt main.c json_min.c)

target_compile_definitions(obp_body_mqtt PRIVATE
    WIFI_SSID=\"${WIFI_SSID}\"
    WIFI_PASSWORD=\"${WIFI_PASSWORD}\"
    MQTT_BROKER=\"${MQTT_BROKER}\"
)

target_include_directories(obp_body_mqtt PRIVATE ${CMAKE_CURRENT_LIST_DIR})

target_link_libraries(obp_body_mqtt
    pico_stdlib
    pico_unique_id
    hardware_watchdog
    pico_cyw43_arch_lwip_threadsafe_background
    pico_lwip_mqtt
)

# USB serial carries the body's own log — join the port to watch it connect.
pico_enable_stdio_usb(obp_body_mqtt 1)
pico_enable_stdio_uart(obp_body_mqtt 0)

pico_add_extra_outputs(obp_body_mqtt)
