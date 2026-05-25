"""
Image encoding utilities for MJPEG streaming.
"""
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Blank frame shown when no stream is available
_BLANK_FRAME: bytes | None = None


def frame_to_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    """
    Encode a numpy BGR frame to JPEG bytes.

    Args:
        frame: OpenCV BGR frame (numpy array)
        quality: JPEG quality 1-100

    Returns:
        JPEG encoded bytes
    """
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    success, buffer = cv2.imencode(".jpg", frame, encode_params)
    if not success:
        raise ValueError("Failed to encode frame to JPEG")
    return buffer.tobytes()


def get_blank_frame(width: int = 640, height: int = 360) -> bytes:
    """
    Return a cached black JPEG frame used as placeholder when stream is unavailable.
    """
    global _BLANK_FRAME
    if _BLANK_FRAME is None:
        blank = np.zeros((height, width, 3), dtype=np.uint8)
        # Add "NO SIGNAL" text
        cv2.putText(
            blank, "NO SIGNAL", (width // 2 - 90, height // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (80, 80, 80), 2
        )
        _BLANK_FRAME = frame_to_jpeg(blank, quality=60)
    return _BLANK_FRAME
