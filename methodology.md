# Methodology — Field Note #08

> **Status: AI-only preliminary for the both-hands layer.** Integrity, sharpness and yield arithmetic are measured; hand checks come from MediaPipe without human verification.

## Recordings
* Stereo rig, full session: 8,694 frames (290 s), left camera 1600×1200 at 30 fps, per-frame exposure, 501.7 Hz IMU on the device clock. No task annotation.
* Phone, knife prep (1,979 frames) and seasoning (1,978 frames): 1920×1080 at 30 fps, 410.6 Hz IMU aligned with the measured +188/+200 ms offset; human keystep annotation (Field Note #05).

## Layers per frame
1. **Integrity** — stereo: valid flags on both cameras, frame interval 16.7–50 ms, ≥3 IMU samples in the exposure, |stereo sync| ≤ 1 ms; phone: frame interval < 50 ms and ≥4 gyro samples within ±16.7 ms.
2. **Task** — phone only: frame not in a non-task keystep.
3. **Sharpness** — relative Laplacian variance (centre crop) ≥ τ (default 0.6) against low-motion frames within ±3 s (Field Note #06); if no reference exists, gyro rule (stereo predicted blur ≤ 1.5 px, phone ≤ 20 °/s).
4. **Both hands** — MediaPipe Hands 0.10.14, three passes (full, mirrored, lite), hand present if any pass finds it within ±2 frames (Field Note #07). Stereo frames 1,800–5,399 reuse the #07 detections (identical frames; a 100-frame re-run on the raw file matched exactly); other frames were detected on the raw file with the same pipeline.

## Yield
* Frame yield = accepted frames / captured frames.
* Clip yield = frames inside runs of accepted frames ≥ L s (L = 1, 3, 5); with gap tolerance g, rejected gaps of ≤ g frames between accepted frames are bridged first (bridged frames count as accepted).
* Capture hours per accepted hour = 1 / yield.
* Sensitivity: τ ∈ {0.4 … 0.8} × hand check ∈ {none, single pass, consensus}.
* Single-cause rejections: frames that pass all other criteria but fail one.

## Upstream checks
* Gyro-to-image map on the full stereo session: R² = 0.970; sharpness on overlapping frames identical to Field Note #06; blur correlation 0.9996.

## Limitations
AI-only hand layer; ~7 minutes of footage from three recordings; sharpness is a proxy; no task annotation on the stereo session; devices/tasks/operators differ; thresholds are illustrative.
