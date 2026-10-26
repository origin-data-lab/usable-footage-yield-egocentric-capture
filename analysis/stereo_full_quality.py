"""Per-frame quality layers for the full 8,694-frame stereo session (left camera).
Integrity (flags, timing, IMU coverage, stereo sync), gyro-predicted blur, relative sharpness.
Usage: python stereo_full_quality.py <left_raw.mp4> <frame_timestamps_full.csv> <imu_full.csv> <out.csv> <out_meta.json>
"""
import sys, json, subprocess
import numpy as np, pandas as pd, cv2
V, TS, IMU, OUT, META = sys.argv[1:6]
OFF = -1100.0  # camera-IMU offset, us (estimated, Field Note #03)
FAST = cv2.FastFeatureDetector_create(threshold=20)


def frames(path, W, H, vf=None):
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path] + (['-vf', vf] if vf else []) + ['-pix_fmt', 'gray', '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    while True:
        b = p.stdout.read(W * H)
        if len(b) < W * H: break
        yield np.frombuffer(b, np.uint8).reshape(H, W)


ft = pd.read_csv(TS); im = pd.read_csv(IMU)
q = []
for g in frames(V, 1600, 1200):
    c = np.ascontiguousarray(g[300:900, 400:1200]); q.append((cv2.Laplacian(c, cv2.CV_64F).var(), len(FAST.detect(c, None))))
q = np.array(q)
mot = []; prev = None
for g in frames(V, 400, 300, 'scale=400:300'):
    row = [np.nan] * 2
    if prev is not None:
        pts = cv2.goodFeaturesToTrack(prev, 400, 0.01, 8)
        if pts is not None and len(pts) > 20:
            nx, st, _ = cv2.calcOpticalFlowPyrLK(prev, g, pts, None, winSize=(21, 21), maxLevel=3); ok = st.ravel() == 1
            M, _ = cv2.estimateAffinePartial2D(pts[ok], nx[ok], method=cv2.RANSAC, ransacReprojThreshold=2.0)
            if M is not None:
                row = [M[0, 2] + (M[0, 0] - 1) * 200 + M[0, 1] * 150, M[1, 2] + M[1, 0] * 200 + (M[1, 1] - 1) * 150]
    mot.append(row); prev = g
mot = np.array(mot) * 4.0
n = min(len(q), len(ft), len(mot)); ft = ft.iloc[:n]; q = q[:n]; mot = mot[:n]
ti = im.timestamp_us.values.astype(float); G = im[['gyro_x_rad_s', 'gyro_y_rad_s', 'gyro_z_rad_s']].values
st = ft.left_exposure_start_us.values + OFF; ex = ft.left_exposure_time_us.values.astype(float)
idx0 = np.searchsorted(ti, st); idx1 = np.searchsorted(ti, st + ex, side='right')
wexp = np.array([G[a:b].mean(0) if b > a else [np.nan] * 3 for a, b in zip(idx0, idx1)]); nimu = idx1 - idx0
ctr = ft.left_exposure_centre_us.values + OFF
c0 = np.searchsorted(ti, ctr[:-1]); c1 = np.searchsorted(ti, ctr[1:])
rot = np.vstack([[np.nan] * 3] + [G[a:b].mean(0) * (ctr[i + 1] - ctr[i]) * 1e-6 if b > a else [np.nan] * 3 for i, (a, b) in enumerate(zip(c0, c1))])
ok = ~np.isnan(mot[:, 0]) & ~np.isnan(rot[:, 0])
A, *_ = np.linalg.lstsq(rot[ok], mot[ok], rcond=None)
r2 = 1 - ((mot[ok] - rot[ok] @ A) ** 2).sum() / ((mot[ok] - mot[ok].mean(0)) ** 2).sum()
blur = np.linalg.norm(wexp @ A, axis=1) * ex * 1e-6
dt = np.diff(ft.left_exposure_centre_us.values, prepend=np.nan) / 1000.0
d = pd.DataFrame(dict(frame=np.arange(n), time_s=(ft.left_exposure_centre_us.values - ft.left_exposure_centre_us.values[0]) / 1e6,
                      exposure_ms=ex / 1000, interval_ms=dt, imu_samples_in_exposure=nimu,
                      stereo_sync_us=(ft.right_exposure_centre_us - ft.left_exposure_centre_us).values,
                      flags_ok=((ft.left_valid_flags == '0x07') & (ft.right_valid_flags == '0x07')).astype(int).values,
                      sharpness=q[:, 0], fast=q[:, 1], blur_px_pred=blur, rotation_dps=np.degrees(np.linalg.norm(wexp, axis=1))))


def rel(x, key, low, win=90, minn=6):
    r = np.full(len(x), np.nan)
    for i in range(len(x)):
        a, b = max(0, i - win), min(len(x), i + win + 1); s = x[a:b][key[a:b] < low]
        if len(s) >= minn: r[i] = x[i] / np.median(s)
    return r


d['rel_sharpness'] = rel(d.sharpness.values, np.nan_to_num(d.blur_px_pred.values, nan=99), 0.35)
d.to_csv(OUT, index=False)
json.dump(dict(frames=n, map_r2=float(r2), map=A.T.tolist(), imu_rows=len(im)), open(META, 'w'), indent=1)
print('frames', n, 'R2', round(r2, 4))
