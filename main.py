#!/usr/bin/env python3
"""Procedurally render a glazed sprinkles donut on a plate, top-down.

Pure standard library (zlib + struct for the PNG container, math for the
shading model). The scene is a shaded 3D torus rendered analytically per
pixel: lambert diffuse, Blinn-Phong specular on the glaze, an angular drip
field that hangs glaze over the walls, dough showing on the far and inner
walls, capsule sprinkles placed around the tube, a ceramic plate, a wooden
table with vignette and film grain. Output: /output/entry.png (or
$MAKEFUN_OUTPUT_DIR), 1024x1024, deterministic.
"""
import math
import os
import struct
import zlib

W = H = 1024

# ---- scene geometry -------------------------------------------------------
R_MAJOR = 0.40          # torus ring radius
R_MINOR = 0.19          # tube radius
PLATE_R = 0.72          # ceramic plate radius
PLATE_Y = -0.06         # plate centre offset

# ---- lighting -------------------------------------------------------------
LX, LY, LZ = -0.30, 0.45, 0.88       # key light, upper-left
FX, FY, FZ = 0.55, -0.25, 0.35       # warm fill, lower-right
_ln = math.sqrt(LX * LX + LY * LY + LZ * LZ)
LX, LY, LZ = LX / _ln, LY / _ln, LZ / _ln

# ---- palette --------------------------------------------------------------
DOUGH_LO = (198, 128, 62)
DOUGH_HI = (240, 186, 118)
GLAZE_A = (244, 150, 186)
GLAZE_B = (255, 214, 228)
SPRINKLE_COLORS = [
    (220, 50, 45), (40, 120, 220), (250, 200, 30), (40, 180, 90),
    (150, 80, 190), (255, 255, 255), (255, 150, 30),
]

# ---- deterministic sprinkles ---------------------------------------------
# A small xorshift-style PRNG keeps the placement fixed across runs.
_state = 0x2545F4914F6CDD1D


def _rand():
    global _state
    _state ^= (_state << 13) & 0xFFFFFFFFFFFFFFFF
    _state ^= _state >> 7
    _state ^= (_state << 17) & 0xFFFFFFFFFFFFFFFF
    return (_state >> 11) / float(1 << 53)


SPRINKLES = []
while len(SPRINKLES) < 520:
    v = _rand() * 2 * math.pi            # angle around the ring
    # triangular distribution keeps sprinkles clustered on the glazed top
    u = (_rand() + _rand() - 1.0) * 1.30
    c = SPRINKLE_COLORS[int(_rand() * len(SPRINKLE_COLORS))]
    SPRINKLES.append((u, v, c))


def _drips(ang):
    """Angular glaze-drip field: lobes that hang over the walls."""
    h = 0.0
    for ph, wv, amp in ((0.4, 3.0, 0.55), (1.8, 5.0, 0.4),
                        (3.6, 2.3, 0.5), (5.1, 4.0, 0.35)):
        h += amp * math.exp(-((math.cos(ang - ph)) ** 2) * wv)
    return h


def shade(px, py):
    """Colour of one pixel. The scene spans [-1, 1] on both axes."""
    x = (px + 0.5) * (2.0 / W) - 1.0
    y = 1.0 - (py + 0.5) * (2.0 / H)
    dx, dy = x, y
    rr = math.hypot(dx, dy) or 1e-9
    urx, ury = dx / rr, dy / rr
    a = rr - R_MAJOR

    if abs(a) >= R_MINOR:
        # --- plate or table -------------------------------------------------
        pr = math.hypot(x, y - PLATE_Y)
        if pr < PLATE_R:
            # ceramic plate with rim shading and a contact shadow
            rim = max(0.0, 1.0 - (PLATE_R - pr) / 0.10)
            inner_sh = max(0.0, 1.0 - abs(pr - (R_MAJOR + R_MINOR + 0.04)) / 0.10) * 0.12
            v = 1.0 - rim * 0.10 - inner_sh
            v *= 0.94 + 0.06 * max(0.0, x * 0.5 + y * 0.8 + 0.5)
            d_out = pr - (R_MAJOR + R_MINOR)
            if d_out > 0:
                v -= max(0.0, 1.0 - d_out / 0.16) ** 2 * 0.38
            c = int(246 * v)
            return (c, int(243 * v), int(238 * v))
        # wooden table with a soft vignette
        vig = max(0.0, 1.0 - math.hypot(x * 0.85, y * 0.85) / 1.15)
        f = 0.35 + 0.65 * vig
        wood_r = (150 + 28 * math.sin(x * 18.0 + y * 1.1)
                  + 14 * math.sin(x * 40.0 - y * 2.3)) * f
        wood_g = (104 + 16 * math.sin(x * 18.0 + y * 1.1)) * f
        wood_b = (62 + 10 * math.sin(x * 18.0 + y * 1.1)) * f
        # drop shadow under the donut
        d_out = rr - (R_MAJOR + R_MINOR)
        if 0 < d_out < 0.13 and pr >= PLATE_R:
            sh = max(0.0, 1.0 - d_out / 0.13) ** 2 * 0.55
            wood_r *= 1 - sh
            wood_g *= 1 - sh
            wood_b *= 1 - sh
        return (int(wood_r), int(wood_g), int(wood_b))

    # --- torus surface -------------------------------------------------------
    z = math.sqrt(max(0.0, R_MINOR * R_MINOR - a * a))
    n_x, n_y, n_z = urx * a / R_MINOR, ury * a / R_MINOR, z / R_MINOR
    diff = max(0.0, n_x * LX + n_y * LY + n_z * LZ)
    fill = max(0.0, n_x * FX + n_y * FY + n_z * FZ)
    hx, hy, hz = LX, LY, LZ + 1.0
    hl = math.sqrt(hx * hx + hy * hy + hz * hz)
    spec = max(0.0, (n_x * hx + n_y * hy + n_z * hz) / hl) ** 140

    ang = math.atan2(ury, urx)
    d = _drips(ang)
    wall = 1.0 - n_z
    coat = max(0.0, n_z * 1.35)
    if n_y < -0.25:                       # far wall shows more dough
        coat *= max(0.0, 1.0 - (-n_y - 0.25) * 1.2)
    if a < 0:                             # inner wall: golden dough peeks out
        coat *= 0.85
    drip_len = 0.35 + 0.65 * d
    hang = max(0.0, (drip_len - wall) * 1.5) if wall > 0 else 0.0
    glaze = min(1.0, max(coat, hang)) if n_z > -0.35 else 0.0

    if glaze > 0.3:
        t = min(1.0, max(0.0, n_z))
        base = [GLAZE_A[i] + (GLAZE_B[i] - GLAZE_A[i]) * t for i in range(3)]
        base = [min(255, b * (0.45 + 0.7 * diff) * (1.0 + 0.25 * fill))
                for b in base]
        if n_z < 0.3 and glaze > 0.9:     # hanging drip ends: thicker tone
            base = [b * 0.92 for b in base]
        if spec > 0:
            base = [min(255, b + spec * 240) for b in base]
    else:
        t = diff
        base = [DOUGH_LO[i] + (DOUGH_HI[i] - DOUGH_LO[i]) * t for i in range(3)]
        base = [min(255, b * (0.4 + 0.75 * diff) * (1.0 + 0.25 * fill))
                for b in base]

    # sprinkles: elongated capsules laid around the tube on glazed areas
    if glaze > 0.7 and n_z > 0.05:
        u = math.atan2(z, a)
        for (su, sv, c) in SPRINKLES:
            du = abs(u - su)
            dv = abs(((ang - sv + math.pi) % (2 * math.pi)) - math.pi)
            if du < 0.085 and dv < 0.05:
                f2 = 0.8 + 0.3 * diff
                return (min(255, int(c[0] * f2)),
                        min(255, int(c[1] * f2)),
                        min(255, int(c[2] * f2)))

    r, g, b = base
    # film grain: deterministic hash noise breaks the CG smoothness
    n = ((px * 73856093) ^ (py * 19349663)) & 0xFFFF
    gn = (n / 32768.0 - 1.0) * 5.0
    return (min(255, max(0, int(r + gn))),
            min(255, max(0, int(g + gn))),
            min(255, max(0, int(b + gn))))


def render_rows():
    rows = []
    for py in range(H):
        row = bytearray()
        for px in range(W):
            r, g, b = shade(px, py)
            row += bytes((r, g, b))
        rows.append(bytes(row))
    return rows


def write_png(path, rows):
    raw = b''.join(b'\x00' + r for r in rows)

    def chunk(typ, data):
        return (struct.pack('>I', len(data)) + typ + data
                + struct.pack('>I', zlib.crc32(typ + data) & 0xFFFFFFFF))

    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 9))
    png += chunk(b'IEND', b'')
    with open(path, 'wb') as fh:
        fh.write(png)


def main():
    out_dir = os.environ.get('MAKEFUN_OUTPUT_DIR') or '/output'
    os.makedirs(out_dir, exist_ok=True)
    rows = render_rows()
    write_png(os.path.join(out_dir, 'entry.png'), rows)


if __name__ == '__main__':
    main()
