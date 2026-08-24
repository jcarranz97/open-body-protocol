# OBP body contract -- pico-sdk (C) firmware for experiment 005.
#
# Adds a debounced push button on GP14 (physical pin 19, next to GND on pin
# 18) that emits notifications/body/event -- the body speaking first.
#
#   export PICO_SDK_PATH=~/pico/pico-sdk
#   cmake -B build -DPICO_BOARD=pico        # or pico_w / pico2 / pico2_w
#   cmake --build build
#   -> build/obp_body.uf2
cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD pico CACHE STRING "Board: pico | pico_w | pico2 | pico2_w")

include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(obp_body C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(obp_body
    main.c
    json_min.c
    button.c
    event_id.c
)

target_link_libraries(obp_body
    pico_stdlib
    pico_unique_id
    hardware_pwm
    pico_rand
)

# Pico W / Pico 2 W drive the onboard LED through the wireless chip.
if(PICO_BOARD STREQUAL "pico_w" OR PICO_BOARD STREQUAL "pico2_w")
    target_link_libraries(obp_body pico_cyw43_arch_none)
endif()

# The body speaks over USB CDC. UART stdio is disabled so that a stray debug
# print cannot corrupt the JSON framing on the wire the host is reading.
pico_enable_stdio_usb(obp_body 1)
pico_enable_stdio_uart(obp_body 0)

pico_add_extra_outputs(obp_body)   # .uf2, .hex, .bin, .map
