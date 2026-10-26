"""Field Note #08 — usable-footage yield.
Combines per-frame layers (integrity, task, sharpness, hands) into frame yield, clip yield and
capture-hours per accepted hour, with threshold sensitivity.
Input: data/yield_frames.csv (one row per frame, see build_yield_table.py)
Usage: python yield_analysis.py data/yield_frames.csv OUT_DIR
"""
import sys, os, json
import numpy as np, pandas as pd
F = pd.read_csv(sys.argv[1]); OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
FPS = 30.0


def runs_ok(mask, min_frames):
    """Frames that belong to a contiguous accepted run of at least min_frames."""
    m = mask.astype(int).values; out = np.zeros(len(m), int); i = 0
    while i < len(m):
        if m[i]:
            j = i
            while j < len(m) and m[j]: j += 1
            if j - i >= min_frames: out[i:j] = 1
            i = j
        else:
            i += 1
    return out


def close_gaps(mask, g):
    """Bridge rejected gaps of at most g frames that sit between accepted frames (tolerance rule)."""
    m = np.asarray(mask, int).copy()
    if g <= 0: return m
    n = len(m); i = 0
    while i < n:
        if m[i] == 0:
            j = i
            while j < n and m[j] == 0: j += 1
            if i > 0 and j < n and (j - i) <= g: m[i:j] = 1
            i = j
        else: i += 1
    return m


def criteria(d, tau=0.6, hands='consensus'):
    c = {}
    c['integrity'] = d.integrity_ok == 1
    c['task'] = d.non_task.fillna(0) == 0
    sharp = d.rel_sharpness >= tau
    sharp = sharp.where(d.rel_sharpness.notna(), d.gyro_ok == 1)        # fallback to gyro rule when no reference
    c['sharp'] = sharp.astype(bool)
    if hands == 'none': c['hands'] = pd.Series(True, index=d.index)
    else: c['hands'] = d[f'{hands}_both'] == 1
    return c


R = {}
for rec, d in F.groupby('recording', sort=False):
    d = d.sort_values('frame').reset_index(drop=True); n = len(d)
    c = criteria(d)
    funnel = []; m = pd.Series(True, index=d.index)
    for k in ['integrity', 'task', 'sharp', 'hands']:
        m = m & c[k]; funnel.append(dict(step=k, frames=int(m.sum()), share=float(m.mean())))
    single = {k: float(v.mean()) for k, v in c.items()}
    acc = m
    clip = {str(L): float(runs_ok(acc, int(L * FPS)).mean()) for L in (1, 2, 3, 5)}
    runs = []; i = 0; a = acc.values
    while i < n:
        if a[i]:
            j = i
            while j < n and a[j]: j += 1
            runs.append((j - i) / FPS); i = j
        else: i += 1
    sens = []
    for tau in (0.4, 0.5, 0.6, 0.7, 0.8):
        for hm in ('none', 'single', 'consensus'):
            cc = criteria(d, tau, hm); mm = cc['integrity'] & cc['task'] & cc['sharp'] & cc['hands']
            y3 = runs_ok(mm, int(3 * FPS)).mean()
            sens.append(dict(tau=tau, hands=hm, frame_yield=float(mm.mean()), clip3_yield=float(y3),
                             capture_h_per_accepted_h=float(1 / mm.mean()) if mm.mean() > 0 else None,
                             capture_h_per_accepted_h_clip3=float(1 / y3) if y3 > 0 else None))
    tol = {}
    for gtol in (0, 3, 6, 15):
        mm = close_gaps(acc.values, gtol)
        tol[str(gtol)] = {str(L): float(runs_ok(pd.Series(mm), int(L * FPS)).mean()) for L in (1, 3, 5)}
    per_min = []
    for k0 in range(0, n, int(60 * FPS)):
        seg = acc.iloc[k0:k0 + int(60 * FPS)]
        if len(seg) >= 30 * FPS: per_min.append(dict(start_s=k0 / FPS, frames=len(seg), frame_yield=float(seg.mean()),
                                                   sharp=float(c['sharp'].iloc[k0:k0 + int(60 * FPS)].mean()), hands=float(c['hands'].iloc[k0:k0 + int(60 * FPS)].mean())))
    reasons = {}
    for k in ['integrity', 'task', 'sharp', 'hands']:
        others = [o for o in c if o != k]; om = pd.concat([c[o] for o in others], axis=1).all(axis=1)
        reasons[k] = int((om & ~c[k]).sum())            # frames rejected ONLY by this criterion
    R[rec] = dict(frames=n, duration_s=n / FPS, task_annotation=bool(d.non_task.notna().any()), single_criterion_pass=single,
                  funnel=funnel, frame_yield=float(acc.mean()), clip_yield=clip, accepted_runs=len(runs),
                  median_run_s=float(np.median(runs)) if runs else 0.0, clip_yield_with_gap_tolerance=tol, per_minute=per_min, sole_rejection_reason=reasons, sensitivity=sens)
    d['accepted'] = acc.astype(int); d['accepted_clip3'] = runs_ok(acc, int(3 * FPS))
    d[['recording', 'frame', 'accepted', 'accepted_clip3']].to_csv(f'{OUT}/accepted_{rec}.csv', index=False)
json.dump(R, open(f'{OUT}/yield_results.json', 'w'), indent=1)
for rec, r in R.items():
    print(rec, r['frames'], 'frame yield %.3f' % r['frame_yield'], 'clip3 %.3f' % r['clip_yield']['3'], [(f['step'], round(f['share'], 3)) for f in r['funnel']])
