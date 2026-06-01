# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
WebSocket bridge to stream Nebula data to frontend.

Receives data from MVP1 StreamReceiver and pushes to WebSocket clients.
"""

import asyncio
import base64
import concurrent.futures
import json
import logging
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from typing import Dict

import aria.sdk_gen2 as sdk_gen2
import aria.stream_receiver as stream_receiver
import cv2
import numpy as np
import websockets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Startup environment header ──
def _log_startup_header():
    logger.info("═" * 55)
    logger.info("  Web App Creator — WebSocket Bridge")
    logger.info("═" * 55)
    logger.info(f"Python    : {platform.python_version()} ({platform.machine()})")
    logger.info(f"Platform  : {platform.platform()}")
    try:
        import projectaria_client_sdk

        logger.info(
            f"Aria SDK  : {getattr(projectaria_client_sdk, '__version__', 'unknown')}"
        )
    except Exception:
        logger.info("Aria SDK  : version unavailable")
    logger.info(f"websockets: {websockets.__version__}")
    logger.info(f"Started   : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("═" * 55)


_log_startup_header()


class _ErrorRateLimiter:
    """Rate-limit repeated error messages to avoid log flooding."""

    def __init__(self, summary_interval: float = 60.0):
        self._counts: dict[str, int] = {}
        self._last_summary: float = time.time()
        self._summary_interval = summary_interval

    def should_log(self, error_key: str) -> bool:
        """Return True only for the first occurrence of each unique error."""
        if error_key not in self._counts:
            self._counts[error_key] = 1
            return True
        self._counts[error_key] += 1
        return False

    def flush_summary(self) -> str | None:
        """If enough time has passed, return a summary string and reset counts."""
        now = time.time()
        if now - self._last_summary < self._summary_interval:
            return None
        self._last_summary = now
        suppressed = {k: v for k, v in self._counts.items() if v > 1}
        if not suppressed:
            return None
        lines = [f"  {k}: {v} occurrences" for k, v in suppressed.items()]
        self._counts = {}
        return "Suppressed error summary (last 60s):\n" + "\n".join(lines)


# Valid stream types that clients can subscribe to
VALID_STREAM_TYPES = {
    "rgb_frame",
    "slam_frame",
    "et_frame",
    "eye_gaze",
    "hand_tracking",
    "vio",
    "imu",
    "audio",
    "ppg",
}

# Always-send types (sent regardless of subscription)
ALWAYS_SEND_TYPES = {"calibration", "device_status", "tts_sent", "subscription_update"}

# Binary frame type constants (byte 0 of binary WebSocket frames)
BINARY_FRAME_RGB = 0x01
BINARY_FRAME_SLAM = 0x02
BINARY_FRAME_ET = 0x03


def _pack_binary_frame(
    frame_type: int, jpeg_bytes: bytes, camera_id: str = ""
) -> bytes:
    """Pack a binary WebSocket frame for image streams.

    Wire format:
        Byte 0:           frame type (BINARY_FRAME_RGB / SLAM / ET)
        Byte 1:           camera_id string length (0 for RGB)
        Bytes 2..2+N:     camera_id UTF-8 bytes
        Remaining bytes:  raw JPEG data
    """
    cam_bytes = camera_id.encode("utf-8") if camera_id else b""
    header = bytes([frame_type, len(cam_bytes)]) + cam_bytes
    return header + jpeg_bytes


class WebSocketBridge:
    """Bridge between Nebula StreamReceiver and WebSocket clients."""

    def __init__(self, port: int = 17300):
        self.port = port
        self.clients: Dict = {}  # websocket -> {"streams": set}
        self.receiver = None
        self.device_client = None  # For TTS sending
        self.device = None  # Device connection
        self.loop = None  # Will be set when event loop starts
        self._error_limiter = _ErrorRateLimiter()
        self.frame_stats = {
            "rgb": 0,
            "slam": 0,
            "eye_gaze": 0,
            "hand_tracking": 0,
            "imu": 0,
            "audio": 0,
            "vio": 0,
            "et": 0,
            "ppg": 0,
        }
        self._vio_ref_quat = None  # Reference quaternion for relative Euler angles
        self._gravity_align_quat = None  # Gravity alignment quaternion

        # Device pose history for timestamp-based lookup (for hand tracking)
        # Each entry: (timestamp_ns, pos, quat)
        self._device_pose_history = []
        self._device_pose_history_max = 100  # Keep last 100 poses (~1 second at 100Hz)

        # T_device_cpf: Transform from Device to CPF (Central Pupil Frame)
        # This is the calibration offset between IMU position and eye center
        # Default values from SDK - will be overwritten by SDK callback if available
        self._T_device_cpf_pos = np.array(
            [0.063, 0.019, -0.030]
        )  # Position offset [x, y, z]
        self._T_device_cpf_quat = np.array(
            [0.036, -0.168, 0.206, -0.963]
        )  # Rotation offset [w, x, y, z]

        # PPG signal processing for heart rate calculation
        self._ppg_buffer = []  # Buffer of (timestamp, value) tuples
        self._ppg_buffer_duration = 15.0  # Keep 15 seconds of data for better averaging
        self._ppg_last_hr = None  # Last calculated heart rate
        self._ppg_last_hr_time = 0  # Time of last HR calculation
        self._ppg_hr_update_interval = 2.0  # Update HR every 2 seconds (slower updates)
        self._ppg_hr_history = []  # History of recent HR calculations for smoothing

        # Thread pool for image encoding (offloads from SDK callback thread)
        self._image_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="img-enc"
        )

        # Time-based throttle for IMU (device sends at ~880 Hz)
        self._imu_last_send_time = 0.0

        # Camera calibration data (for frontend 3D projection)
        self._camera_calibrations = {}  # Stores calibration data for each camera
        self._calibration_sent = False  # Track if calibration has been sent to clients

    async def register_client(self, websocket):
        """Register a new WebSocket client.

        New clients default to streams=set() (receive NOTHING until they send
        a 'subscribe' message).  Only always-send types (calibration,
        device_status) are delivered without subscription.
        """
        self.clients[websocket] = {"streams": set()}
        self._log_client_event("CONNECT", websocket, "streams=none (must subscribe)")

        # Send calibration message to new client if available
        await self._send_calibration_to_single_client(websocket)

        try:
            # Listen for incoming messages from client
            async for message in websocket:
                await self.handle_client_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.pop(websocket, None)
            self._log_client_event("DISCONNECT", websocket)

    def _log_client_event(self, event: str, websocket=None, detail: str = ""):
        """Log client event to both logger and logs/aria_clients.log."""
        import os

        # Build summary of all clients
        total = len(self.clients)
        active = set()
        for meta in self.clients.values():
            active |= meta["streams"]
        idle = VALID_STREAM_TYPES - active

        remote = ""
        if websocket:
            try:
                remote = f" remote={websocket.remote_address}"
            except Exception:
                pass

        line_parts = [
            f"[{event}]{remote}",
            f" {detail}" if detail else "",
            f" | clients={total}",
            f" active_streams={sorted(active)}",
            f" idle={sorted(idle)}" if idle else "",
        ]
        summary = "".join(line_parts)
        logger.info(summary)

        # Also write to dedicated client log file
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
            os.makedirs(log_dir, exist_ok=True)
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(os.path.join(log_dir, "aria_clients.log"), "a") as f:
                f.write(f"[{ts}] {summary}\n")
        except Exception:
            pass

    async def _send_calibration_to_single_client(self, websocket):
        """Send calibration message to a single WebSocket client."""
        calib_message = self.build_calibration_message()

        if calib_message is None:
            logger.debug("No calibration data available to send to new client")
            return

        try:
            import json

            message_str = json.dumps(calib_message)
            await websocket.send(message_str)
            logger.info(
                f"📤 Calibration message sent to new client ({len(self._camera_calibrations)} cameras)"
            )
        except Exception as e:
            logger.warning(f"Failed to send calibration to client: {e}")

    def has_subscribers(self, stream_type: str) -> bool:
        """Check if any connected client is subscribed to a given stream type."""
        for meta in self.clients.values():
            if stream_type in meta["streams"]:
                return True
        return False

    async def broadcast(self, message: str):
        """Broadcast message to all connected clients (always-send types)."""
        if not self.clients:
            return

        disconnected = []
        for client in self.clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(client)

        for client in disconnected:
            self.clients.pop(client, None)

    async def broadcast_stream(self, stream_type: str, message: str):
        """Broadcast a stream message only to subscribed clients.

        Args:
            stream_type: The stream type (e.g. 'vio', 'hand_tracking')
            message: JSON string to send
        """
        if not self.clients:
            return

        disconnected = []
        for client, meta in self.clients.items():
            if stream_type in meta["streams"]:
                try:
                    await client.send(message)
                except websockets.exceptions.ConnectionClosed:
                    disconnected.append(client)

        for client in disconnected:
            self.clients.pop(client, None)

    async def broadcast_binary_stream(self, stream_type: str, binary_data: bytes):
        """Broadcast binary data only to subscribed clients (WebSocket binary opcode).

        Args:
            stream_type: The stream type (e.g. 'rgb_frame', 'slam_frame', 'et_frame')
            binary_data: Raw bytes to send (packed binary frame)
        """
        if not self.clients:
            return

        disconnected = []
        for client, meta in self.clients.items():
            if stream_type in meta["streams"]:
                try:
                    await client.send(binary_data)
                except websockets.exceptions.ConnectionClosed:
                    disconnected.append(client)

        for client in disconnected:
            self.clients.pop(client, None)

    def on_rgb_frame(self, image_data, record):
        """Handle RGB camera frame.

        Submits image encoding to a thread pool so the SDK callback thread
        is never blocked.  The encoded frame is sent immediately to clients
        via asyncio.run_coroutine_threadsafe().
        """
        if image_data is None:
            return

        self.frame_stats["rgb"] += 1

        if not self.has_subscribers("rgb_frame"):
            return

        try:
            # Convert to numpy (must happen here — image_data may not survive cross-thread)
            if hasattr(image_data, "to_numpy_array"):
                img_array = image_data.to_numpy_array()
            elif hasattr(image_data, "to_numpy"):
                img_array = image_data.to_numpy()
            elif isinstance(image_data, np.ndarray):
                img_array = image_data
            else:
                return

            # Submit encoding to thread pool — callback returns immediately
            self._image_executor.submit(self._encode_and_send_rgb, img_array)
        except Exception as e:
            key = f"on_rgb_frame: {e}"
            if self._error_limiter.should_log(key):
                logger.error(f"Error in {key}")

    def _encode_and_send_rgb(self, img_array):
        """Encode RGB frame to JPEG and send immediately (runs in thread pool)."""
        try:
            if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)

            # Downsample for web (1408x1408 -> 704x704)
            height, width = img_array.shape[:2]
            downsampled = cv2.resize(img_array, (width // 2, height // 2))

            _, buffer = cv2.imencode(
                ".jpg", downsampled, [cv2.IMWRITE_JPEG_QUALITY, 85]
            )

            data = _pack_binary_frame(BINARY_FRAME_RGB, buffer.tobytes())
            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_binary_stream("rgb_frame", data), self.loop
                )
        except Exception as e:
            key = f"_encode_rgb: {e}"
            if self._error_limiter.should_log(key):
                logger.error(f"Error in {key}")

    def on_slam_frame(self, image_data, record):
        """Handle SLAM camera frame — offloaded to thread pool."""
        if image_data is None:
            return

        self.frame_stats["slam"] += 1

        if not self.has_subscribers("slam_frame"):
            return

        if self.frame_stats["slam"] <= 2:
            camera_id_raw = getattr(record, "camera_id", "unknown")
            logger.info(
                f"SLAM frame #{self.frame_stats['slam']}: camera_id={camera_id_raw} type={type(camera_id_raw)}"
            )

        try:
            if hasattr(image_data, "to_numpy_array"):
                img_array = image_data.to_numpy_array()
            elif hasattr(image_data, "to_numpy"):
                img_array = image_data.to_numpy()
            elif isinstance(image_data, np.ndarray):
                img_array = image_data
            else:
                return

            camera_id = str(getattr(record, "camera_id", "unknown"))
            self._image_executor.submit(
                self._encode_and_send_slam, img_array, camera_id
            )
        except Exception as e:
            key = f"on_slam_frame: {e}"
            if self._error_limiter.should_log(key):
                logger.error(f"Error in {key}")

    def _encode_and_send_slam(self, img_array, camera_id):
        """Encode SLAM frame and send immediately (runs in thread pool)."""
        try:
            height, width = img_array.shape[:2]
            downsampled = cv2.resize(img_array, (width // 2, height // 2))

            _, buffer = cv2.imencode(
                ".jpg", downsampled, [cv2.IMWRITE_JPEG_QUALITY, 70]
            )

            data = _pack_binary_frame(BINARY_FRAME_SLAM, buffer.tobytes(), camera_id)
            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_binary_stream("slam_frame", data), self.loop
                )
        except Exception as e:
            key = f"_encode_slam: {e}"
            if self._error_limiter.should_log(key):
                logger.error(f"Error in {key}")

    def on_et_frame(self, image_data, record):
        """Handle Eye Tracking camera frame — offloaded to thread pool."""
        if image_data is None:
            return

        self.frame_stats["et"] += 1

        if not self.has_subscribers("et_frame"):
            return

        if self.frame_stats["et"] <= 2:
            camera_id_raw = getattr(record, "camera_id", "unknown")
            logger.info(
                f"ET frame #{self.frame_stats['et']}: camera_id={camera_id_raw} type={type(camera_id_raw)}"
            )

        try:
            if hasattr(image_data, "to_numpy_array"):
                img_array = image_data.to_numpy_array()
            elif hasattr(image_data, "to_numpy"):
                img_array = image_data.to_numpy()
            elif isinstance(image_data, np.ndarray):
                img_array = image_data
            else:
                return

            camera_id = str(getattr(record, "camera_id", "unknown"))
            self._image_executor.submit(self._encode_and_send_et, img_array, camera_id)
        except Exception as e:
            key = f"on_et_frame: {e}"
            if self._error_limiter.should_log(key):
                logger.error(f"Error in {key}")

    def _encode_and_send_et(self, img_array, camera_id):
        """Encode ET frame and send immediately (runs in thread pool)."""
        try:
            height, width = img_array.shape[:2]
            downsampled = cv2.resize(img_array, (width // 2, height // 2))

            _, buffer = cv2.imencode(
                ".jpg", downsampled, [cv2.IMWRITE_JPEG_QUALITY, 70]
            )

            data = _pack_binary_frame(BINARY_FRAME_ET, buffer.tobytes(), camera_id)
            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_binary_stream("et_frame", data), self.loop
                )
        except Exception as e:
            key = f"_encode_et: {e}"
            if self._error_limiter.should_log(key):
                logger.error(f"Error in {key}")

    def on_eye_gaze(self, eye_gaze):
        """Handle eye gaze data."""
        if eye_gaze is None:
            return

        self.frame_stats["eye_gaze"] += 1

        if not self.has_subscribers("eye_gaze"):
            return

        # Extract timestamp and data
        timestamp = getattr(eye_gaze, "capture_timestamp_ns", time.time() * 1e9) / 1e9

        message = json.dumps(
            {
                "type": "eye_gaze",
                "timestamp": timestamp,
                "data": {
                    "yaw": eye_gaze.yaw if hasattr(eye_gaze, "yaw") else 0,
                    "pitch": eye_gaze.pitch if hasattr(eye_gaze, "pitch") else 0,
                    "depth": eye_gaze.depth if hasattr(eye_gaze, "depth") else None,
                },
            }
        )

        # Schedule broadcast in event loop (thread-safe)
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast_stream("eye_gaze", message), self.loop
            )

    def on_hand_tracking(self, hand_data):
        if hand_data is None:
            return

        self.frame_stats["hand_tracking"] += 1

        if not self.has_subscribers("hand_tracking"):
            return

        # Debug: Print hand_data structure on first call
        if self.frame_stats["hand_tracking"] == 1:
            logger.info(f"Hand data type: {type(hand_data)}")
            logger.info(f"Hand data dir: {dir(hand_data)}")
            if hasattr(hand_data, "__dict__"):
                logger.info(f"Hand data dict: {hand_data.__dict__}")

        # Extract timestamp
        timestamp = getattr(hand_data, "capture_timestamp_ns", time.time() * 1e9) / 1e9

        # Get HEAD pose for hand tracking (gravity aligned + SurrealToUnity + CPF applied)
        # From cheat sheet: Hand data needs to be transformed using HEAD pose:
        #   raw_unity = (x, y, -z)              ← Surreal → Unity
        #   rotated = head_quat × raw_unity     ← Rotate by HEAD quaternion
        #   world = rotated + head_pos          ← Translate by HEAD position
        head_pos = getattr(self, "_last_head_pos_for_hand", None)
        head_quat_xyzw = getattr(self, "_last_head_quat_xyzw_for_hand", None)

        # Debug: 打印 HEAD 姿态
        if self.frame_stats["hand_tracking"] <= 5:
            logger.info(f"Hand transform - head_pos (Unity World): {head_pos}")
            logger.info(
                f"Hand transform - head_quat [x,y,z,w] (Unity World): {head_quat_xyzw}"
            )

        # Extract hand joint positions
        hands = {}

        if hasattr(hand_data, "left_hand") and hand_data.left_hand:
            hands["left"] = self._extract_hand_joints(
                hand_data.left_hand, head_pos, head_quat_xyzw, "left"
            )

        if hasattr(hand_data, "right_hand") and hand_data.right_hand:
            hands["right"] = self._extract_hand_joints(
                hand_data.right_hand, head_pos, head_quat_xyzw, "right"
            )

        message = json.dumps(
            {
                "type": "hand_tracking",
                "timestamp": timestamp,
                "data": hands,
            }
        )

        # Schedule broadcast in event loop (thread-safe)
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast_stream("hand_tracking", message), self.loop
            )

    def _extract_hand_joints(
        self, hand, head_pos=None, head_quat_xyzw=None, hand_side="left"
    ) -> dict:
        """Extract joint positions from hand data and transform to world coordinates.

        Hand landmarks are in device coordinates (Surreal).
        From cheat sheet, we need to:
        1. Step1: raw_surreal = original landmark position
        2. Step2: raw_unity = (x, y, -z)              ← Surreal → Unity conversion
        3. Step3: rotated = head_quat × raw_unity     ← Rotate by HEAD quaternion
        4. Step4: world = rotated + head_pos          ← Translate by HEAD position

        Note: head_quat_xyzw is already in [x,y,z,w] format for Unity rotation.
        """
        joints = []
        debug_info = None  # 只对第一个关节记录调试信息

        def quat_rotate_vec_xyzw(q_xyzw, v):
            """Rotate vector v by quaternion q in [x,y,z,w] format (Unity convention).

            Formula: v' = v + 2w(u×v) + 2(u×(u×v)) where u=[x,y,z], w=w
            """
            qx, qy, qz, qw = q_xyzw
            u = np.array([qx, qy, qz])
            t = 2.0 * np.cross(u, v)
            return v + qw * t + np.cross(u, t)

        # Get all 21 landmark positions (fingertips, joints, wrist, palm)
        if hasattr(hand, "landmark_positions_device"):
            landmarks = hand.landmark_positions_device
            for i, landmark in enumerate(landmarks):
                # 原始数据 (Surreal 坐标系) - 完全不做任何转换
                raw_surreal = np.array(
                    [float(landmark[0]), float(landmark[1]), float(landmark[2])]
                )

                if i == 0 and self.frame_stats["hand_tracking"] <= 3:
                    logger.info(
                        f"RAW landmark_device (Surreal, no transform): {raw_surreal}"
                    )

                # Step 2: Surreal → Unity coordinate conversion
                # (x, y, z) → (x, y, -z)
                pos_unity = np.array(
                    [
                        float(landmark[0]),  # X stays same
                        float(landmark[1]),  # Y stays same
                        -float(landmark[2]),  # Z negated
                    ]
                )

                # Step 3 & 4: Transform to world using HEAD pose
                # From cheat sheet:
                #   rotated = head_quat × raw_unity
                #   world = rotated + head_pos
                pos_rotated = None
                if head_pos is not None and head_quat_xyzw is not None:
                    pos_rotated = quat_rotate_vec_xyzw(head_quat_xyzw, pos_unity)
                    pos_world = pos_rotated + head_pos
                else:
                    pos_world = pos_unity

                # 只对第一个关节记录调试信息 (matching cheat sheet format)
                if i == 0:
                    debug_info = {
                        "joint_id": 0,
                        "joint_name": "THUMB_FINGERTIP",  # First joint in cheat sheet
                        "step1_raw_surreal": {
                            "x": float(raw_surreal[0]),
                            "y": float(raw_surreal[1]),
                            "z": float(raw_surreal[2]),
                        },
                        "step2_raw_unity": {
                            "x": float(pos_unity[0]),
                            "y": float(pos_unity[1]),
                            "z": float(pos_unity[2]),
                        },
                        "head_pos": (
                            {
                                "x": float(head_pos[0]),
                                "y": float(head_pos[1]),
                                "z": float(head_pos[2]),
                            }
                            if head_pos is not None
                            else None
                        ),
                        "head_quat_xyzw": (
                            {
                                "x": float(head_quat_xyzw[0]),
                                "y": float(head_quat_xyzw[1]),
                                "z": float(head_quat_xyzw[2]),
                                "w": float(head_quat_xyzw[3]),
                            }
                            if head_quat_xyzw is not None
                            else None
                        ),
                        "step3_rotated": (
                            {
                                "x": float(pos_rotated[0]),
                                "y": float(pos_rotated[1]),
                                "z": float(pos_rotated[2]),
                            }
                            if pos_rotated is not None
                            else None
                        ),
                        "step4_world": {
                            "x": float(pos_world[0]),
                            "y": float(pos_world[1]),
                            "z": float(pos_world[2]),
                        },
                    }

                # Final output: Apply X mirror to match VIO (替代前端scaleX(-1))
                joints.append(
                    {
                        "id": i,
                        "position": {
                            "x": -float(pos_world[0]),  # X negated (镜像效果)
                            "y": float(pos_world[1]),
                            "z": float(pos_world[2]),
                        },
                    }
                )

        # Get confidence
        confidence = getattr(hand, "confidence", 0.0)

        # Detect pinch gesture (thumb tip to index tip distance)
        # Joint indices based on Surreal SDK:
        # 0 = THUMB_TIP, 1 = INDEX_TIP (matching Developer Hub)
        is_pinching = False
        pinch_distance = None
        PINCH_THRESHOLD = 0.03  # 3cm threshold, matching Developer Hub

        if len(joints) >= 2:
            thumb_tip = joints[0]["position"]  # THUMB_TIP
            index_tip = joints[1]["position"]  # INDEX_TIP
            dx = thumb_tip["x"] - index_tip["x"]
            dy = thumb_tip["y"] - index_tip["y"]
            dz = thumb_tip["z"] - index_tip["z"]
            pinch_distance = (dx**2 + dy**2 + dz**2) ** 0.5
            is_pinching = pinch_distance < PINCH_THRESHOLD

        # Detect thumbs up gesture
        # Joint indices: 0=THUMB_TIP, 7=THUMB_MCP, 1=INDEX_TIP, 10=INDEX_MCP,
        # 2=MIDDLE_TIP, 13=MIDDLE_MCP, 3=RING_TIP, 16=RING_MCP, 4=PINKY_TIP, 19=PINKY_MCP
        # Additional joints: 5=WRIST, 6=THUMB_IP, 20=PALM_CENTER
        is_thumbs_up = False
        thumbs_up_debug = {}
        is_pointing = False
        pointing_debug = {}
        THUMBS_UP_MARGIN = 0.005  # 0.5cm margin for thumb extension

        if len(joints) >= 21:
            # Get thumb positions
            thumb_tip = joints[0]["position"]  # THUMB_TIP
            thumb_mcp = joints[7]["position"]  # THUMB_MCP

            # Get finger tip positions
            index_tip = joints[1]["position"]  # INDEX_TIP
            middle_tip = joints[2]["position"]  # MIDDLE_TIP
            ring_tip = joints[3]["position"]  # RING_TIP
            pinky_tip = joints[4]["position"]  # PINKY_TIP

            # Get palm center for reference (wrist = joints[5])
            palm_center = joints[20]["position"]  # PALM_CENTER

            # Helper function to calculate 3D distance
            def calc_distance(p1, p2):
                return (
                    (p1["x"] - p2["x"]) ** 2
                    + (p1["y"] - p2["y"]) ** 2
                    + (p1["z"] - p2["z"]) ** 2
                ) ** 0.5

            # Thumb should be extended upward (tip Y > mcp Y)
            thumb_extended_up = thumb_tip["y"] > thumb_mcp["y"] + THUMBS_UP_MARGIN

            # For finger curl detection, we check if fingertips are close to palm center
            # When fingers are curled (fist), tips are close to palm
            # When fingers are extended, tips are far from palm
            # From real data: curled ~2-3.5cm from palm, extended ~8.5-9.5cm from palm
            CURL_PALM_THRESHOLD = 0.055  # 5.5cm - fingers curled if tip-to-palm < this

            # Calculate tip-to-palm distances for each finger
            index_tip_to_palm = calc_distance(index_tip, palm_center)
            middle_tip_to_palm = calc_distance(middle_tip, palm_center)
            ring_tip_to_palm = calc_distance(ring_tip, palm_center)
            pinky_tip_to_palm = calc_distance(pinky_tip, palm_center)

            # A finger is considered curled if its tip is close to the palm center
            index_curled = index_tip_to_palm < CURL_PALM_THRESHOLD
            middle_curled = middle_tip_to_palm < CURL_PALM_THRESHOLD
            ring_curled = ring_tip_to_palm < CURL_PALM_THRESHOLD
            pinky_curled = pinky_tip_to_palm < CURL_PALM_THRESHOLD

            # Thumbs up requires: thumb extended upward, other fingers curled, AND NOT pinching
            is_thumbs_up = (
                thumb_extended_up
                and index_curled
                and middle_curled
                and ring_curled
                and pinky_curled
                and (not is_pinching)
            )

            # Store debug info to send to frontend
            thumbs_up_debug = {
                "thumbExtendedUp": thumb_extended_up,
                "indexCurled": index_curled,
                "middleCurled": middle_curled,
                "ringCurled": ring_curled,
                "pinkyCurled": pinky_curled,
                "thumbTipY": round(thumb_tip["y"], 3),
                "thumbMcpY": round(thumb_mcp["y"], 3),
                "indexTipToPalm": round(index_tip_to_palm, 3),
                "middleTipToPalm": round(middle_tip_to_palm, 3),
                "ringTipToPalm": round(ring_tip_to_palm, 3),
                "pinkyTipToPalm": round(pinky_tip_to_palm, 3),
                "curlThreshold": CURL_PALM_THRESHOLD,
            }

            # Detect pointing gesture (👈)
            # Pointing requires: index finger extended, thumb extended, other fingers curled
            # This is direction-agnostic, only checks finger states
            EXTEND_PALM_THRESHOLD = (
                0.065  # 6.5cm - finger extended if tip-to-palm > this
            )

            # Calculate thumb tip to palm distance for thumb extension check
            thumb_tip_to_palm = calc_distance(thumb_tip, palm_center)

            # Check if index and thumb are extended (far from palm)
            index_extended = index_tip_to_palm > EXTEND_PALM_THRESHOLD
            thumb_extended = thumb_tip_to_palm > EXTEND_PALM_THRESHOLD

            # Pointing: index extended, thumb extended, middle/ring/pinky curled
            is_pointing = (
                index_extended
                and thumb_extended
                and middle_curled
                and ring_curled
                and pinky_curled
                and (not is_pinching)
            )

            # Determine pointing direction (relative to head/device)
            # Calculate direction vector from index MCP to index TIP
            pointing_direction = None
            if is_pointing:
                index_mcp = joints[10]["position"]  # INDEX_MCP
                # Direction vector: tip - mcp
                dir_x = index_tip["x"] - index_mcp["x"]
                dir_y = index_tip["y"] - index_mcp["y"]
                dir_z = index_tip["z"] - index_mcp["z"]

                # Determine dominant direction
                # In device coordinates:
                # X: right(+) / left(-)
                # Y: up(+) / down(-)
                # Z: forward(+) / backward(-)
                abs_x, abs_y, abs_z = abs(dir_x), abs(dir_y), abs(dir_z)

                # Find the dominant axis
                if abs_y > abs_x and abs_y > abs_z:
                    # Y is dominant - up or down
                    pointing_direction = "up" if dir_y > 0 else "down"
                elif abs_x > abs_y and abs_x > abs_z:
                    # X is dominant - left or right
                    # Note: from user's perspective, +X is right, -X is left
                    pointing_direction = "right" if dir_x > 0 else "left"
                else:
                    # Z is dominant - forward (we can treat as "forward" or default to a direction)
                    # For now, if pointing forward, we consider it as no specific direction
                    # or we could map forward to "up" as a default
                    pointing_direction = "forward"

            # Store pointing debug info
            pointing_debug = {
                "indexExtended": index_extended,
                "thumbExtended": thumb_extended,
                "middleCurled": middle_curled,
                "ringCurled": ring_curled,
                "pinkyCurled": pinky_curled,
                "indexTipToPalm": round(index_tip_to_palm, 3),
                "thumbTipToPalm": round(thumb_tip_to_palm, 3),
                "extendThreshold": EXTEND_PALM_THRESHOLD,
                "curlThreshold": CURL_PALM_THRESHOLD,
                "direction": pointing_direction,
            }

        return {
            "joints": joints,
            "confidence": confidence,
            "debug": debug_info,
            "gestures": {
                "pinch": {"detected": is_pinching, "distance": pinch_distance},
                "thumbsUp": {"detected": is_thumbs_up, "debug": thumbs_up_debug},
                "pointing": {"detected": is_pointing, "debug": pointing_debug},
            },
        }

    def on_device_calib(self, calib_data):
        """Handle device calibration data (contains T_device_cpf).

        This transform is the offset from Device coordinate system (IMU position)
        to CPF coordinate system (Central Pupil Frame - eye center position).
        """
        try:
            logger.info(
                f"Device calibration callback received! Type: {type(calib_data)}"
            )
            attrs = [a for a in dir(calib_data) if not a.startswith("_")]
            logger.info(f"Calibration data attributes: {attrs}")

            T_device_cpf = None

            # SDK provides get_transform_device_cpf() method
            if hasattr(calib_data, "get_transform_device_cpf"):
                try:
                    T_device_cpf = calib_data.get_transform_device_cpf()
                    logger.info("Got T_device_cpf from get_transform_device_cpf()")
                except Exception as e:
                    logger.warning(f"Failed to call get_transform_device_cpf(): {e}")

            if T_device_cpf is not None:
                logger.info(f"T_device_cpf type: {type(T_device_cpf)}")
                t_attrs = [a for a in dir(T_device_cpf) if not a.startswith("_")]
                logger.info(f"T_device_cpf attributes: {t_attrs}")

                pos_extracted = False
                rot_extracted = False

                # Use translation() and rotation() separately for SE3 type
                if hasattr(T_device_cpf, "translation"):
                    try:
                        trans = T_device_cpf.translation()
                        logger.info(f"translation() result: {trans}")
                        # Handle 2D array [[x, y, z]] or 1D array [x, y, z]
                        if hasattr(trans, "flatten"):
                            trans = trans.flatten()
                        self._T_device_cpf_pos = np.array(
                            [float(trans[0]), float(trans[1]), float(trans[2])]
                        )
                        pos_extracted = True
                    except Exception as e:
                        logger.warning(f"translation() failed: {e}")

                if hasattr(T_device_cpf, "rotation"):
                    try:
                        rot = T_device_cpf.rotation()
                        logger.info(f"rotation() result: {rot}")
                        if hasattr(rot, "to_quat"):
                            quat = rot.to_quat()
                            logger.info(f"to_quat() result: {quat}")
                        else:
                            quat = rot
                        # Handle 2D array or 1D array
                        if hasattr(quat, "flatten"):
                            quat = quat.flatten()
                        self._T_device_cpf_quat = np.array(
                            [
                                float(quat[0]),
                                float(quat[1]),
                                float(quat[2]),
                                float(quat[3]),
                            ]
                        )
                        rot_extracted = True
                    except Exception as e:
                        logger.warning(f"rotation() failed: {e}")

                if pos_extracted or rot_extracted:
                    logger.info(
                        f"✅ T_device_cpf extracted from SDK - "
                        f"pos=({self._T_device_cpf_pos[0]:.4f}, {self._T_device_cpf_pos[1]:.4f}, {self._T_device_cpf_pos[2]:.4f}), "
                        f"quat=({self._T_device_cpf_quat[0]:.4f}, {self._T_device_cpf_quat[1]:.4f}, {self._T_device_cpf_quat[2]:.4f}, {self._T_device_cpf_quat[3]:.4f})"
                    )
                    self._cpf_from_sdk = True
                else:
                    logger.warning("T_device_cpf found but could not extract pos/rot")
            else:
                logger.warning("Could not get T_device_cpf. Using hardcoded defaults.")

        except Exception as e:
            logger.error(f"Error processing device calibration: {e}")
            import traceback

            traceback.print_exc()

        # Extract camera calibrations for all cameras
        self._extract_camera_calibrations(calib_data)

    def _extract_camera_calibrations(self, calib_data):
        """Extract calibration data for all cameras (SLAM and RGB).

        Extracts T_device_camera (4x4 transformation matrix) and intrinsics
        (fx, fy, cx, cy, width, height) for each camera.
        """
        # Camera label mapping: SDK label -> frontend label
        # Try multiple possible naming conventions
        camera_label_map = {
            # Primary naming convention (Aria Gen2)
            "camera-slam-left": "slam1",
            "camera-slam-right": "slam2",
            "camera-slam-left2": "slam3",
            "camera-slam-right2": "slam4",
            "camera-rgb": "rgb",
            # Alternative naming conventions (Aria SDK variations)
            "slam-left": "slam1",
            "slam-right": "slam2",
            "camera-slam-left-2": "slam3",
            "camera-slam-right-2": "slam4",
            "rgb": "rgb",
            # Mono camera variations
            "camera-slam-mono-left": "slam1",
            "camera-slam-mono-right": "slam2",
            "slam-mono-left": "slam1",
            "slam-mono-right": "slam2",
            # SLAM without "camera-" prefix
            "slam_left": "slam1",
            "slam_right": "slam2",
            "slam_left2": "slam3",
            "slam_right2": "slam4",
            # ET cameras
            "camera-et-left": "et_left",
            "camera-et-right": "et_right",
            "et-left": "et_left",
            "et-right": "et_right",
        }

        try:
            # First, try to get all available camera labels
            all_labels = []
            # Try get_camera_labels first (this is what Aria SDK uses)
            if hasattr(calib_data, "get_camera_labels"):
                try:
                    all_labels = calib_data.get_camera_labels()
                    logger.info(
                        f"📷 Available camera labels from SDK: {list(all_labels)}"
                    )
                except Exception as e:
                    logger.debug(f"get_camera_labels failed: {e}")
            # Fallback to get_all_camera_labels
            if not all_labels and hasattr(calib_data, "get_all_camera_labels"):
                try:
                    all_labels = calib_data.get_all_camera_labels()
                    logger.info(
                        f"📷 Available camera labels from SDK (all): {list(all_labels)}"
                    )
                except Exception as e:
                    logger.debug(f"get_all_camera_labels failed: {e}")

            # If we got labels from SDK, try them all directly
            if all_labels:
                for label in all_labels:
                    label_str = str(label)
                    # Determine frontend name based on label content
                    frontend_label = None
                    if "slam" in label_str.lower():
                        # Aria Gen2 uses: slam-front-left, slam-front-right, slam-side-left, slam-side-right
                        if "front" in label_str.lower() and "left" in label_str.lower():
                            frontend_label = "slam_front_left"
                        elif (
                            "front" in label_str.lower()
                            and "right" in label_str.lower()
                        ):
                            frontend_label = "slam_front_right"
                        elif (
                            "side" in label_str.lower() and "left" in label_str.lower()
                        ):
                            frontend_label = "slam_side_left"
                        elif (
                            "side" in label_str.lower() and "right" in label_str.lower()
                        ):
                            frontend_label = "slam_side_right"
                        # Fallback for other naming conventions
                        elif (
                            "left2" in label_str.lower()
                            or "left-2" in label_str.lower()
                        ):
                            frontend_label = "slam3"
                        elif (
                            "right2" in label_str.lower()
                            or "right-2" in label_str.lower()
                        ):
                            frontend_label = "slam4"
                        elif "left" in label_str.lower():
                            frontend_label = "slam1"
                        elif "right" in label_str.lower():
                            frontend_label = "slam2"
                    elif "rgb" in label_str.lower():
                        frontend_label = "rgb"
                    elif "et" in label_str.lower():
                        if "left" in label_str.lower():
                            frontend_label = "et_left"
                        elif "right" in label_str.lower():
                            frontend_label = "et_right"

                    if (
                        frontend_label
                        and frontend_label not in self._camera_calibrations
                    ):
                        try:
                            cam_calib = calib_data.get_camera_calib(label_str)
                            if cam_calib:
                                self._extract_single_camera(
                                    cam_calib, label_str, frontend_label
                                )
                        except Exception as e:
                            logger.debug(f"Failed to get calib for {label_str}: {e}")

            # Check if get_camera_calib exists
            if not hasattr(calib_data, "get_camera_calib"):
                logger.warning(
                    "❌ calib_data has no get_camera_calib method - cannot extract camera calibrations"
                )
                return

            logger.info(
                "✅ Found get_camera_calib method, extracting camera calibrations..."
            )

            extracted_cameras = (
                set()
            )  # Track which frontend labels we've already extracted

            for sdk_label, frontend_label in camera_label_map.items():
                # Skip if we already have this camera
                if frontend_label in extracted_cameras:
                    continue

                try:
                    cam_calib = calib_data.get_camera_calib(sdk_label)

                    if cam_calib is None:
                        continue

                    logger.info(
                        f"  📷 Found calibration for {sdk_label} -> {frontend_label}"
                    )

                    # Extract T_device_camera (4x4 transformation matrix)
                    T_device_camera = None
                    if hasattr(cam_calib, "get_transform_device_camera"):
                        transform = cam_calib.get_transform_device_camera()
                        if hasattr(transform, "to_matrix"):
                            T_device_camera = transform.to_matrix().tolist()
                        elif hasattr(transform, "matrix"):
                            T_device_camera = transform.matrix().tolist()

                    # Extract intrinsics (fx, fy, cx, cy)
                    intrinsics = {}
                    if hasattr(cam_calib, "get_principal_point"):
                        pp = cam_calib.get_principal_point()
                        intrinsics["cx"] = float(pp[0])
                        intrinsics["cy"] = float(pp[1])

                    if hasattr(cam_calib, "get_focal_lengths"):
                        fl = cam_calib.get_focal_lengths()
                        intrinsics["fx"] = float(fl[0])
                        intrinsics["fy"] = float(fl[1])

                    # Extract image dimensions
                    if hasattr(cam_calib, "get_image_size"):
                        img_size = cam_calib.get_image_size()
                        intrinsics["width"] = int(img_size[0])
                        intrinsics["height"] = int(img_size[1])

                    # Extract full projection model (FISHEYE624 params for distortion)
                    projection_model = {}
                    if hasattr(cam_calib, "get_model_name"):
                        try:
                            model_name = str(cam_calib.get_model_name())
                            projection_model["model_name"] = model_name
                        except Exception:
                            pass

                    if hasattr(cam_calib, "get_projection_params"):
                        try:
                            params = cam_calib.get_projection_params()
                            # Convert numpy array to list of floats
                            projection_model["params"] = [float(p) for p in params]
                            # FISHEYE624 has 15 params: [f, cx, cy, k0-k5, p0, p1, s0-s3]
                            projection_model["num_params"] = len(params)
                        except Exception:
                            pass

                    if hasattr(cam_calib, "get_valid_radius"):
                        try:
                            projection_model["valid_radius"] = float(
                                cam_calib.get_valid_radius()
                            )
                        except Exception:
                            pass

                    # Store calibration data
                    if T_device_camera and intrinsics:
                        calib_entry = {
                            "T_device_camera": T_device_camera,
                            **intrinsics,
                        }
                        # Add projection model if available
                        if projection_model:
                            calib_entry["projection_model"] = projection_model

                        self._camera_calibrations[frontend_label] = calib_entry
                        extracted_cameras.add(frontend_label)
                        logger.info(
                            f"    ✅ {frontend_label}: "
                            f"{intrinsics.get('width', '?')}x{intrinsics.get('height', '?')}, "
                            f"fx={intrinsics.get('fx', '?'):.1f}, fy={intrinsics.get('fy', '?'):.1f}"
                        )
                    else:
                        logger.debug(f"Incomplete calibration for {sdk_label}")

                except Exception as e:
                    logger.debug(f"Failed to extract calibration for {sdk_label}: {e}")

            if self._camera_calibrations:
                logger.info(
                    f"📷 Camera calibrations extracted: {list(self._camera_calibrations.keys())}"
                )
                # Mark calibration as not sent so it will be sent to new clients
                self._calibration_sent = False
            else:
                logger.warning("No camera calibrations could be extracted from SDK")

        except Exception as e:
            logger.error(f"Error extracting camera calibrations: {e}")
            import traceback

            traceback.print_exc()

    def _extract_single_camera(self, cam_calib, sdk_label, frontend_label):
        """Extract calibration data for a single camera.

        Args:
            cam_calib: Camera calibration object from SDK
            sdk_label: Original SDK label for logging
            frontend_label: Frontend-friendly label to store data under
        """
        try:
            # Extract T_device_camera (4x4 transformation matrix)
            T_device_camera = None
            if hasattr(cam_calib, "get_transform_device_camera"):
                transform = cam_calib.get_transform_device_camera()
                if hasattr(transform, "to_matrix"):
                    T_device_camera = transform.to_matrix().tolist()
                elif hasattr(transform, "matrix"):
                    T_device_camera = transform.matrix().tolist()

            # Extract intrinsics (fx, fy, cx, cy)
            intrinsics = {}
            if hasattr(cam_calib, "get_principal_point"):
                pp = cam_calib.get_principal_point()
                intrinsics["cx"] = float(pp[0])
                intrinsics["cy"] = float(pp[1])

            if hasattr(cam_calib, "get_focal_lengths"):
                fl = cam_calib.get_focal_lengths()
                intrinsics["fx"] = float(fl[0])
                intrinsics["fy"] = float(fl[1])

            # Extract image dimensions
            if hasattr(cam_calib, "get_image_size"):
                img_size = cam_calib.get_image_size()
                intrinsics["width"] = int(img_size[0])
                intrinsics["height"] = int(img_size[1])

            # Store calibration data
            if T_device_camera and intrinsics:
                self._camera_calibrations[frontend_label] = {
                    "T_device_camera": T_device_camera,
                    **intrinsics,
                }
                logger.info(
                    f"  📷 {frontend_label} ({sdk_label}): "
                    f"{intrinsics.get('width', '?')}x{intrinsics.get('height', '?')}, "
                    f"fx={intrinsics.get('fx', '?'):.1f}, fy={intrinsics.get('fy', '?'):.1f}"
                )
            else:
                logger.debug(f"Incomplete calibration for {sdk_label}")

        except Exception as e:
            logger.debug(f"Failed to extract single camera {sdk_label}: {e}")

    def build_calibration_message(self):
        """Build the calibration message to send to frontend.

        Returns a JSON message containing all camera calibration data
        including T_device_camera (4x4 transformation) and intrinsics.
        Also includes camera_id mapping for SLAM and ET frames.
        """
        if not self._camera_calibrations:
            logger.warning("No camera calibrations available to send")
            return None

        # Camera ID mapping (from SDK's integer camera_id to camera name)
        # These values are determined by Aria SDK's camera enumeration
        camera_id_map = {
            # SLAM cameras (bitmask values)
            "1": "slam_front_left",
            "2": "slam_front_right",
            "4": "slam_side_left",
            "8": "slam_side_right",
            # ET cameras
            "16": "et_left",
            "32": "et_right",
            # RGB camera (if applicable)
            "64": "rgb",
        }

        message = {
            "type": "calibration",
            "timestamp": time.time(),
            "data": {
                "cameras": self._camera_calibrations,
                "camera_id_map": camera_id_map,
            },
        }

        return message

    async def send_calibration_to_clients(self):
        """Send calibration message to all connected WebSocket clients."""
        calib_message = self.build_calibration_message()

        if calib_message is None:
            return

        import json

        message_str = json.dumps(calib_message)

        disconnected = []
        for ws in self.clients:
            try:
                await ws.send(message_str)
                logger.info("📤 Calibration message sent to client")
            except Exception as e:
                logger.warning(f"Failed to send calibration to client: {e}")
                disconnected.append(ws)

        # Remove disconnected clients
        for ws in disconnected:
            self.clients.pop(ws, None)

    def on_vio(self, vio_data):
        """Handle VIO (Visual-Inertial Odometry) data.

        ═══════════════════════════════════════════════════════════════════════════
        CORRECT PIPELINE (per StepByStep.md):
        ═══════════════════════════════════════════════════════════════════════════

        Step 1: 获取原始姿态 T_odometry_device
                - 组合变换: T_odometry_device = T_odometry_bodyImu × T_bodyImu_device

        Step 2: 重力对齐 (FromToRotation)
                - R_gravityAlign = FromToRotation(normalize(gravity_odometry), [0, -1, 0])
                - T_aligned.rotation = R_gravityAlign × T_odometry_device.rotation
                - T_aligned.position = R_gravityAlign × T_odometry_device.position

        Step 3: 坐标系转换 (Surreal → Web)
                - Position: x' = x, y' = y, z' = -z (handedness flip)
                - Quaternion: x' = -x, y' = -y, z' = z, w' = w

        ═══════════════════════════════════════════════════════════════════════════
        Coordinate Systems:
        - Surreal (right-handed, Z-up): X=right, Y=forward, Z=up
        - Web/Unity (left-handed, Y-up): X=right, Y=up, Z=forward
        ═══════════════════════════════════════════════════════════════════════════
        """
        if vio_data is None:
            return

        self.frame_stats["vio"] += 1

        try:
            import math

            import numpy as np
            from projectaria_tools.core.sophus import SE3

            timestamp = (
                getattr(vio_data, "capture_timestamp_ns", time.time() * 1e9) / 1e9
            )

            # ══════════════════════════════════════════════════════════════════
            # STEP 1: 获取原始姿态 T_odometry_device
            # ══════════════════════════════════════════════════════════════════
            T_odometry_bodyImu = vio_data.transform_odometry_bodyimu
            T_bodyImu_device = getattr(vio_data, "transform_bodyimu_device", None)

            if T_bodyImu_device is not None:
                T_odometry_device = SE3.from_matrix(
                    T_odometry_bodyImu.to_matrix() @ T_bodyImu_device.to_matrix()
                )
            else:
                T_odometry_device = T_odometry_bodyImu

            # Extract raw position and quaternion in odometry frame
            pos_raw = T_odometry_device.translation().flatten()
            quat_raw = T_odometry_device.rotation().to_quat().flatten()  # [w, x, y, z]

            # ══════════════════════════════════════════════════════════════════
            # STEP 2: 重力对齐 (FromToRotation)
            # ══════════════════════════════════════════════════════════════════
            # 完全按照 Unity SDK 的方式 (NebulaDevicePose.cs line 194):
            #   R_unityGravity_odometryGravity = FromToRotation(
            #       normalize(gravity_odometry), [0, -1, 0])
            #
            # gravity_odometry = [0, 0, -9.81] → normalized = [0, 0, -1]
            # Target = [0, -1, 0] (Unity's down direction)
            #
            # 这会创建一个绕 X 轴旋转 -90 度的四元数:
            #   R = (-0.7071, 0, 0, 0.7071) [x,y,z,w]
            #   R = (0.7071, -0.7071, 0, 0) [w,x,y,z]
            # ══════════════════════════════════════════════════════════════════

            # Gravity is ALWAYS [0, 0, -9.81] in Surreal odometry frame (Z-up)
            gravity_array = np.array([0.0, 0.0, -9.81], dtype=np.float64)

            # Unity's target down direction (in the mixed coordinate space)
            # Unity 直接把 Surreal 的 -Z 映射到 Unity 的 -Y
            target_down = np.array([0.0, -1.0, 0.0])

            # Helper functions
            def normalize(v):
                """Normalize a vector"""
                norm = np.linalg.norm(v)
                return v / norm if norm > 1e-9 else v

            def from_to_rotation(from_vec, to_vec):
                """
                Compute quaternion that rotates from_vec to to_vec.
                Returns [w, x, y, z] quaternion.
                """
                from_vec = normalize(np.array(from_vec, dtype=np.float64))
                to_vec = normalize(np.array(to_vec, dtype=np.float64))

                dot = np.clip(np.dot(from_vec, to_vec), -1.0, 1.0)

                if dot > 0.9999:
                    # Vectors are nearly parallel
                    return np.array([1.0, 0.0, 0.0, 0.0])
                elif dot < -0.9999:
                    # Vectors are nearly opposite, find orthogonal axis
                    axis = np.cross([1.0, 0.0, 0.0], from_vec)
                    if np.linalg.norm(axis) < 0.01:
                        axis = np.cross([0.0, 1.0, 0.0], from_vec)
                    axis = normalize(axis)
                    return np.array([0.0, axis[0], axis[1], axis[2]])
                else:
                    # Standard case: axis = cross, angle = acos(dot)
                    axis = np.cross(from_vec, to_vec)
                    axis = normalize(axis)
                    angle = np.arccos(dot)
                    half_angle = angle / 2.0
                    s = np.sin(half_angle)
                    return np.array(
                        [np.cos(half_angle), axis[0] * s, axis[1] * s, axis[2] * s]
                    )

            def quat_mult(a, b):
                """Hamilton product: a × b, where q = [w, x, y, z]"""
                aw, ax, ay, az = a
                bw, bx, by, bz = b
                return np.array(
                    [
                        aw * bw - ax * bx - ay * by - az * bz,
                        aw * bx + ax * bw + ay * bz - az * by,
                        aw * by - ax * bz + ay * bw + az * bx,
                        aw * bz + ax * by - ay * bx + az * bw,
                    ]
                )

            def quat_rotate_vec(q, v):
                """Rotate vector v by quaternion q (q = [w,x,y,z])"""
                qw, qx, qy, qz = q
                t = 2.0 * np.cross([qx, qy, qz], v)
                return v + qw * t + np.cross([qx, qy, qz], t)

            # ══════════════════════════════════════════════════════════════════
            # STEP 1.5: Save Device pose for HAND TRACKING (before CPF transform)
            # Unity flow for hand: raw VIO → gravity aligned → SurrealToUnity
            # NOTE: Hand data is relative to Device, NOT CPF!
            # ══════════════════════════════════════════════════════════════════
            # Apply gravity alignment to raw pose (for hand tracking)
            if self._gravity_align_quat is not None:
                hand_device_pos = quat_rotate_vec(self._gravity_align_quat, pos_raw)
                hand_device_quat = quat_mult(self._gravity_align_quat, quat_raw)
                hand_device_quat = hand_device_quat / np.linalg.norm(hand_device_quat)
            else:
                hand_device_pos = pos_raw.copy()
                hand_device_quat = quat_raw.copy()

            # Convert to Unity coordinates (SurrealToUnity)
            hand_device_pos_unity = np.array(
                [hand_device_pos[0], hand_device_pos[1], -hand_device_pos[2]]
            )
            hdqw, hdqx, hdqy, hdqz = hand_device_quat
            hand_device_quat_unity = np.array([hdqw, -hdqx, -hdqy, hdqz])
            hand_device_quat_unity = hand_device_quat_unity / np.linalg.norm(
                hand_device_quat_unity
            )

            self._last_device_pos_for_hand = hand_device_pos_unity
            self._last_device_quat_for_hand = hand_device_quat_unity

            # ══════════════════════════════════════════════════════════════════
            # STEP 1.6: Apply T_device_cpf (Device → CPF transform) for HEAD visualization
            # ══════════════════════════════════════════════════════════════════
            # Unity order: T_odometry_cpf = T_odometry_device × T_device_cpf
            # THEN gravity alignment is applied to T_odometry_cpf
            # ══════════════════════════════════════════════════════════════════

            if (
                self._T_device_cpf_pos is not None
                and self._T_device_cpf_quat is not None
            ):
                # T_cpf = T_device × T_device_cpf
                # Position: pos_cpf = pos_device + R_device × pos_device_cpf
                # Rotation: quat_cpf = quat_device × quat_device_cpf

                # Store original for debug
                pos_before_cpf = pos_raw.copy()
                quat_before_cpf = quat_raw.copy()

                cpf_pos_rotated = quat_rotate_vec(quat_raw, self._T_device_cpf_pos)
                pos_raw = pos_raw + cpf_pos_rotated

                quat_raw = quat_mult(quat_raw, self._T_device_cpf_quat)

                # Normalize quaternion
                quat_raw = quat_raw / np.linalg.norm(quat_raw)

                # Debug: Log T_device_cpf application (first few frames only)
                if self.frame_stats["vio"] < 3:
                    logger.info(
                        f"T_device_cpf applied: "
                        f"pos {pos_before_cpf} -> {pos_raw}, "
                        f"quat {quat_before_cpf} -> {quat_raw}"
                    )

            # Initialize gravity alignment on first frame
            if self._gravity_align_quat is None:
                logger.info(
                    f"Gravity vector (constant): [{gravity_array[0]:.3f}, {gravity_array[1]:.3f}, {gravity_array[2]:.3f}]"
                )
                logger.info(
                    f"Target down (Unity): [{target_down[0]:.3f}, {target_down[1]:.3f}, {target_down[2]:.3f}]"
                )

                # Compute gravity alignment quaternion
                # FromToRotation([0,0,-1], [0,-1,0]) = -90 degrees around X
                self._gravity_align_quat = from_to_rotation(
                    normalize(gravity_array), target_down
                )

                logger.info(
                    f"Gravity alignment quat [w,x,y,z]: [{self._gravity_align_quat[0]:.4f}, "
                    f"{self._gravity_align_quat[1]:.4f}, {self._gravity_align_quat[2]:.4f}, "
                    f"{self._gravity_align_quat[3]:.4f}]"
                )

            # ══════════════════════════════════════════════════════════════════
            # Save RAW device pose for hand tracking transformation
            # Hand data (landmark_positions_device) is relative to Device (IMU),
            # NOT relative to CPF! So we need raw device pose, not CPF pose.
            # ══════════════════════════════════════════════════════════════════
            # Convert raw pose to Unity coordinates (only coordinate transform, no CPF or gravity)
            raw_pos_unity = np.array([pos_raw[0], pos_raw[1], -pos_raw[2]])
            raw_qw, raw_qx, raw_qy, raw_qz = quat_raw
            raw_quat_unity = np.array([raw_qw, -raw_qx, -raw_qy, raw_qz])
            raw_quat_unity = raw_quat_unity / np.linalg.norm(raw_quat_unity)

            self._last_device_pos_raw = raw_pos_unity
            self._last_device_quat_raw = raw_quat_unity

            # Apply gravity alignment to position (ABSOLUTE position, not relative!)
            # Unity 直接用绝对位置，不做相对处理
            pos_aligned = quat_rotate_vec(self._gravity_align_quat, pos_raw)

            # Apply gravity alignment to quaternion
            # Q_aligned = R_gravityAlign × Q_raw
            quat_aligned = quat_mult(self._gravity_align_quat, quat_raw)

            # ══════════════════════════════════════════════════════════════════
            # STEP 3: 坐标系转换 (Surreal → Unity/Web) + X镜像
            # ══════════════════════════════════════════════════════════════════
            # Unity 原始转换公式 (from NebulaDevicePose.cs):
            #   Position: (x, y, z) → (x, y, -z)
            #   Rotation: (x, y, z, w) → (-x, -y, z, w)
            #
            # 额外 X 镜像 (替代前端 CSS scaleX(-1)):
            #   Position: x → -x
            #   Rotation: 绕 X 轴镜像 → (x, -y, -z, w) → (-x, y, z, w)
            # ══════════════════════════════════════════════════════════════════

            # Position: Surreal → Unity (negate Z) + X镜像 (negate X)
            pos_web = np.array(
                [
                    -pos_aligned[0],  # X negated (镜像效果，替代前端scaleX(-1))
                    pos_aligned[1],  # Y stays same
                    -pos_aligned[2],  # Z negated
                ]
            )

            # Quaternion: Surreal → Unity + X镜像
            # quat_aligned is in [w, x, y, z] format
            # Unity conversion: (x, y, z, w) → (-x, -y, z, w)
            # X镜像: 绕YZ平面镜像，quaternion变换为 (x, -y, -z, w)
            # 组合: (-x, -y, z, w) 然后 X镜像 → (-x, y, -z, w)
            qw, qx, qy, qz = quat_aligned
            quat_web = np.array(
                [
                    qw,  # w stays same
                    -qx,  # x negated (from Unity conversion)
                    qy,  # y: -(-y) = y (Unity negate + mirror negate cancel)
                    -qz,  # z: z then mirror negate = -z
                ]
            )

            # Normalize
            quat_web = quat_web / np.linalg.norm(quat_web)

            # ══════════════════════════════════════════════════════════════════
            # Save CPF pose for visualization (pos_web has CPF applied)
            # ══════════════════════════════════════════════════════════════════
            self._last_device_pos = pos_web
            self._last_device_quat = quat_web

            # ══════════════════════════════════════════════════════════════════
            # HEAD pose for hand tracking = T_final (Step 5) = Device pose WITHOUT CPF
            # From cheat sheet: HEAD pos = T_final.pos, HEAD quat = T_final.rot
            # Hand transform: rotated = head_quat × raw_unity, world = rotated + head_pos
            #
            # CRITICAL: Use _last_device_pos_for_hand and _last_device_quat_for_hand
            # which are saved BEFORE CPF transform (lines 717-718)
            # ══════════════════════════════════════════════════════════════════
            # Convert [w,x,y,z] → [x,y,z,w] for hand rotation
            # _last_device_quat_for_hand is already in [w,x,y,z] format
            device_quat_for_hand = getattr(self, "_last_device_quat_for_hand", None)
            if device_quat_for_hand is not None:
                self._last_head_quat_xyzw_for_hand = np.array(
                    [
                        device_quat_for_hand[1],  # x
                        device_quat_for_hand[2],  # y
                        device_quat_for_hand[3],  # z
                        device_quat_for_hand[0],  # w
                    ]
                )
            # HEAD position = Device position (no CPF)
            device_pos_for_hand = getattr(self, "_last_device_pos_for_hand", None)
            if device_pos_for_hand is not None:
                self._last_head_pos_for_hand = device_pos_for_hand.copy()

            # ══════════════════════════════════════════════════════════════════
            # Compute Euler angles for debug display
            # 使用和 Unity NebulaDevicePose.cs 完全相同的 ToEulerAngles 函数
            # quat_web 是 [w, x, y, z] 格式，但 Unity 的 quaternion.value 是 [x, y, z, w]
            # ══════════════════════════════════════════════════════════════════
            qw_w, qx_w, qy_w, qz_w = quat_web

            # Unity ToEulerAngles (from NebulaDevicePose.cs line 273-291)
            # Note: Unity's q.value is (x, y, z, w), so we use our qx_w, qy_w, qz_w, qw_w

            # euler.x (Pitch - rotation around X axis)
            sinr_cosp = 2 * (qw_w * qx_w + qy_w * qz_w)
            cosr_cosp = 1 - 2 * (qx_w * qx_w + qy_w * qy_w)
            euler_x = math.atan2(sinr_cosp, cosr_cosp)

            # euler.y (Yaw - rotation around Y axis)
            sinp = 2 * (qw_w * qy_w - qz_w * qx_w)
            sinp = max(-1.0, min(1.0, sinp))
            if abs(sinp) >= 1:
                euler_y = math.copysign(math.pi / 2, sinp)
            else:
                euler_y = math.asin(sinp)

            # euler.z (Roll - rotation around Z axis)
            siny_cosp = 2 * (qw_w * qz_w + qx_w * qy_w)
            cosy_cosp = 1 - 2 * (qy_w * qy_w + qz_w * qz_w)
            euler_z = math.atan2(siny_cosp, cosy_cosp)

            # Convert to degrees (Unity style: X, Y, Z order)
            pitch_deg = math.degrees(euler_x)  # X
            yaw_deg = math.degrees(euler_y)  # Y
            roll_deg = math.degrees(euler_z)  # Z

            # Quality info
            status = getattr(vio_data, "status", 0)
            pose_quality = getattr(vio_data, "pose_quality", 0)

            # Full absolute quaternion (for hand tracking)
            # This is the gravity-aligned quaternion in Surreal frame
            quat_full_aligned = quat_aligned

            message = json.dumps(
                {
                    "type": "vio",
                    "timestamp": timestamp,
                    "data": {
                        "position": {
                            "x": float(pos_web[0]),
                            "y": float(pos_web[1]),
                            "z": float(pos_web[2]),
                        },
                        "quaternion": {
                            "w": float(quat_web[0]),
                            "x": float(quat_web[1]),
                            "y": float(quat_web[2]),
                            "z": float(quat_web[3]),
                        },
                        "quaternion_full": {
                            "w": float(quat_full_aligned[0]),
                            "x": float(quat_full_aligned[1]),
                            "y": float(quat_full_aligned[2]),
                            "z": float(quat_full_aligned[3]),
                        },
                        "euler": {"yaw": yaw_deg, "pitch": pitch_deg, "roll": roll_deg},
                        "status": int(status) if hasattr(status, "__int__") else 0,
                        "poseQuality": (
                            int(pose_quality) if hasattr(pose_quality, "__int__") else 0
                        ),
                        # ═══════════════════════════════════════════════════════════
                        # DEBUG: Step-by-step intermediate values for troubleshooting
                        # ═══════════════════════════════════════════════════════════
                        "debug": {
                            "step1_raw": {
                                "pos": {
                                    "x": float(pos_raw[0]),
                                    "y": float(pos_raw[1]),
                                    "z": float(pos_raw[2]),
                                },
                                "quat": {
                                    "w": float(quat_raw[0]),
                                    "x": float(quat_raw[1]),
                                    "y": float(quat_raw[2]),
                                    "z": float(quat_raw[3]),
                                },
                            },
                            "step2_gravity": {
                                "gravity_vec": {
                                    "x": (
                                        float(gravity_array[0])
                                        if gravity_array is not None
                                        else 0
                                    ),
                                    "y": (
                                        float(gravity_array[1])
                                        if gravity_array is not None
                                        else 0
                                    ),
                                    "z": (
                                        float(gravity_array[2])
                                        if gravity_array is not None
                                        else 0
                                    ),
                                },
                                "align_quat": {
                                    "w": float(self._gravity_align_quat[0]),
                                    "x": float(self._gravity_align_quat[1]),
                                    "y": float(self._gravity_align_quat[2]),
                                    "z": float(self._gravity_align_quat[3]),
                                },
                                "pos_raw": {
                                    "x": float(pos_raw[0]),
                                    "y": float(pos_raw[1]),
                                    "z": float(pos_raw[2]),
                                },
                                "pos_aligned": {
                                    "x": float(pos_aligned[0]),
                                    "y": float(pos_aligned[1]),
                                    "z": float(pos_aligned[2]),
                                },
                                "quat_aligned": {
                                    "w": float(quat_aligned[0]),
                                    "x": float(quat_aligned[1]),
                                    "y": float(quat_aligned[2]),
                                    "z": float(quat_aligned[3]),
                                },
                            },
                            "step3_web": {
                                "pos": {
                                    "x": float(pos_web[0]),
                                    "y": float(pos_web[1]),
                                    "z": float(pos_web[2]),
                                },
                                "quat": {
                                    "w": float(quat_web[0]),
                                    "x": float(quat_web[1]),
                                    "y": float(quat_web[2]),
                                    "z": float(quat_web[3]),
                                },
                            },
                            "t_device_cpf": {
                                "pos": {
                                    "x": float(self._T_device_cpf_pos[0]),
                                    "y": float(self._T_device_cpf_pos[1]),
                                    "z": float(self._T_device_cpf_pos[2]),
                                },
                                "quat": {
                                    "w": float(self._T_device_cpf_quat[0]),
                                    "x": float(self._T_device_cpf_quat[1]),
                                    "y": float(self._T_device_cpf_quat[2]),
                                    "z": float(self._T_device_cpf_quat[3]),
                                },
                                "source": (
                                    "sdk_callback"
                                    if hasattr(self, "_cpf_from_sdk")
                                    and self._cpf_from_sdk
                                    else "hardcoded"
                                ),
                            },
                        },
                    },
                }
            )

            # Schedule broadcast in event loop (thread-safe)
            # NOTE: VIO state updates above MUST always run (hand tracking
            # depends on them), so we only skip the broadcast — not the
            # processing — when no client is subscribed.
            if self.loop and self.has_subscribers("vio"):
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_stream("vio", message), self.loop
                )
        except Exception as e:
            logger.error(f"Error in on_vio: {e}", exc_info=True)

    def on_imu(self, imu_data, sensor_label):
        """Handle IMU data (downsampled for web).

        Args:
            imu_data: MotionData with accel_msec2 and gyro_radsec
            sensor_label: "imu-left" or "imu-right"
        """
        if imu_data is None:
            return

        self.frame_stats["imu"] += 1

        # Time-based throttle: ~10 Hz output regardless of input rate (device sends ~880 Hz)
        now = time.monotonic()
        if now - self._imu_last_send_time < 0.1:
            return
        self._imu_last_send_time = now

        if not self.has_subscribers("imu"):
            return

        try:
            # Extract accelerometer and gyroscope data
            accel = imu_data.accel_msec2
            gyro = imu_data.gyro_radsec

            # Use current time since IMU data might not have capture_timestamp_ns
            timestamp = time.time()

            message = json.dumps(
                {
                    "type": "imu",
                    "timestamp": timestamp,
                    "data": {
                        "sensor": sensor_label,
                        "accel": {
                            "x": float(accel[0]),
                            "y": float(accel[1]),
                            "z": float(accel[2]),
                        },
                        "gyro": {
                            "x": float(gyro[0]),
                            "y": float(gyro[1]),
                            "z": float(gyro[2]),
                        },
                    },
                }
            )

            # Schedule broadcast in event loop (thread-safe)
            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_stream("imu", message), self.loop
                )
        except Exception as e:
            logger.error(f"Error in on_imu: {e}")

    def on_audio(self, audio_data, audio_record, num_channels: int):
        """Handle audio data from device.

        Aria Gen2 audio pipeline (from internal docs):
        - Device has 8 microphones, interleaved in audio_data.data
        - Profile-dependent format:
          * profile0 (raw PCM): int32 (S32), 48kHz, 8ch — RT600 puts 16-bit in MSB
          * profile2/mp_streaming_demo (Opus): S16 decoded by SDK → returned as int
          * profile9 (default Python SDK): Opus-decoded
        - SDK handles Opus decoding internally; callback gets PCM samples
        - We extract channel 2 (RIM_BOTTOM_LEFT) and normalize to float32

        Args:
            audio_data: AudioData with samples (.data)
            audio_record: Record with timestamps
            num_channels: Number of audio channels (typically 7 or 8)
        """
        if audio_data is None:
            return

        self.frame_stats["audio"] += 1

        if not self.has_subscribers("audio"):
            return

        frame_num = self.frame_stats["audio"]

        try:
            # Extract raw audio samples
            raw_samples = audio_data.data if hasattr(audio_data, "data") else []
            num_samples = len(raw_samples)

            # Get timestamp
            timestamps = (
                audio_record.capture_timestamps_ns
                if hasattr(audio_record, "capture_timestamps_ns")
                else []
            )
            timestamp = timestamps[0] / 1e9 if timestamps else time.time()

            if num_samples == 0:
                return

            # Convert to numpy array
            if not isinstance(raw_samples, np.ndarray):
                raw_samples = np.array(raw_samples)

            # ── Detailed debug logging for first 5 frames ──
            if frame_num <= 5:
                logger.info(
                    f"🎤 Audio frame #{frame_num}: "
                    f"num_channels={num_channels}, "
                    f"total_samples={num_samples}, "
                    f"dtype={raw_samples.dtype}, "
                    f"min={raw_samples.min()}, max={raw_samples.max()}, "
                    f"abs_max={np.max(np.abs(raw_samples.astype(np.float64)))}, "
                    f"samples_per_ch={num_samples // max(num_channels, 1)}, "
                    f"first_16={raw_samples[:16].tolist()}"
                )

            # ── Channel extraction ──
            # SDK: 8-ch interleaved [ch0 ch1 ... ch7 | ch0 ch1 ...]
            # Select channel 2 (RIM_BOTTOM_LEFT)
            MIC_CHANNEL = 2
            if num_channels > 1 and num_samples >= num_channels:
                channel_idx = MIC_CHANNEL % num_channels
                mono_samples = raw_samples[channel_idx::num_channels].copy()
            else:
                mono_samples = raw_samples.copy()

            # ── Normalization: fixed divisor + gain boost ──
            # From logs: dtype=int64, values like ±5373952 (= int16_val << 16)
            # This is S32 format: RT600 puts 16-bit audio in MSB of 32-bit word
            # Step 1: Right-shift 16 bits → extract int16 payload
            # Step 2: Normalize int16 → [-1, 1]
            # Combined: divide by 2^31 (= 65536 * 32768)
            # Step 3: Apply gain boost (original int16 values are tiny, ~50-100)
            mono_float = mono_samples.astype(np.float64) / 2147483648.0  # fixed 2^31

            # Boost gain — raw int16 values are ~50-100 (out of 32768 max)
            # so after /2^31 they're ~0.003. Boost 100x → ~0.3 (comfortable level)
            AUDIO_GAIN = 100.0
            mono_float = mono_float * AUDIO_GAIN
            mono_float = np.clip(mono_float, -1.0, 1.0).astype(np.float32)

            # ── NO noise gate — let all audio through ──

            # ── RMS / peak for visualization ──
            rms = float(np.sqrt(np.mean(mono_float.astype(np.float64) ** 2)))
            peak = float(np.max(np.abs(mono_float)))

            # Determine sample rate from frame size
            # Opus standard frame = 20ms → sample_rate = samples_per_channel / 0.020
            # With 320 samples/ch: 320 / 0.020 = 16000 Hz
            # With 960 samples/ch: 960 / 0.020 = 48000 Hz
            samples_per_channel = len(mono_float)
            if samples_per_channel > 0:
                sample_rate = int(samples_per_channel / 0.020)  # Opus 20ms frame
            else:
                sample_rate = 48000

            if frame_num <= 5:
                duration_ms = (samples_per_channel / sample_rate) * 1000
                mono_abs_max = float(np.max(np.abs(mono_float)))
                logger.info(
                    f"🎤 Audio processed #{frame_num}: "
                    f"dtype_in={raw_samples.dtype}, mono={samples_per_channel} samples, "
                    f"rms={rms:.6f}, peak={peak:.6f}, mono_max={mono_abs_max:.6f}, "
                    f"~{duration_ms:.1f}ms at {sample_rate}Hz, "
                    f"first_5_float={mono_float[:5].tolist()}"
                )

            # Encode mono float32 as base64
            audio_bytes = mono_float.tobytes()
            b64_audio = base64.b64encode(audio_bytes).decode("utf-8")

            message = json.dumps(
                {
                    "type": "audio",
                    "timestamp": timestamp,
                    "data": {
                        "samples": b64_audio,
                        "num_samples": samples_per_channel,
                        "num_channels": 1,
                        "sample_rate": sample_rate,
                        "dtype": "float32",
                        "level": rms,
                        "peak": peak,
                    },
                }
            )

            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_stream("audio", message), self.loop
                )
        except Exception as e:
            logger.error(f"Error in on_audio: {e}", exc_info=True)

    def on_ppg(self, ppg_data, ppg_record=None):
        """Handle PPG (photoplethysmography) data from device.

        PPG sensors measure blood volume changes through light absorption,
        commonly used for heart rate and pulse monitoring.

        Args:
            ppg_data: PPG data containing raw samples and derived values
            ppg_record: Record with timestamps (optional, may vary by SDK version)
        """
        # Always log the first few calls to debug data format
        self.frame_stats["ppg"] += 1
        frame_num = self.frame_stats["ppg"]

        if frame_num <= 2:
            logger.info(
                f"💓 PPG callback #{frame_num} received: "
                f"ppg_data type={type(ppg_data).__name__}, "
                f"ppg_record type={type(ppg_record).__name__ if ppg_record else 'None'}"
            )
            if ppg_data is not None:
                attrs = [a for a in dir(ppg_data) if not a.startswith("_")]
                logger.info(f"  ppg_data attributes: {attrs[:20]}")

        if ppg_data is None:
            return

        try:
            # Get timestamp - try multiple sources
            timestamp = time.time()
            if ppg_record is not None:
                if hasattr(ppg_record, "capture_timestamp_ns"):
                    timestamp = ppg_record.capture_timestamp_ns / 1e9
                elif hasattr(ppg_record, "timestamp_ns"):
                    timestamp = ppg_record.timestamp_ns / 1e9
            elif hasattr(ppg_data, "capture_timestamp_ns"):
                timestamp = ppg_data.capture_timestamp_ns / 1e9
            elif hasattr(ppg_data, "timestamp_ns"):
                timestamp = ppg_data.timestamp_ns / 1e9

            # Extract PPG data fields
            ppg_values = {}

            # Get the raw PPG value
            raw_value = None
            if hasattr(ppg_data, "value"):
                raw_value = float(ppg_data.value)
                ppg_values["value"] = raw_value

            # Add to buffer for heart rate calculation
            if raw_value is not None:
                self._ppg_buffer.append((timestamp, raw_value))

                # Remove old samples (keep only last N seconds)
                cutoff_time = timestamp - self._ppg_buffer_duration
                self._ppg_buffer = [
                    (t, v) for t, v in self._ppg_buffer if t > cutoff_time
                ]

                # Calculate heart rate periodically
                current_time = time.time()
                if (
                    current_time - self._ppg_last_hr_time
                    >= self._ppg_hr_update_interval
                ):
                    hr = self._calculate_heart_rate()
                    if hr is not None:
                        self._ppg_last_hr = hr
                    self._ppg_last_hr_time = current_time

            # Add calculated heart rate to output
            if self._ppg_last_hr is not None:
                ppg_values["heart_rate"] = self._ppg_last_hr

            # Other raw values (if available)
            if hasattr(ppg_data, "ir_value"):
                ppg_values["ir"] = float(ppg_data.ir_value)
            if hasattr(ppg_data, "red_value"):
                ppg_values["red"] = float(ppg_data.red_value)
            if hasattr(ppg_data, "green_value"):
                ppg_values["green"] = float(ppg_data.green_value)

            # Log first few frames for debugging
            if frame_num <= 5:
                logger.info(
                    f"💓 PPG frame #{frame_num}: "
                    f"timestamp={timestamp:.3f}, "
                    f"values={ppg_values}"
                )

            message = json.dumps(
                {
                    "type": "ppg",
                    "timestamp": timestamp,
                    "data": ppg_values,
                }
            )

            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_stream("ppg", message), self.loop
                )
        except Exception as e:
            logger.error(f"Error in on_ppg: {e}", exc_info=True)

    def _calculate_heart_rate(self):
        """Calculate heart rate from PPG buffer using peak detection.

        Returns:
            float: Heart rate in BPM, or None if not enough data
        """
        if len(self._ppg_buffer) < 100:  # Need at least ~5 seconds of data
            return self._ppg_last_hr

        try:
            timestamps = np.array([t for t, v in self._ppg_buffer])
            values = np.array([v for t, v in self._ppg_buffer])

            # Normalize the signal (remove DC offset and scale)
            values_norm = values - np.mean(values)
            if np.std(values_norm) > 0:
                values_norm = values_norm / np.std(values_norm)

            # Simple peak detection
            # A peak is a point higher than its neighbors
            peaks = []
            for i in range(2, len(values_norm) - 2):
                if (
                    values_norm[i] > values_norm[i - 1]
                    and values_norm[i] > values_norm[i - 2]
                    and values_norm[i] > values_norm[i + 1]
                    and values_norm[i] > values_norm[i + 2]
                    and values_norm[i] > 0.3  # Must be above threshold
                ):
                    # Check minimum distance from last peak (~0.3s = 200 BPM max)
                    if len(peaks) == 0 or (timestamps[i] - timestamps[peaks[-1]]) > 0.3:
                        peaks.append(i)

            if len(peaks) < 3:  # Need at least 3 peaks for reliable calculation
                return self._ppg_last_hr

            # Calculate intervals between peaks
            intervals = []
            for i in range(1, len(peaks)):
                interval = timestamps[peaks[i]] - timestamps[peaks[i - 1]]
                # Valid interval: 0.4s (150 BPM) to 1.5s (40 BPM)
                if 0.4 <= interval <= 1.5:
                    intervals.append(interval)

            if len(intervals) < 2:
                return self._ppg_last_hr

            # Calculate average interval and convert to BPM
            avg_interval = np.median(intervals)  # Use median to reduce outliers
            heart_rate = 60.0 / avg_interval

            # Sanity check: 40-150 BPM is reasonable range
            if not (40 <= heart_rate <= 150):
                return self._ppg_last_hr

            # Add to HR history for smoothing
            self._ppg_hr_history.append(heart_rate)
            # Keep only last 10 HR calculations
            self._ppg_hr_history = self._ppg_hr_history[-10:]

            # Use weighted moving average of recent calculations
            if len(self._ppg_hr_history) >= 3:
                # Give more weight to recent values
                weights = np.linspace(0.5, 1.0, len(self._ppg_hr_history))
                weights = weights / weights.sum()
                smoothed_hr = np.average(self._ppg_hr_history, weights=weights)
            else:
                smoothed_hr = np.mean(self._ppg_hr_history)

            # Additional smoothing with previous output
            if self._ppg_last_hr is not None:
                # 80% previous + 20% new for very smooth transitions
                smoothed_hr = 0.8 * self._ppg_last_hr + 0.2 * smoothed_hr

            return round(smoothed_hr, 0)

        except Exception as e:
            logger.error(f"Error calculating heart rate: {e}")
            return self._ppg_last_hr

    async def handle_client_message(self, websocket, message: str):
        """Handle incoming message from WebSocket client.

        Args:
            websocket: The WebSocket connection that sent the message
            message: JSON string with type and data
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "subscribe":
                requested = data.get("streams", [])
                valid = {s for s in requested if s in VALID_STREAM_TYPES}
                self.clients[websocket] = {"streams": valid}
                self._log_client_event(
                    "SUBSCRIBE", websocket, f"streams={sorted(valid)}"
                )
                confirmation = json.dumps(
                    {
                        "type": "subscription_update",
                        "timestamp": time.time(),
                        "data": {"streams": sorted(valid)},
                    }
                )
                await websocket.send(confirmation)
            elif msg_type == "status":
                clients_info = []
                for i, (ws, meta) in enumerate(self.clients.items()):
                    streams = sorted(meta["streams"])
                    clients_info.append(
                        {
                            "client": i,
                            "subscribed_streams": streams,
                            "is_you": ws is websocket,
                        }
                    )
                active = set()
                for meta in self.clients.values():
                    active |= meta["streams"]
                status_msg = json.dumps(
                    {
                        "type": "status",
                        "timestamp": time.time(),
                        "data": {
                            "total_clients": len(self.clients),
                            "clients": clients_info,
                            "active_streams": sorted(active),
                            "idle_streams": sorted(VALID_STREAM_TYPES - active),
                        },
                    }
                )
                await websocket.send(status_msg)
            elif msg_type == "tts":
                text = data.get("text", "")
                if text:
                    await self.send_tts(text)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse client message: {e}")
        except Exception as e:
            logger.error(f"Error handling client message: {e}")

    async def send_tts(self, text: str):
        """Send text-to-speech command to device.

        Args:
            text: Text to be spoken by the device
        """
        try:
            # Initialize device client if needed
            if self.device_client is None or self.device is None:
                logger.info("Initializing DeviceClient for TTS...")
                self.device_client = sdk_gen2.DeviceClient()
                config = sdk_gen2.DeviceClientConfig()
                self.device_client.set_client_config(config)
                self.device = self.device_client.connect()
                logger.info(f"Connected to device: {self.device.connection_id()}")

            # Send TTS command
            logger.info(f"Sending TTS: '{text}'")
            self.device.render_tts(text)
            logger.info("TTS command sent successfully")

            # Send confirmation back to all clients
            confirmation = json.dumps(
                {
                    "type": "tts_sent",
                    "timestamp": time.time(),
                    "data": {"text": text, "status": "success"},
                }
            )
            await self.broadcast(confirmation)
        except Exception as e:
            logger.error(f"Error sending TTS: {e}")
            # Send error back to clients
            error_msg = json.dumps(
                {
                    "type": "tts_sent",
                    "timestamp": time.time(),
                    "data": {"text": text, "status": "error", "error": str(e)},
                }
            )
            await self.broadcast(error_msg)

    def setup_receiver(self):
        """Setup StreamReceiver server to receive device data."""
        self.receiver = stream_receiver.StreamReceiver(
            enable_image_decoding=True, enable_raw_stream=False
        )

        # HttpServerConfig() requires TLS cert files at ~/.aria/streaming-certs/
        # to exist at construction time. Check both persistent/ and ephemeral/
        # directories (--use-ephemeral-certs writes to ephemeral/).
        # On machines where certs are missing, generate placeholders so the
        # constructor doesn't crash, then disable SSL for USB (local) streaming.
        base_cert_dir = os.path.join(
            os.path.expanduser("~"), ".aria", "streaming-certs"
        )
        needed_files = ["root_ca.pem", "subscriber.pem", "subscriber-key.pem"]

        # Check persistent/ first, then ephemeral/
        certs_exist = False
        for sub in ("persistent", "ephemeral"):
            cert_dir = os.path.join(base_cert_dir, sub)
            if all(os.path.isfile(os.path.join(cert_dir, f)) for f in needed_files):
                certs_exist = True
                logger.info(f"Streaming certs found in {cert_dir}")
                break

        if not certs_exist:
            cert_dir = os.path.join(base_cert_dir, "persistent")
            logger.warning(
                "Streaming certs missing — generating placeholders for USB mode"
            )
            os.makedirs(cert_dir, exist_ok=True)
            try:
                import subprocess as _sp

                _sp.run(
                    [
                        "openssl",
                        "req",
                        "-x509",
                        "-newkey",
                        "rsa:2048",
                        "-nodes",
                        "-keyout",
                        os.path.join(cert_dir, "subscriber-key.pem"),
                        "-out",
                        os.path.join(cert_dir, "subscriber.pem"),
                        "-days",
                        "365",
                        "-subj",
                        "/CN=aria-placeholder",
                    ],
                    capture_output=True,
                    timeout=10,
                )
                import shutil

                shutil.copy2(
                    os.path.join(cert_dir, "subscriber.pem"),
                    os.path.join(cert_dir, "root_ca.pem"),
                )
                logger.info(
                    "Placeholder certs generated — will use non-SSL USB streaming"
                )
            except Exception as e:
                logger.warning(f"Could not generate placeholder certs: {e}")

        config = sdk_gen2.HttpServerConfig()

        if not certs_exist:
            config.use_ssl = False
            logger.info("SSL disabled — streaming via USB local connection")

        config.address = "0.0.0.0"
        config.port = 6768
        self.receiver.set_server_config(config)

        # Register callbacks
        self.receiver.register_rgb_callback(self.on_rgb_frame)
        self.receiver.register_slam_callback(self.on_slam_frame)
        self.receiver.register_et_callback(self.on_et_frame)
        self.receiver.register_eye_gaze_callback(self.on_eye_gaze)
        self.receiver.register_hand_pose_callback(self.on_hand_tracking)
        self.receiver.register_vio_callback(self.on_vio)
        self.receiver.register_imu_callback(self.on_imu)
        self.receiver.register_audio_callback(self.on_audio)
        # Try to register PPG callback if available in SDK
        if hasattr(self.receiver, "register_ppg_callback"):
            self.receiver.register_ppg_callback(self.on_ppg)
            logger.info("PPG callback registered")
        else:
            logger.info("PPG callback not available in current SDK version")
        self.receiver.register_device_calib_callback(
            self.on_device_calib
        )  # For T_device_cpf

        logger.info("StreamReceiver configured with callbacks")

    def start_receiver(self):
        """Start the StreamReceiver HTTP server."""
        self.receiver.start_server()
        logger.info("StreamReceiver HTTP server started on port 6768")

    async def run(self):
        """Run the WebSocket server."""
        # Save event loop reference for callbacks
        self.loop = asyncio.get_running_loop()

        self.setup_receiver()
        self.start_receiver()

        logger.info(f"Starting WebSocket server on port {self.port}")

        async with websockets.serve(self.register_client, "0.0.0.0", self.port):
            logger.info(f"WebSocket server running on ws://0.0.0.0:{self.port}")

            # Run forever and print stats every 5 seconds
            while True:
                await asyncio.sleep(5)
                total = sum(self.frame_stats.values())
                logger.info(
                    f"Stats: RGB:{self.frame_stats['rgb']} "
                    f"SLAM:{self.frame_stats['slam']} "
                    f"Gaze:{self.frame_stats['eye_gaze']} "
                    f"Hand:{self.frame_stats['hand_tracking']} "
                    f"Audio:{self.frame_stats['audio']} "
                    f"VIO:{self.frame_stats['vio']} "
                    f"IMU:{self.frame_stats['imu']} "
                    f"Total:{total} | Clients:{len(self.clients)}"
                )

                # Broadcast device status (battery, wifi, temperature)
                await self._broadcast_device_status()

    async def _broadcast_device_status(self):
        """Poll and broadcast device telemetry (battery, wifi, temp) to clients."""
        try:
            status_client = sdk_gen2.DeviceClient()
            config = sdk_gen2.DeviceClientConfig()
            status_client.set_client_config(config)
            device = status_client.connect()

            serial = device.serial()
            status = device.status()
            battery = getattr(status, "battery_level", None)
            charging = getattr(status, "charging", None)
            wifi_connected = getattr(status, "wifi_connected", None)
            wifi_ssid = getattr(status, "wifi_ssid", None) if wifi_connected else None
            skin_temp = getattr(status, "skin_temp_celsius", None)
            thermal_triggered = getattr(status, "thermal_mitigation_triggered", None)

            message = json.dumps(
                {
                    "type": "device_status",
                    "timestamp": time.time(),
                    "data": {
                        "serial": serial,
                        "battery_level": battery,
                        "charging": charging,
                        "wifi_connected": wifi_connected,
                        "wifi_ssid": wifi_ssid,
                        "skin_temp_celsius": skin_temp,
                        "thermal_mitigation_triggered": thermal_triggered,
                    },
                }
            )
            await self.broadcast(message)
            temp_str = f"{skin_temp:.1f}°C" if skin_temp is not None else "N/A"
            logger.info(f"Device status: battery={battery}% temp={temp_str}")

            summary = self._error_limiter.flush_summary()
            if summary:
                logger.warning(summary)
        except Exception as e:
            logger.warning(f"Device status poll failed: {e}")


async def main():
    """Main entry point."""
    bridge = WebSocketBridge(port=17300)

    def _get_ppid(pid):
        """Get parent PID of a given process."""
        try:
            result = subprocess.run(
                ["ps", "-o", "ppid=", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return int(result.stdout.strip())
        except Exception:
            return 1

    # Orphan detection: stop streaming if parent process dies (terminal closed).
    # macOS Meta python3 is a wrapper: bash → python3(wrapper) → Python3.12(our code)
    # When terminal closes, bash dies → wrapper reparented to PID 1.
    # We check both direct parent (ppid) and grandparent (grandppid).
    initial_ppid = os.getppid()
    initial_grandppid = _get_ppid(initial_ppid)
    orphan_watch_active = True

    def _watch_parent():
        while orphan_watch_active:
            time.sleep(2)
            ppid = os.getppid()
            grandppid = _get_ppid(ppid) if ppid > 1 else 1
            if ppid != initial_ppid or grandppid != initial_grandppid:
                logger.info(
                    "Parent process died (terminal closed) — stopping streaming..."
                )
                aria_cli = os.path.join(os.path.dirname(sys.executable), "aria_gen2")
                try:
                    subprocess.run(
                        [aria_cli, "streaming", "stop"],
                        timeout=5,
                        capture_output=True,
                    )
                    logger.info("Streaming stopped via CLI")
                except Exception as e:
                    logger.warning(f"Error stopping streaming on parent exit: {e}")
                os._exit(0)

    threading.Thread(target=_watch_parent, daemon=True, name="parent-monitor").start()

    try:
        await bridge.run()
    except KeyboardInterrupt:
        pass
    finally:
        # Ctrl+C already handled by bash script's cleanup (aria_gen2 streaming stop).
        # Disable orphan watch so this process doesn't interfere with other terminals.
        orphan_watch_active = False


if __name__ == "__main__":
    # SIGINT handler: exit immediately — bash script handles aria_gen2 streaming stop.
    # Without this, asyncio's event loop + thread pool can hang for seconds on Ctrl+C.
    def _handle_sigint(signum, frame):
        logger.info("Received SIGINT — exiting immediately")
        os._exit(0)

    signal.signal(signal.SIGINT, _handle_sigint)

    # SIGHUP handler: when terminal window is closed, stop streaming before exit.
    # This fires BEFORE the process dies, unlike orphan detection which is a backup.
    def _handle_sighup(signum, frame):
        logger.info("Received SIGHUP (terminal closed) — stopping streaming...")
        aria_cli = os.path.join(os.path.dirname(sys.executable), "aria_gen2")
        try:
            subprocess.run(
                [aria_cli, "streaming", "stop"], timeout=5, capture_output=True
            )
            logger.info("Streaming stopped via CLI")
        except Exception as e:
            logger.warning(f"Error stopping streaming on SIGHUP: {e}")
        os._exit(0)

    signal.signal(signal.SIGHUP, _handle_sighup)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down WebSocket bridge")
