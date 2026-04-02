# Channels, frequency slots, and chat scope

Doc status: active-runtime
Last reviewed: 2026-03-14

Meshtastic is an adorable pile of radio + crypto + mesh routing… and it reuses the word **“channel”** for multiple things.
This doc tries to make the dashboard’s behavior *obvious* to a beginner.

## The 3 different “channel” concepts

| Concept | Where you see it in Meshyface | What it controls | Do other nodes need to match? |
|---|---|---|---|
| **Frequency slot** (LoRa physical frequency) | **Settings → LoRa → Frequency slot** (`lora.channel_num`) | The actual RF frequency your radio transmits/receives on | **Yes**. If this doesn’t match, you won’t hear each other at all. |
| **Messaging channels** (Meshtastic channel index `0..7`) | **Chat header → View Ch / Send Ch** and **Settings → Channels** | Which *message group / encryption key* is used for a packet | **Yes** for reading messages: recipients need the same channel index + PSK to decrypt. |
| **Chat scope** (“Everyone” vs “Peer-to-peer”) | Chat left rail | The destination: broadcast (`^all`) vs a specific node (`!abcd1234`) | N/A (this is just “who you’re talking to”) |

### Key mental model

- Your radio is basically **one LoRa modem** configured with one set of physical parameters (region, preset, frequency slot, etc.).
- Meshtastic “messaging channels” are **virtual**: they’re mostly about *encryption keys* and grouping, not extra radios.

## How sending works in this dashboard

When you press **Send**:

1. The UI chooses a destination:
   - **Everyone** → `^all`
   - **Peer-to-peer** → the selected node id like `!abcdef12`
2. The UI chooses a Meshtastic **send channel index** from **Send Ch**.
   - **View Ch** is only a feed filter.
   - If you pick a specific View Ch, the dashboard can follow that into Send Ch for convenience.
   - If you pick **All channels (view)**, Send Ch remains independently selectable.
3. The backend calls the Meshtastic Python API with `channelIndex=<that index>`.

## How receiving works (and why “receive everything” is tricky)

- Your radio will **physically receive** LoRa packets on its configured frequency slot.
- To *show you the message text*, it must be able to **decrypt** the payload using one of its configured channel PSKs.

So:

- You *can* “receive everything you have keys for” by configuring multiple channels on your radio.
- You *cannot* decrypt/read traffic for channels you don’t know.

This is also why you might still see “activity” in graphs/packet counts even if chat text is missing: the mesh can relay packets it can’t decrypt.

## Channel settings: Role, PSK, Uplink/Downlink

In **Settings → Channels**, each row is one Meshtastic channel slot.

- **Role**
  - `PRIMARY` (index 0): exactly one, cannot be disabled.
  - `SECONDARY` (index 1–7): optional additional message groups.
  - `DISABLED`: unused slot.

- **PSK** (Pre-Shared Key)
  - This is the encryption key for that channel.
  - Nodes must share the same PSK on the same channel index to read each other’s messages on that channel.

- **Uplink / Downlink**
  - These are **MQTT bridge toggles**, not “LoRa TX/RX”.
  - In the dashboard UI they are hidden unless you enable **Advanced channel options**.
  - If you run a node with internet connectivity + MQTT configured, these flags control whether packets on that channel are bridged:
    - **Uplink**: mesh → MQTT
    - **Downlink**: MQTT → mesh

## Simple mode quick actions (dashboard UI)

The Channels panel also has a beginner-friendly set of shortcuts:

- **Join from Channel URL (QR)**
  - Paste a Meshtastic share URL (the same thing you’d scan as a QR code in the mobile apps).
  - This applies **LoRa + channel** settings from the URL and may reboot the radio.
  - Only paste URLs from people you trust.

- **Create private channel (random key)**
  - Adds the next available `SECONDARY` channel slot with a random PSK.
  - You can share it using **Copy Channel URL (all)** (requires `--show-secrets`).

- **Advanced channel options**
  - Reveals MQTT bridge toggles (Uplink/Downlink) and other power-user details.

## Why the UI enforces “consecutive channels” and “disable from the end”

Meshtastic channel slots are indexed. To keep things predictable (and to match common device behavior), Meshyface enforces:

- Channels are treated as consecutive: `0..N`
- You disable channels from the end (highest active index) to avoid gaps
- You add channels in the next available disabled slot

This reduces “mystery states” where different tools disagree about which slots are active.

## FAQ

### Can I “send to all channels”?

Not in one packet. A packet has exactly **one** channel index.

You *could* implement “send to all” by sending the same message N times (once per channel), but that:

- multiplies airtime (more collisions, more battery)
- increases the chance you hit duty-cycle / regulatory limits
- produces duplicates for anyone who is joined to multiple of those channels

So Meshyface treats “All channels” as a **view filter**, not a transmit mode.

### Do secondary channels have their own frequency?

No. Secondary channels are for encryption/auth/grouping.
All channels share the same LoRa modem config (including frequency slot).

### Why does changing Channel 0 name sometimes break comms?

If **Frequency slot** is unset (`0`), Meshtastic can derive the slot using a channel-name-hash algorithm.
So renaming Channel 0 can indirectly change the physical frequency slot.

If you want stability, explicitly set **Settings → LoRa → Frequency slot**.

## System diagram

```mermaid
flowchart LR
  UI[Browser UI] -->|POST /api/chat/send\n(dest + channel_index + text)| Dash[Dashboard backend]
  Dash -->|meshtastic iface.sendText\n(channelIndex=...)| Radio[Local Meshtastic node]
  Radio -->|LoRa TX\n(region + preset + frequency slot)| Air((LoRa air))
  Air --> Other[Other radios\non same frequency slot]
  Other -->|Decrypt if they share\nchannel index + PSK| TheirUI[Their apps / UIs]
  Air -->|LoRa RX| Radio
  Radio -->|decoded packets| Dash
  Dash --> UI

  subgraph Optional MQTT bridge
    Radio <-->|Uplink/Downlink per channel| MQTT[(MQTT server)]
  end
```
