"""
Pure-numpy 3D renderer (no GPU, no paid tools).

TerrainScene : perspective height-field renderer (voxel-space / ray-column),
               used for mountains, volcanoes, dunes, canyons, oceans, glaciers, hills.
SpaceScene   : ray-traced planet + rings + starfield.
CityScene    : extruded-building skyline flythrough (painter's algorithm).

Every scene exposes  render(t, T) -> (rgb float32 HxWx3 in 0..1, info dict)
where t is the local time and T the scene duration.
"""
import numpy as np
import cv2

# ----------------------------------------------------------------- moods
MOODS = {
    #            sky_top            sky_horizon        sun_color          ambient            fog_dens  sun_az sun_el
    "alpine":  ((0.10, 0.25, 0.55), (0.62, 0.76, 0.92), (1.00, 0.96, 0.88), (0.35, 0.45, 0.60), 0.0016, 0.6, 0.55),
    "arctic":  ((0.18, 0.30, 0.48), (0.80, 0.86, 0.93), (0.95, 0.97, 1.00), (0.45, 0.52, 0.62), 0.0022, 2.2, 0.25),
    "storm":   ((0.06, 0.08, 0.11), (0.33, 0.38, 0.43), (0.60, 0.66, 0.72), (0.22, 0.26, 0.31), 0.0034, 1.0, 0.45),
    "dusk":    ((0.10, 0.07, 0.22), (0.98, 0.52, 0.30), (1.00, 0.62, 0.38), (0.30, 0.24, 0.40), 0.0020, 3.4, 0.10),
    "golden":  ((0.22, 0.32, 0.55), (1.00, 0.80, 0.55), (1.00, 0.82, 0.58), (0.36, 0.36, 0.45), 0.0017, 4.0, 0.14),
    "night":   ((0.01, 0.02, 0.07), (0.14, 0.20, 0.36), (0.70, 0.80, 1.10), (0.16, 0.20, 0.32), 0.0026, 5.2, 0.35),
    "blood":   ((0.10, 0.02, 0.03), (0.75, 0.22, 0.12), (1.00, 0.45, 0.30), (0.28, 0.12, 0.14), 0.0024, 2.8, 0.12),
    "desert":  ((0.20, 0.42, 0.72), (0.95, 0.85, 0.70), (1.00, 0.93, 0.80), (0.45, 0.42, 0.40), 0.0012, 1.4, 0.40),
}

PALETTES = {  # low, mid, high (rock), snow
    "rock":    ((0.16, 0.15, 0.14), (0.34, 0.31, 0.29), (0.45, 0.43, 0.42), (0.93, 0.96, 1.00)),
    "dark":    ((0.08, 0.08, 0.09), (0.20, 0.19, 0.19), (0.30, 0.29, 0.30), (0.90, 0.93, 0.98)),
    "green":   ((0.10, 0.20, 0.08), (0.22, 0.32, 0.14), (0.40, 0.38, 0.32), (0.93, 0.96, 1.00)),
    "sand":    ((0.62, 0.42, 0.22), (0.80, 0.58, 0.32), (0.92, 0.72, 0.45), (0.98, 0.88, 0.70)),
    "canyon":  ((0.42, 0.16, 0.08), (0.66, 0.30, 0.14), (0.85, 0.52, 0.30), (0.95, 0.80, 0.62)),
    "volcano": ((0.06, 0.05, 0.05), (0.14, 0.11, 0.10), (0.24, 0.20, 0.18), (0.70, 0.70, 0.72)),
    "ocean":   ((0.01, 0.06, 0.12), (0.03, 0.17, 0.28), (0.10, 0.35, 0.45), (0.85, 0.95, 1.00)),
    "ice":     ((0.30, 0.45, 0.60), (0.55, 0.70, 0.82), (0.80, 0.88, 0.95), (0.96, 0.98, 1.00)),
}


def _spectral(N, beta, rng):
    kx = np.fft.fftfreq(N)[:, None]
    ky = np.fft.fftfreq(N)[None, :]
    k = np.sqrt(kx ** 2 + ky ** 2)
    k[0, 0] = 1.0
    amp = k ** (-beta / 2.0)
    amp[0, 0] = 0
    ph = rng.uniform(0, 2 * np.pi, (N, N))
    f = amp * np.exp(1j * ph)
    n = np.real(np.fft.ifft2(f))
    n -= n.mean()
    n /= (np.abs(n).max() + 1e-9)
    return n


def make_heightmap(preset, seed, N=1024):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32) / N - 0.5
    r = np.sqrt(xx ** 2 + yy ** 2)
    ridged = (1 - np.abs(_spectral(N, 3.0, rng))) ** 2.2
    smooth = _spectral(N, 3.0, rng) * 0.5 + 0.5
    fine = _spectral(N, 2.1, rng)
    falloff = np.clip(1 - r / 0.5, 0, 1) ** 0.7
    ang = rng.uniform(0, np.pi)
    ca, sa = np.cos(ang), np.sin(ang)
    u = xx * ca - yy * sa
    v = xx * sa + yy * ca

    if preset == "pyramid":       # K2-like faceted pyramid
        d = (np.abs(u) ** 1.15 + np.abs(v) ** 1.15) ** (1 / 1.15)
        peak = np.clip(1 - d / 0.30, 0, 1) ** 1.25
    elif preset == "horn":        # Matterhorn-like sharp horn
        d = (np.abs(u) ** 1.05 + np.abs(v * 1.15) ** 1.05) ** (1 / 1.05)
        peak = np.clip(1 - d / 0.22, 0, 1) ** 1.9
    elif preset == "wall":        # Eiger-like vertical north face
        d = np.sqrt((u * 0.75) ** 2 + (v * 1.6) ** 2)
        peak = np.clip(1 - d / 0.30, 0, 1) ** 1.1
        face = np.clip((v + 0.02) * 30, 0, 1)        # cut one side steep
        peak = peak * (0.25 + 0.75 * face) + np.clip(1 - d / 0.30, 0, 1) ** 3 * (1 - face) * 0.2
    elif preset == "massif":      # Annapurna/Kangchenjunga style long massif with several summits
        peak = np.zeros_like(r)
        for i, (o, h, w) in enumerate([(-0.17, 0.78, 0.15), (0.0, 1.0, 0.17), (0.15, 0.86, 0.14), (0.27, 0.6, 0.10)]):
            d = np.sqrt(((u - o) * 1.0) ** 2 + (v * 1.7) ** 2)
            peak = np.maximum(peak, h * np.clip(1 - d / w / 1.6, 0, 1) ** 1.3)
    elif preset == "dome":        # Mont Blanc / Denali broad white dome
        d = np.sqrt(u ** 2 + (v * 1.2) ** 2)
        peak = np.clip(1 - (d / 0.33) ** 1.6, 0, 1) ** 1.3
    elif preset == "everest":     # tall triangular with ridges
        d = (np.abs(u) ** 1.3 + np.abs(v * 1.1) ** 1.3) ** (1 / 1.3)
        peak = np.clip(1 - d / 0.30, 0, 1) ** 1.35
        peak = np.maximum(peak, 0.72 * np.clip(1 - np.sqrt((u - 0.17) ** 2 + (v * 1.5) ** 2) / 0.17, 0, 1) ** 1.4)
    elif preset == "volcano":
        d = r * 1.0
        peak = np.clip(1 - d / 0.36, 0, 1) ** 1.6
        crater = np.exp(-(d / 0.035) ** 2) * 0.28
        peak = peak - crater
    elif preset == "dunes":
        w = np.sin((u * 14 + smooth * 3) * np.pi) * 0.5 + 0.5
        peak = (w ** 2.5) * 0.35 + smooth * 0.2
        ridged = ridged * 0.1
    elif preset == "canyon":
        river = np.abs(v + 0.08 * np.sin(u * 12) + 0.04 * np.sin(u * 31))
        peak = 0.55 + 0.15 * smooth - 0.55 * np.clip(1 - river / 0.09, 0, 1) ** 0.6
        peak = np.round(peak * 9) / 9 * 0.5 + peak * 0.5   # terraces
    elif preset == "hills":
        peak = smooth * 0.55
    elif preset == "ocean":
        peak = np.zeros_like(r)
    else:
        raise ValueError(preset)

    if preset == "ocean":
        h = 0.02 * smooth
    elif preset in ("dunes",):
        h = peak + 0.03 * fine
    elif preset in ("canyon",):
        h = peak + 0.05 * ridged + 0.02 * fine
    else:
        # radial ridges & couloirs: ridged noise sampled in polar coordinates
        theta = (np.arctan2(v, u) / (2 * np.pi)) % 1.0
        rad_tex = cv2.resize(((1 - np.abs(_spectral(48, 1.8, rng))) ** 2.5).astype(np.float32), (N, N), interpolation=cv2.INTER_CUBIC)
        mx = (theta * N).astype(np.float32)
        my = ((r * 1.6 + 0.07 * smooth) * N % N).astype(np.float32)
        radial = cv2.remap(rad_tex.astype(np.float32), mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        base = (0.5 * ridged + 0.5 * smooth) * 0.22 * falloff
        detail = 0.65 * radial + 0.35 * ridged
        h = base + peak * (0.80 + 0.22 * detail) - 0.22 * peak * (1 - peak) * (1 - radial) + 0.012 * fine * (0.3 + peak)
    h = cv2.GaussianBlur(h.astype(np.float32), (0, 0), 1.3)
    h -= h.min()
    h /= h.max() + 1e-9
    return h.astype(np.float32)


def bake_colors(h, height_scale, palette, mood, seed, snowline=0.55, lava=False):
    """Precompute lit albedo per texel (sun lighting, AO, snow)."""
    N = h.shape[0]
    rng = np.random.default_rng(seed + 7)
    sky_top, sky_hor, sun_col, amb, _, saz, sel = MOODS[mood]
    lo, mid, hi, snow = [np.array(c, np.float32) for c in PALETTES[palette]]
    H = h * height_scale
    gx = (np.roll(H, -1, 1) - np.roll(H, 1, 1)) * 0.5
    gy = (np.roll(H, -1, 0) - np.roll(H, 1, 0)) * 0.5
    nrm = np.stack([-gx, -gy, np.ones_like(H)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    sun = np.array([np.cos(saz) * np.cos(sel), np.sin(saz) * np.cos(sel), np.sin(sel)], np.float32)
    lam = np.clip((nrm * sun).sum(-1), 0, 1)
    # soft shadow approximation: compare to blurred height in the sun direction
    shift = (int(round(-np.cos(saz) * 6)), int(round(-np.sin(saz) * 6)))
    sh = np.roll(H, shift, axis=(1, 0))
    shadow = np.clip(1 - (sh - H - 2.0) * 0.08, 0.35, 1.0)
    shadow = cv2.GaussianBlur(shadow.astype(np.float32), (0, 0), 2)
    ao = np.clip(1 + (H - cv2.GaussianBlur(H, (0, 0), 10)) * 0.025, 0.55, 1.15)
    slope = 1 - nrm[..., 2]
    noise = _spectral(N, 2.2, rng) * 0.5 + 0.5
    # albedo by height
    t = np.clip(h / 0.75, 0, 1)[..., None]
    alb = np.where(t < 0.5, lo + (mid - lo) * (t / 0.5), mid + (hi - mid) * ((t - 0.5) / 0.5))
    alb = alb * (0.8 + 0.4 * noise[..., None])
    # snow
    sl = snowline + (noise - 0.5) * 0.16
    snow_m = np.clip((h - sl) * 12, 0, 1) * np.clip((0.62 - slope) * 4.0, 0, 1)
    if palette in ("ocean",):
        snow_m = np.clip((noise - 0.86) * 10, 0, 1) * 0.6   # foam
    alb = alb * (1 - snow_m[..., None]) + snow * snow_m[..., None]
    light = (lam * shadow)[..., None] * np.array(sun_col) * 1.15 + np.array(amb) * (0.55 + 0.45 * nrm[..., 2:3])
    col = alb * light * ao[..., None]
    if lava:
        glow = np.clip(1 - h / 0.25, 0, 1) ** 3 * np.clip((noise - 0.55) * 6, 0, 1)
        col += glow[..., None] * np.array([1.4, 0.35, 0.05])
    return col.astype(np.float32)


def _bilinear(arr, x, y):
    N = arr.shape[0]
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    fx = (x - x0)[..., None] if arr.ndim == 3 else (x - x0)
    fy = (y - y0)[..., None] if arr.ndim == 3 else (y - y0)
    x0 %= N
    y0 %= N
    x1 = (x0 + 1) % N
    y1 = (y0 + 1) % N
    a = arr[y0, x0]
    b = arr[y0, x1]
    c = arr[y1, x0]
    d = arr[y1, x1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def sky_image(W, H, mood, horizon, yaw, t):
    sky_top, sky_hor, sun_col, amb, _, saz, sel = MOODS[mood]
    y = np.arange(H, dtype=np.float32)[:, None]
    g = np.clip((horizon - y) / (H * 0.9), 0, 1) ** 0.6
    top = np.array(sky_top, np.float32)
    hor = np.array(sky_hor, np.float32)
    img = hor + (top - hor) * g[..., None]
    img = np.broadcast_to(img, (H, W, 3)).copy()
    # sun / moon glow
    fov = np.deg2rad(70)
    da = (saz - yaw + np.pi) % (2 * np.pi) - np.pi
    sx = W / 2 + np.tan(np.clip(da, -1.4, 1.4)) * (W / 2) / np.tan(fov / 2)
    sy = horizon - np.tan(sel) * (W / 2) / np.tan(fov / 2)
    xx = np.arange(W, dtype=np.float32)[None, :]
    d = np.sqrt((xx - sx) ** 2 + (y - sy) ** 2) / W
    if abs(da) < 1.3:
        glow = np.exp(-d * 6) * 0.55 + np.exp(-d * 40) * 1.4
        img += glow[..., None] * np.array(sun_col)
    if mood == "night":
        rng = np.random.default_rng(3)
        n = 260
        px = ((rng.uniform(0, 2 * np.pi, n) - yaw) % (2 * np.pi)) / (2 * np.pi) * W * 5 - W * 2
        py = rng.uniform(0, horizon * 0.95, n)
        br = rng.uniform(0.3, 1, n) * (0.7 + 0.3 * np.sin(t * 3 + np.arange(n)))
        for x, yy, b in zip(px, py, br):
            if 0 <= x < W and 0 <= yy < H:
                img[int(yy), int(x)] += b
    return img


class TerrainScene:
    def __init__(self, W, H, preset="pyramid", mood="storm", palette="rock", seed=1,
                 height_scale=260.0, snowline=0.5, particles="snow", orbit=0.9,
                 radius=250.0, cam_height=0.92, start_angle=None, lava=False,
                 waves=False, clouds=True, peak_screen_y=0.47, **_):
        self.W, self.H = W, H
        self.N = 1024
        self.preset, self.mood, self.seed = preset, mood, seed
        self.hmap = make_heightmap(preset, seed, self.N)
        self.hs = height_scale
        self.Hm = self.hmap * height_scale
        self.col = bake_colors(self.hmap, height_scale, palette, mood, seed, snowline, lava)
        self.fov = np.deg2rad(70)
        self.f = (W / 2) / np.tan(self.fov / 2)
        self.zs = (np.geomspace(1.5, 1500, 420)).astype(np.float32)
        self.cols = (np.arange(W, dtype=np.float32) - W / 2) / self.f
        self.orbit, self.radius, self.cam_height = orbit, radius, cam_height
        rng = np.random.default_rng(seed)
        self.a0 = rng.uniform(0, 2 * np.pi) if start_angle is None else start_angle
        self.particles = particles
        self.pp = rng.uniform(-1, 1, (450, 3)).astype(np.float32)
        self.waves = waves
        self.peak_screen_y = peak_screen_y
        self.clouds = clouds
        cy, cx = np.unravel_index(np.argmax(self.hmap), self.hmap.shape)
        self.peak = np.array([cx, cy, self.Hm[cy, cx]], np.float32)
        fog = MOODS[mood]
        self.fog_col = np.array(fog[1], np.float32)
        self.fog_d = fog[4]
        if clouds:
            self.cloud = (_spectral(512, 2.6, rng) * 0.5 + 0.5).astype(np.float32)

    def camera(self, t, T):
        s = t / max(T, 1e-6)
        e = s * s * (3 - 2 * s)
        ang = self.a0 + self.orbit * (0.65 * s + 0.35 * e)
        rad = self.radius * (1.12 - 0.22 * e)
        cx = self.peak[0] - np.cos(ang) * rad
        cy = self.peak[1] - np.sin(ang) * rad
        ch = self.peak[2] * self.cam_height + 6 * np.sin(t * 0.7)
        ground = _bilinear(self.Hm, np.array([cx]), np.array([cy]))[0]
        ch = max(ch, ground + 12)
        yaw = ang + 0.04 * np.sin(t * 0.5)
        return np.array([cx, cy, ch], np.float32), yaw

    def render(self, t, T):
        W, H = self.W, self.H
        cam, yaw = self.camera(t, T)
        fwd = np.array([np.cos(yaw), np.sin(yaw)], np.float32)
        right = np.array([-np.sin(yaw), np.cos(yaw)], np.float32)
        # horizon so the summit sits at ~36% of screen height
        rel = self.peak[:2] - cam[:2]
        dpk = max(float(rel @ fwd), 1.0)
        horizon = self.peak_screen_y * H + (self.peak[2] - cam[2]) / dpk * self.f
        horizon = float(np.clip(horizon, 0.15 * H, 0.95 * H))

        zs = self.zs
        px = cam[0] + zs[:, None] * (fwd[0] + self.cols[None, :] * right[0])
        py = cam[1] + zs[:, None] * (fwd[1] + self.cols[None, :] * right[1])
        hm = self.Hm
        if self.waves:
            hh = _bilinear(hm, px, py) + 2.2 * np.sin(px * 0.09 + t * 1.6) * np.cos(py * 0.07 - t * 1.1) \
                 + 1.2 * np.sin(px * 0.21 - py * 0.13 + t * 2.3)
        else:
            hh = _bilinear(hm, px, py)
        ys = horizon - (hh - cam[2]) / zs[:, None] * self.f            # K x W
        M = np.minimum.accumulate(ys, axis=0)
        M = np.clip(M, -2 * H, 2 * H)
        K = len(zs)
        BIG = 5.0 * H
        keys = (np.arange(W, dtype=np.float64)[None, :] * BIG + (-M.astype(np.float64))).T.ravel()  # col-major
        rows = np.arange(H, dtype=np.float64)
        q = (np.arange(W, dtype=np.float64)[None, :] * BIG + (-rows[:, None])).ravel()  # H x W
        idx = np.searchsorted(keys, q, side="left").reshape(H, W)
        k = idx - (np.arange(W)[None, :] * K)
        sky_mask = k >= K
        k = np.clip(k, 0, K - 1)

        colk = _bilinear(self.col, px, py)                               # K x W x 3
        if self.waves:
            spec = np.clip(np.sin(px * 0.09 + t * 1.6 + 1.2), 0, 1) ** 8 * 0.35
            colk = colk + spec[..., None] * np.array(MOODS[self.mood][2])
        fogt = np.exp(-zs * self.fog_d)[:, None, None]
        # height fog: low valleys mistier
        hf = np.clip(1 - hh / (self.hs * 0.35), 0, 1)[..., None] * 0.35
        fogt = fogt * (1 - hf)
        colk = colk * fogt + self.fog_col * (1 - fogt)
        img = colk[k, np.arange(W)[None, :]]
        sky = sky_image(W, H, self.mood, horizon, yaw, t)
        img = np.where(sky_mask[..., None], sky, img)

        if self.clouds:
            img = self._clouds(img, horizon, yaw, t)
        info = {"horizon": horizon, "cam": cam, "yaw": yaw}
        # project summit for 3D pin
        relp = self.peak[:2] - cam[:2]
        d = float(relp @ fwd)
        if d > 5:
            lx = float(relp @ right) / d
            info["peak_xy"] = (W / 2 + lx * self.f, horizon - (self.peak[2] - cam[2]) / d * self.f)
        return img.astype(np.float32), info

    def _clouds(self, img, horizon, yaw, t):
        H, W = img.shape[:2]
        n = self.cloud.shape[0]
        y = np.arange(int(horizon), dtype=np.float32)
        if len(y) < 4:
            return img
        d = (horizon - y + 1)
        vz = 260.0 / d * (self.f / W) * 60       # depth of cloud plane
        xs = (np.arange(W, dtype=np.float32) - W / 2) / self.f
        u = (vz[:, None] * xs[None, :] * 0.6 + yaw * 120 + t * 4) % n
        v = (vz[:, None] * 0.5 + t * 2) % n
        c = _bilinear(self.cloud, u, np.broadcast_to(v, u.shape))
        c = np.clip((c - 0.55) * 2.2, 0, 1) * np.clip(d / (H * 0.25), 0, 1)[:, None] * 0.55
        ccol = np.array(MOODS[self.mood][1], np.float32) * 0.85 + 0.15
        img[: len(y)] = img[: len(y)] * (1 - c[..., None]) + ccol * c[..., None]
        return img

    def draw_particles(self, frame, info, t, scale):
        """Snow / ash / dust particles in camera space, drawn on the full-res frame (uint8 BGR)."""
        if not self.particles:
            return
        H, W = frame.shape[:2]
        p = self.pp.copy()
        speed = {"snow": (0.25, -0.18), "ash": (0.05, -0.05), "dust": (0.4, 0.02), "spray": (0.1, 0.1)}[self.particles]
        p[:, 0] = (p[:, 0] + t * speed[0] + 1) % 2 - 1
        p[:, 1] = (p[:, 1] + t * speed[1] + 1) % 2 - 1
        z = (p[:, 2] + 1) * 0.5 * 0.9 + 0.08
        x = W / 2 + p[:, 0] / z * W * 0.5
        y = H / 2 - p[:, 1] / z * H * 0.5
        rad = np.clip(1.1 / z * scale, 1, 6)
        col = {"snow": (245, 245, 250), "ash": (120, 160, 255), "dust": (150, 200, 230), "spray": (240, 240, 230)}[self.particles]
        ov = frame.copy()
        for xi, yi, ri, zi in zip(x, y, rad, z):
            if -20 < xi < W + 20 and -20 < yi < H + 20:
                cv2.circle(ov, (int(xi), int(yi)), int(ri), col, -1, cv2.LINE_AA)
        cv2.addWeighted(ov, 0.45, frame, 0.55, 0, frame)


class SpaceScene:
    def __init__(self, W, H, seed=1, planet=(0.75, 0.45, 0.25), rings=True, **_):
        self.W, self.H = W, H
        rng = np.random.default_rng(seed)
        self.tex = (_spectral(512, 2.4, rng) * 0.5 + 0.5).astype(np.float32)
        self.band = (_spectral(512, 3.5, rng) * 0.5 + 0.5).astype(np.float32)
        self.pc = np.array(planet, np.float32)
        self.rings = rings
        self.stars = rng.uniform(0, 1, (900, 3))

    def render(self, t, T):
        W, H = self.W, self.H
        img = np.zeros((H, W, 3), np.float32) + np.array([0.01, 0.012, 0.03])
        for sx, sy, b in self.stars:
            x = int((sx * W * 1.3 - t * 6) % W)
            y = int(sy * H)
            img[y, x] += b * (0.6 + 0.4 * np.sin(t * 2 + sx * 50))
        s = t / T
        R = H * (0.2 + 0.04 * s)
        cx, cy = W * 0.5, H * 0.7
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        nx = (xx - cx) / R
        ny = (yy - cy) / R
        rr = nx ** 2 + ny ** 2
        m = rr < 1
        nz = np.sqrt(np.clip(1 - rr, 0, 1))
        lon = np.arctan2(nx, nz) + t * 0.15
        lat = np.arcsin(np.clip(ny, -1, 1))
        u = ((lon / (2 * np.pi)) % 1) * 511
        v = ((lat / np.pi + 0.5) * 511)
        b = _bilinear(self.band, np.full_like(u, 7.0), v * 3 % 511)
        tx = _bilinear(self.tex, u, v)
        alb = self.pc * (0.6 + 0.5 * b[..., None]) * (0.85 + 0.3 * tx[..., None])
        L = np.array([-0.6, -0.35, 0.72])
        L /= np.linalg.norm(L)
        lam = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
        planet = alb * (lam[..., None] * 1.2 + 0.03)
        rim = np.clip(1 - nz, 0, 1) ** 3 * lam
        planet += rim[..., None] * np.array([0.4, 0.6, 1.0]) * 0.6
        img = np.where(m[..., None], planet, img)
        glow = np.exp(-np.clip(np.sqrt(rr) - 1, 0, None) * 8) * (~m)
        img += glow[..., None] * np.array([0.25, 0.35, 0.6]) * 0.5
        if self.rings:
            tilt = 0.28
            ry = (yy - cy) / (R * tilt)
            rx = (xx - cx) / R
            rd = np.sqrt(rx ** 2 + ry ** 2)
            ring = ((rd > 1.35) & (rd < 2.3)).astype(np.float32)
            ring *= 0.5 + 0.5 * np.sin(rd * 40) * np.sin(rd * 13)
            front = (ry > 0) | (~m)
            a = ring * front * 0.75
            img = img * (1 - a[..., None]) + np.array([0.85, 0.75, 0.6]) * a[..., None] * 0.9
        return img, {}

    def draw_particles(self, *a, **k):
        pass


class CityScene:
    def __init__(self, W, H, seed=1, mood="night", **_):
        self.W, self.H = W, H
        rng = np.random.default_rng(seed)
        self.mood = mood
        n = 26
        self.b = []
        for i in range(-n, n):
            for j in range(2, 70):
                if rng.random() < 0.55:
                    continue
                h = rng.lognormal(3.0, 0.65) * (1.8 if abs(i) < 3 and j < 20 else 1)
                if abs(i) < 1:
                    continue
                self.b.append((i * 14.0 + rng.uniform(-2, 2), j * 14.0, rng.uniform(6, 11), rng.uniform(6, 11), min(h, 260), rng.random()))
        self.b = np.array(self.b, np.float32)

    def render(self, t, T):
        W, H = self.W, self.H
        f = (W / 2) / np.tan(np.deg2rad(35))
        camz = 18 + t * 9
        camy = 38 + 18 * (t / T)
        horizon = H * 0.42
        sky = sky_image(W, H, self.mood, horizon, 0, t)
        img = (np.clip(sky, 0, 1) * 255).astype(np.uint8).copy()
        # ground
        cv2.rectangle(img, (0, int(horizon)), (W, H), (14, 10, 10) if self.mood == "night" else (60, 60, 60), -1)
        order = np.argsort(-(self.b[:, 1] - camz))
        for k in order:
            x, z, w, d, h, r = self.b[k]
            z0 = z - camz
            if z0 < 2:
                continue
            def P(X, Y, Z):
                return (int(W / 2 + X / Z * f), int(horizon - (Y - camy) / Z * f))
            x0, x1 = x - w / 2, x + w / 2
            za, zb = z0, z0 + d
            fog = np.exp(-z0 * 0.006)
            base = np.array([40, 30, 35]) if self.mood == "night" else np.array([150, 150, 160])
            front = [P(x0, 0, za), P(x1, 0, za), P(x1, h, za), P(x0, h, za)]
            side = [P(x1 if x < 0 else x0, 0, za), P(x1 if x < 0 else x0, 0, zb), P(x1 if x < 0 else x0, h, zb), P(x1 if x < 0 else x0, h, za)]
            cv2.fillConvexPoly(img, np.array(side), tuple(int(c) for c in base * 0.6 * fog + 20 * (1 - fog)), cv2.LINE_AA)
            cv2.fillConvexPoly(img, np.array(front), tuple(int(c) for c in base * fog + 20 * (1 - fog)), cv2.LINE_AA)
            # windows
            if self.mood == "night" and z0 < 400:
                fx0, fy0 = front[0]
                fx1, fy1 = front[2]
                rows = int(h / 3.5)
                cols = int(w / 2.5)
                rng = np.random.default_rng(int(k))
                lit = rng.random((rows, cols)) < 0.35
                for a in range(rows):
                    for c in range(cols):
                        if lit[a, c]:
                            px = int(fx0 + (fx1 - fx0) * (c + 0.5) / cols)
                            py = int(fy0 + (fy1 - fy0) * (a + 0.5) / rows)
                            cv2.circle(img, (px, py), max(1, int(60 / z0)), (255, 205, 110), -1)
        return img.astype(np.float32) / 255.0, {"peak_xy": (W / 2, horizon * 0.6)}

    def draw_particles(self, *a, **k):
        pass


def make_scene(spec, W, H):
    typ = spec.get("type", "terrain")
    if typ == "terrain":
        return TerrainScene(W, H, **{k: v for k, v in spec.items() if k != "type"})
    if typ == "space":
        return SpaceScene(W, H, **{k: v for k, v in spec.items() if k != "type"})
    if typ == "city":
        return CityScene(W, H, **{k: v for k, v in spec.items() if k != "type"})
    raise ValueError(typ)
