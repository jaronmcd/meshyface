# Test Reply plugin

This example replies to ordinary mesh messages that match configurable wildcard
patterns. It is intended for quick antenna checks and radio-link smoke tests:

```text
Incoming: testing new antenna
Reply:    3 hops to Saint Paul, MN
```

Enable it with:

```bash
python mesh_dashboard.py --plugins-enable --plugin-enable test_reply
```

Keep the rest of the arguments required by your radio and HTTP setup.

## Wildcard Triggers

The **Trigger patterns** setting is a comma-separated list of shell-style
wildcard patterns.
Matching is case-insensitive and runs against the whole incoming message.

```text
*test*, *ping*, antenna*
```

`*test*` catches messages such as `test`, `testing new antenna`, and
`can someone test this?`. `ping*` catches messages that start with `ping`.

The script also accepts one pattern per line if you copy it and prefer editing
the plugin files directly.

## Response Macros

The **Response template** setting can combine static text with these macros:
`{nearest_city}` is based on the sender's last known position, while
`{server_city}` is based on the local Meshyface node position when available.

```text
{hops}                 3 hops
{hop_count}            3
{hop_word}             hops
{nearest_city}         Saint Paul, MN
{city}                 Saint Paul
{state}                Minnesota
{country}              United States of America
{distance_km}          1.1 km
{sender}               Someone
{sender_short}         SMON
{sender_id}            !01020304
{snr}                  7.5 dB
{rssi}                 -81 dBm
{channel}              0
{text}                 testing new antenna
{matched}              *test*
{server_city}          Minneapolis, MN
```

Example templates:

```text
{hops} to {nearest_city}
{sender}: {hops}
{sender_short}: {hop_count} {hop_word}, SNR {snr}, RSSI {rssi}
```

Unknown values render as `unknown`, `unknown hops`, or `unknown city` so the bot
still gives a useful reply when a node has no recent position.
