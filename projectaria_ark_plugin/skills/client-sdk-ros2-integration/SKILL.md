---
name: client-sdk-ros2-integration
description: Use when integrating Aria Gen 2 sensor streams with ROS2 — publishing raw Aria sensor data through ROS2 topics, decoding it in subscriber nodes, sharing device calibration across nodes. The integration uses a custom `AriaRaw` message (a thin FlatBuffer wrapper) and a required `aria_data_types` package name. Use whenever the user asks about Aria + ROS2, publishing Aria data to topics, or building ROS2 nodes around Aria sensors.
---

# Aria + ROS2 Integration

The Client SDK ships an example ROS2 publisher / subscriber pair that streams raw Aria sensor data through ROS2 topics. Sensor messages stay in FlatBuffer format end-to-end — a thin custom message type (`AriaRaw`) carries them on the wire, and the SDK's data converter decodes them in the subscriber.

> Reference + full code walkthrough: https://facebookresearch.github.io/projectaria_tools/gen2/ark/client-sdk/python-sdk/ros2-example

## Why a custom message type

Aria streams data in FlatBuffer format. Re-encoding into standard `sensor_msgs/*` types would:

1. Lose timing precision — nanosecond timestamps survive better in raw bytes.
2. Force one publisher per sensor type — Aria has many sensors, that's a lot of plumbing.
3. Break when new sensor types are added.

So the example uses **one** `AriaRaw` topic for all sensors, carrying:

```msg
int64 id        # SDK message type ID (indicates which sensor / message type)
uint8[] payload # raw FlatBuffer bytes
```

The subscriber uses `aria.oss_data_converter.OssDataConverter` to decode each payload into a typed Python object (NumPy image, IMU struct, eye-gaze object, etc.) based on the `id`.

## Critical constraint: the custom-message package MUST be named `aria_data_types`

Both example files import:

```python
from aria_data_types.msg import AriaRaw
```

Any other package name fails with `ImportError`. The `aria_data_types` package contains only the `AriaRaw.msg` definition.

## Prerequisites

- Client SDK installed in a virtual environment (see the `client-sdk` skill).
- Device authenticated: `aria_gen2 auth pair`.
- ROS2 (Humble or later) installed, with a workspace (e.g. `~/ros2_ws`).
- C++ compiler for building the custom message package.

## Workflow

```
1. Extract SDK samples       python3 -m aria.extract_sdk_samples --out ~/Downloads
                              → yields AriaRaw.msg, ros2_publisher_example.py,
                                ros2_subscriber_example.py
2. Create C++ package        aria_data_types  (with AriaRaw.msg)
                              — follow the standard ROS2 custom-message tutorial
3. Create Python package     e.g. py_pubsub  (publisher + subscriber nodes)
4. Copy example code         ros2_publisher_example.py → publisher_member_function.py
                             ros2_subscriber_example.py → subscriber_member_function.py
5. Add to py_pubsub/package.xml:
                             <exec_depend>aria_data_types</exec_depend>
6. BUILD aria_data_types FIRST, then py_pubsub:
                             colcon build --packages-select py_pubsub
7. In BOTH terminals: export the same ROS_DOMAIN_ID
                             export ROS_DOMAIN_ID=0
8. Terminal A:  ros2 run py_pubsub talker    (publisher — connects to device)
   Terminal B:  ros2 run py_pubsub listener  (subscriber)
```

ROS2 tutorials referenced above:

- Custom messages: https://docs.ros.org/en/foxy/Tutorials/Beginner-Client-Libraries/Single-Package-Define-And-Use-Interface.html
- Python publisher / subscriber: https://docs.ros.org/en/foxy/Tutorials/Beginner-Client-Libraries/Writing-A-Simple-Py-Publisher-And-Subscriber.html

## How calibration flows

Several decoders (VIO, eye gaze, hand pose) need calibration to transform coordinates. The publisher:

1. Receives `device_calib` from the device on first connection.
2. Converts it to a JSON string via `projectaria_tools.core.calibration.device_calibration_to_json_string`.
3. Publishes it on the **`/calibration`** topic (queue size 100, **republished at 10 Hz** so late-joining subscribers still get it).

The subscriber:

1. Subscribes to `/calibration` and `/aria_raw_message`.
2. **Waits for calibration** before processing any sensor message (gates a global flag).
3. Once calibration arrives, calls `converter.set_calibration(json_str)`, then handles each raw message by switching on `message_id`.

> **If the subscriber receives data but logs nothing, it is almost always still waiting for calibration.** Check the publisher logs to confirm calibration was published.

## Topics and ports

- `aria_raw_message` (topic) — `AriaRaw`, queue size 1000.
- `calibration` (topic) — `std_msgs/String` (calibration JSON), queue size 100.
- **`:6768` (TCP)** — HTTP server inside the publisher that receives streamed data from the device. Single-binding per host — only one publisher can hold it at a time.

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `ImportError: aria_data_types` | Package not named `aria_data_types`, or not built before `py_pubsub` | Rename, then `colcon build` `aria_data_types` first |
| Subscriber receives messages but prints nothing | Calibration not received yet | Check publisher logs for the calibration callback |
| Publisher fails: port 6768 in use | Another viewer or example server is bound to the port | `lsof -i :6768`, kill the other process, or change `config.port` in the publisher script |
| Subscriber sees no messages at all | Different `ROS_DOMAIN_ID` between terminals | `export ROS_DOMAIN_ID=0` in both before running |
| `ros2 node list` shows only one node | `ROS_DOMAIN_ID` mismatch | Same fix |
| Many dropped messages | Queue size too small, slow callback, or wireless bandwidth | Increase queue, simplify callback, prefer USB streaming |

## Related plugin skills

- `client-sdk` — the underlying device control and streaming SDK.
- `aria-knowledge` — overall Aria platform / sensor concepts.
- `projectaria-tools` — calibration helpers used by the publisher.
