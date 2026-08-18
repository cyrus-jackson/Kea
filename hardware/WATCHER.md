# Kea — the wireless watcher

A battery camera that sleeps, wakes when its PIR sees something, sends
one frame to Kea, and goes back to sleep.

## Parts

| Part | Why this one | Approx |
|---|---|---|
| **Seeed XIAO ESP32S3 Sense** | USB-C, LiPo charging on board, OV2640, ~14 µA deep sleep | €18 |
| **1× 3.7 V LiPo, 1000 mAh** | plugs into the XIAO's battery pads | €8 |
| **AM312 PIR** | 3.3 V native, ~12 µA idle | €3 |

**Not the AI-Thinker ESP32-CAM**, the board everyone means by "ESP32
camera". It has no power gating and idles near 3 mA, which loses to the
XIAO *on twice the battery*. It also needs an external USB-serial adapter
to flash. It is cheaper and wrong.

**No separate UPS.** The XIAO charges the cell whenever USB is connected,
so the LiPo already is one: plugged in it runs and charges, unplugged it
keeps going. Buying a UPS as well would be paying twice for the same
behaviour.

**Not AAs.** They cannot recharge in place, they need a regulator to get
to 3.3 V, and alkalines sag under the ~240 mA pulses that WiFi
transmission draws — the same internal-resistance problem the servos hit.

## Battery, honestly

One wake-capture-upload cycle is about **0.27 mAh** (≈4 s at ≈240 mA).
Deep sleep is 14 µA. So on a 1000 mAh cell:

| Behaviour | Life |
|---|---|
| ~10 triggers/day | **300+ days** |
| every 10 minutes | 26 days |
| every minute | 2.6 days |
| awake, streaming | 4 hours |

**Sleep current decides this, not resolution or capture rate.** Which is
why the one line that matters in the firmware is `esp_camera_deinit()`
before sleeping: leave the sensor powered and a "14 µA" node measures
nearer a milliamp, and the month becomes a week. Several people have
reported exactly that on Seeed's forum — measure yours before believing
the table above.

## Wiring

```
   AM312 PIR          XIAO ESP32S3 Sense
   ─────────          ──────────────────
   VCC  ───────────►  3V3
   OUT  ───────────►  D1  (GPIO2, ext0 wake)
   GND  ───────────►  GND

   LiPo  ──────────►  BAT+ / BAT- pads on the underside
   USB-C ──────────►  charges the cell and runs the board
```

## The Pi side

```bash
export KEA_WATCHER_TOKEN='pick-something-long'
export KEA_WATCHER_PORT=842        # optional
```

The token is **required** — with none set the server refuses to start
rather than running an open image-upload endpoint on your network. It is
compared with `hmac.compare_digest`, which stops something else on the
LAN posting junk into your dataset; it is plain HTTP, so it does not stop
anyone who can read your traffic. **Do not port-forward it.**

Put the same values in `watcher.ino`, flash, and the node appears.

## What happens to a frame

It goes through `backend/dataset.py` exactly like one Kea took itself:
sidecar JSON written first, then the image, then the same encrypted
rclone offload. A watcher frame is indistinguishable downstream from a
built-in one, which is the point — one dataset, one pipeline.

Motion also raises a Kea alert, rate-limited to one per 20 s and
self-expiring after two minutes. A PIR pointed at a doorway during a
conversation fires every few seconds; alerting on each would make the
screen useless and teach you to ignore it. And "the door opened an hour
ago" is news that expires, unlike "call the landlord", so it clears
itself rather than silting up the Docket.

## Why the node pushes and Kea never asks

The intuitive design is "Kea requests a picture". It is also the design
that kills the battery: to answer, the node must be awake and listening,
so no deep sleep, so four hours instead of months.

The node owns the schedule. Kea can leave one instruction in the reply to
a POST, which the node collects on its **next** wake — so "on demand"
honestly means "within one trigger". If you need true on-demand, that
node wants USB power, and then none of this page applies.
