#!/usr/bin/env python3
"""
arch.py — Rotating 3D ASCII globe.
Yellow land blocks, blue-grey ocean dashes, country labels with arrows.

Controls:
  +  /  -    speed up / slow down
  SPACE      pause / resume
  q          quit
  r          reset

note to self: country polygons were traced by eye off a low-res map,
so borders are rough in places (Sudan/S.Sudan never got split out,
Somaliland isn't in here either). fine for ascii art, nobody's
navigating a ship with this.
"""

import sys, os, math, time, tty, termios, select, signal, random
import numpy as np

DEBUG = False   # flip on if the globe looks wrong again, dumps frame timing to stderr

# ─────────────────────────────────────────────────────────────────────────────
# ANSI HELPERS
# ─────────────────────────────────────────────────────────────────────────────
RESET = '\x1b[0m'
BOLD  = '\x1b[1m'
def fg(r, g, b): return f'\x1b[38;2;{r};{g};{b}m'
def bg(r, g, b): return f'\x1b[48;2;{r};{g};{b}m'   # not used anywhere yet, kept around from when I tried a highlight-row idea
def move(r, c):  return f'\x1b[{r+1};{c+1}H'

LAND_BRIGHT  = fg(255, 220,  20)
LAND_MID     = fg(200, 165,  15)
LAND_DIM     = fg(110,  88,   8)
LABEL_WHITE  = fg(255, 255, 255)
ARROW_BLUE   = fg(160, 190, 255)
STATUS_COL   = fg(100, 145, 190)

OCEAN_CH  = ['-', '·', '-', ' ', '·', '-']
LAND_CH   = '█'

# cosmetic signal-noise glitch — like a bad satellite feed cutting out
# for a split second. purely visual, doesn't touch the actual sim state.
GLITCH        = True
GLITCH_CHANCE = 0.02          # rough odds per frame of a glitch starting
GLITCH_CHARS  = ['▓', '▒', '░', '#', '%', '¤']

# ─────────────────────────────────────────────────────────────────────────────
# COUNTRY POLYGON DATA  (lon, lat pairs)
# ─────────────────────────────────────────────────────────────────────────────
COUNTRY_POLYS = [
  # North America
  ("United States",   [(-124,49),(-95,49),(-83,46),(-76,44),(-67,47),(-67,44),
                        (-70,42),(-74,40),(-75,38),(-80,32),(-87,30),(-90,29),
                        (-94,29),(-97,26),(-97,28),(-104,29),(-111,31),(-117,32),
                        (-117,34),(-122,37),(-124,37),(-124,49)]),
  ("Canada",          [(-60,47),(-67,47),(-76,44),(-83,46),(-88,48),(-95,49),
                        (-110,49),(-124,49),(-130,55),(-136,60),(-140,60),(-140,69),
                        (-120,69),(-95,69),(-80,68),(-65,63),(-62,64),(-68,68),
                        (-75,68),(-90,68),(-110,68),(-130,70),(-60,47)]),
  ("Mexico",          [(-117,32),(-111,31),(-104,29),(-97,28),(-97,26),(-94,29),
                        (-90,29),(-87,16),(-90,16),(-92,18),(-96,19),(-104,19),
                        (-109,23),(-110,28),(-114,31),(-117,32)]),
  ("Cuba",            [(-84,20),(-80,20),(-74,22),(-76,24),(-82,22),(-84,20)]),
  # South America
  ("Venezuela",       [(-74,12),(-66,12),(-62,10),(-60,8),(-64,4),(-68,4),(-68,8),(-74,12)]),
  ("Colombia",        [(-78,8),(-74,12),(-68,8),(-68,4),(-76,-1),(-78,2),(-78,8)]),
  ("Brazil",          [(-34,-4),(-36,-6),(-38,-12),(-38,-18),(-40,-20),(-42,-22),
                        (-46,-24),(-48,-26),(-50,-28),(-52,-32),(-53,-34),
                        (-56,-28),(-58,-18),(-58,-8),(-60,-4),(-60,0),(-52,4),
                        (-50,2),(-48,-2),(-44,-4),(-38,-2),(-34,-4)]),
  ("Peru",            [(-80,-2),(-74,0),(-70,-4),(-72,-10),(-70,-14),(-68,-16),(-76,-14),(-80,-8),(-80,-2)]),
  ("Bolivia",         [(-70,-10),(-66,-14),(-60,-16),(-62,-22),(-68,-22),(-70,-18),(-70,-10)]),
  ("Chile",           [(-70,-18),(-68,-20),(-68,-52),(-72,-52),(-72,-18),(-70,-18)]),
  ("Argentina",       [(-68,-22),(-58,-22),(-56,-34),(-62,-38),(-64,-42),(-68,-46),(-68,-52),(-68,-22)]),
  ("Paraguay",        [(-58,-18),(-58,-24),(-62,-24),(-62,-18),(-58,-18)]),
  ("Uruguay",         [(-54,-30),(-58,-30),(-58,-34),(-54,-34),(-52,-32),(-54,-30)]),
  ("Ecuador",         [(-80,-2),(-76,-2),(-76,-6),(-80,-6),(-80,-2)]),
  ("Guyana",          [(-60,4),(-58,4),(-58,8),(-60,8),(-60,4)]),
  # Europe
  ("United Kingdom",  [(-5,50),(-2,51),(0,52),(0,53),(-2,55),(-4,58),(-4,57),(-2,56),(-2,54),(-3,52),(-4,51),(-5,50)]),
  ("France",          [(-5,44),(0,43),(3,43),(5,43),(7,44),(7,48),(5,49),(2,51),(0,51),(0,48),(-2,47),(-4,48),(-5,48),(-5,44)]),
  ("Spain",           [(-9,44),(-4,44),(0,43),(3,43),(3,40),(1,38),(-2,37),(-5,36),(-7,37),(-9,38),(-9,44)]),
  ("Germany",         [(6,51),(8,48),(10,48),(12,48),(14,50),(14,54),(10,55),(8,55),(6,53),(6,51)]),
  ("Italy",           [(7,44),(10,44),(12,46),(14,46),(16,40),(16,38),(14,38),(12,38),(10,44),(7,44)]),
  ("Poland",          [(14,54),(18,54),(22,54),(24,52),(24,50),(18,50),(14,50),(14,54)]),
  ("Ukraine",         [(22,52),(32,52),(36,50),(38,48),(32,46),(24,46),(22,48),(22,52)]),
  ("Sweden",          [(12,56),(18,60),(22,66),(20,68),(14,62),(12,58),(12,56)]),
  ("Norway",          [(5,58),(10,62),(14,68),(18,70),(20,68),(14,66),(8,60),(5,58)]),
  ("Finland",         [(22,60),(28,62),(30,68),(26,70),(22,66),(20,62),(22,60)]),
  ("Romania",         [(22,44),(30,46),(30,48),(24,48),(22,46),(22,44)]),
  ("Netherlands",     [(4,52),(6,52),(6,54),(4,54),(4,52)]),
  ("Greece",          [(20,36),(22,38),(24,40),(22,40),(20,38),(20,36)]),
  ("Portugal",        [(-10,38),(-8,38),(-8,42),(-10,42),(-10,38)]),
  ("Belarus",         [(24,52),(28,54),(26,56),(22,54),(24,52)]),
  # Russia
  ("Russia",          [(28,70),(60,72),(100,74),(130,72),(140,70),(140,50),
                        (132,44),(130,42),(136,46),(140,52),(130,60),(110,54),
                        (100,52),(80,56),(60,54),(50,52),(44,44),(40,42),
                        (36,46),(32,48),(28,52),(24,52),(22,54),(24,58),(28,60),(28,70)]),
  # Middle East
  ("Turkey",          [(26,42),(36,42),(40,40),(44,40),(44,38),(40,36),(32,36),(26,38),(26,42)]),
  ("Iran",            [(44,38),(52,38),(60,36),(62,28),(56,22),(50,26),(46,28),(44,30),(44,38)]),
  ("Saudi Arabia",    [(36,30),(42,24),(50,20),(56,24),(56,28),(46,32),(36,30)]),
  ("Iraq",            [(38,34),(46,36),(48,34),(48,30),(44,32),(38,30),(38,34)]),
  ("Syria",           [(36,34),(42,36),(42,38),(38,38),(36,36),(36,34)]),
  ("Yemen",           [(42,18),(50,16),(54,14),(48,12),(42,16),(42,18)]),
  # Central / South Asia
  ("Kazakhstan",      [(52,46),(60,52),(72,56),(80,52),(80,46),(68,42),(56,44),(52,46)]),
  ("Uzbekistan",      [(56,42),(64,40),(66,38),(60,38),(56,40),(56,42)]),
  ("Afghanistan",     [(62,36),(70,38),(74,36),(70,34),(62,34),(60,34),(62,36)]),
  ("Pakistan",        [(62,24),(68,26),(72,34),(66,38),(62,36),(60,28),(62,24)]),
  ("India",           [(68,36),(76,34),(80,32),(80,16),(78,8),(74,18),(72,20),(68,22),(66,24),(68,36)]),
  ("Nepal",           [(80,28),(88,26),(88,28),(80,30),(80,28)]),
  ("Bangladesh",      [(88,24),(92,22),(92,20),(88,22),(88,24)]),
  ("Sri Lanka",       [(80,10),(82,8),(80,8),(80,10)]),
  # East / SE Asia
  ("China",           [(80,44),(88,48),(100,50),(110,44),(116,40),(122,38),(120,28),
                        (116,22),(104,22),(96,28),(88,28),(80,30),(76,38),(80,44)]),
  ("Mongolia",        [(88,48),(110,48),(116,46),(116,42),(98,42),(88,44),(88,48)]),
  ("Japan",           [(130,30),(134,32),(136,36),(140,40),(140,38),(136,34),(130,30)]),
  ("South Korea",     [(126,34),(130,36),(130,38),(126,38),(126,34)]),
  ("North Korea",     [(124,38),(128,40),(128,42),(124,40),(124,38)]),
  ("Myanmar",         [(92,28),(100,20),(96,16),(92,22),(92,28)]),
  ("Thailand",        [(100,20),(104,16),(100,6),(98,8),(100,12),(100,20)]),
  ("Vietnam",         [(104,22),(108,18),(108,10),(104,14),(102,16),(104,22)]),
  ("Cambodia",        [(102,10),(106,10),(106,14),(102,14),(102,10)]),
  ("Malaysia",        [(100,2),(108,2),(108,6),(104,6),(100,4),(100,2)]),
  ("Indonesia",       [(96,4),(104,0),(112,-8),(116,-8),(120,-10),(120,-4),(108,-6),(104,-2),(100,2),(96,4)]),
  ("Philippines",     [(118,8),(122,14),(122,18),(118,14),(118,8)]),
  ("Taiwan",          [(120,22),(122,24),(122,26),(120,24),(120,22)]),
  # Africa
  ("Morocco",         [(-6,36),(0,34),(0,30),(-4,28),(-14,28),(-14,30),(-6,34),(-6,36)]),
  ("Algeria",         [(0,18),(12,24),(12,30),(6,36),(0,36),(-2,30),(-2,22),(0,18)]),
  ("Libya",           [(10,22),(20,24),(24,24),(24,30),(14,32),(10,30),(10,22)]),
  ("Egypt",           [(24,22),(34,28),(36,30),(32,32),(24,30),(24,22)]),
  ("Sudan",           [(24,22),(36,22),(38,16),(32,12),(24,12),(24,22)]),
  ("Ethiopia",        [(36,16),(42,12),(44,8),(40,4),(36,8),(34,12),(36,16)]),
  ("Kenya",           [(36,4),(42,2),(40,-4),(34,-2),(34,4),(36,4)]),
  ("Tanzania",        [(30,-2),(40,-6),(36,-12),(30,-10),(30,-2)]),
  ("Nigeria",         [(4,4),(4,8),(2,10),(4,12),(12,14),(14,12),(14,8),(10,4),(4,4)]),
  ("Dem. Rep. Congo", [(18,-6),(24,-4),(30,-8),(28,-14),(20,-12),(16,-8),(18,-6)]),
  ("South Africa",    [(16,-28),(26,-22),(32,-26),(32,-30),(26,-34),(18,-32),(16,-28)]),
  ("Madagascar",      [(44,-14),(50,-20),(50,-24),(44,-22),(44,-14)]),
  ("Angola",          [(12,-6),(20,-4),(24,-8),(20,-14),(12,-8),(12,-6)]),
  ("Mozambique",      [(32,-14),(36,-18),(34,-26),(30,-22),(30,-14),(32,-14)]),
  ("Zambia",          [(22,-8),(30,-10),(30,-14),(22,-14),(22,-8)]),
  ("Somalia",         [(44,12),(50,10),(50,4),(44,2),(42,8),(44,12)]),
  ("Ghana",           [(-4,4),(0,4),(0,8),(-4,10),(-4,4)]),
  ("Cameroon",        [(8,4),(14,6),(14,8),(10,12),(8,10),(8,4)]),
  ("Mali",            [(-4,14),(4,14),(4,18),(0,22),(-4,22),(-4,14)]),
  ("Niger",           [(4,14),(14,14),(14,12),(8,12),(4,12),(4,14)]),
  ("Chad",            [(14,12),(22,12),(24,14),(22,18),(14,16),(14,12)]),
  ("Zimbabwe",        [(26,-14),(32,-18),(28,-22),(24,-16),(26,-14)]),
  ("Namibia",         [(12,-18),(20,-20),(20,-28),(12,-28),(12,-18)]),
  ("Botswana",        [(20,-18),(26,-22),(26,-26),(20,-26),(20,-18)]),
  # Oceania
  ("Australia",       [(114,-22),(122,-18),(130,-14),(138,-16),(142,-10),
                        (150,-22),(152,-30),(146,-38),(138,-36),(130,-32),
                        (118,-30),(114,-26),(114,-22)]),
  ("New Zealand",     [(166,-46),(172,-42),(172,-38),(168,-36),(166,-42),(166,-46)]),
  ("Papua New Guinea",[(142,-8),(150,-6),(150,-2),(142,-6),(142,-8)]),
]

# Label anchor points — (name, lon, lat)
LABELS = [
    ("United States",   -98,  38), ("Canada",          -96,  56),
    ("Mexico",         -102,  24), ("Cuba",             -80,  22),
    ("Venezuela",       -66,   8), ("Colombia",         -74,   4),
    ("Brazil",          -52, -10), ("Peru",             -75, -10),
    ("Bolivia",         -64, -16), ("Chile",            -70, -30),
    ("Argentina",       -64, -36), ("Paraguay",         -58, -22),
    ("Uruguay",         -56, -32), ("Ecuador",          -78,  -2),
    ("United Kingdom",   -2,  54), ("France",             2,  46),
    ("Spain",            -4,  40), ("Germany",           10,  51),
    ("Italy",            12,  43), ("Poland",            19,  52),
    ("Ukraine",          32,  49), ("Sweden",            16,  62),
    ("Norway",           12,  64), ("Finland",           26,  64),
    ("Romania",          25,  46), ("Netherlands",        5,  53),
    ("Greece",           22,  38), ("Portugal",           -8,  40),
    ("Russia",           60,  60), ("Turkey",            35,  39),
    ("Iran",             53,  33), ("Saudi Arabia",      45,  24),
    ("Iraq",             44,  33), ("Syria",             38,  36),
    ("Yemen",            48,  16), ("Kazakhstan",        68,  48),
    ("Afghanistan",      66,  34), ("Pakistan",          68,  30),
    ("India",            78,  22), ("China",            105,  36),
    ("Mongolia",        104,  46), ("Myanmar",           96,  20),
    ("Thailand",        100,  14), ("Vietnam",          106,  16),
    ("Indonesia",       108,  -4), ("Malaysia",         110,   4),
    ("Philippines",     122,  13), ("Japan",            138,  36),
    ("South Korea",     128,  36), ("North Korea",      126,  40),
    ("Bangladesh",       90,  24), ("Nepal",             84,  28),
    ("Morocco",          -4,  32), ("Algeria",            3,  28),
    ("Libya",            17,  26), ("Egypt",             30,  26),
    ("Sudan",            30,  16), ("Ethiopia",          40,  10),
    ("Kenya",            38,   1), ("Tanzania",          35,  -6),
    ("Nigeria",           8,   8), ("Dem. Rep. Congo",  24,  -4),
    ("South Africa",     25, -30), ("Madagascar",        47, -18),
    ("Angola",           18,  -8), ("Mozambique",        34, -18),
    ("Zambia",           26, -12), ("Somalia",           46,   6),
    ("Ghana",            -1,   7), ("Cameroon",          12,   6),
    ("Mali",              0,  18), ("Niger",              9,  16),
    ("Chad",             18,  14), ("Zimbabwe",          29, -18),
    ("Australia",       134, -28), ("New Zealand",      172, -42),
    ("Papua New Guinea",145,  -6),
]

# ─────────────────────────────────────────────────────────────────────────────
# LAND MASK  (720 × 360 boolean grid)
# ─────────────────────────────────────────────────────────────────────────────
MASK_W, MASK_H = 720, 360

def _pip(px, py, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > py) != (yj > py)) and px < (xj-xi)*(py-yi)/(yj-yi+1e-12)+xi:
            inside = not inside
        j = i
    return inside

def build_land_mask():
    # yeah this is O(polygons * bbox_area), it's a one-time startup cost so
    # I never bothered vectorizing it. ~720x360 grid, takes well under a sec.
    grid = np.zeros((MASK_H, MASK_W), dtype=np.uint8)
    for _, poly in COUNTRY_POLYS:
        if len(poly) < 3:
            continue
        lons = [p[0] for p in poly]; lats = [p[1] for p in poly]
        c0 = max(0, int((min(lons)+180)/360*MASK_W)-2)
        c1 = min(MASK_W-1, int((max(lons)+180)/360*MASK_W)+2)
        r0 = max(0, int((90-max(lats))/180*MASK_H)-2)
        r1 = min(MASK_H-1, int((90-min(lats))/180*MASK_H)+2)
        for r in range(r0, r1+1):
            lat = 90 - r/MASK_H*180
            for c in range(c0, c1+1):
                lon = c/MASK_W*360 - 180
                if grid[r,c] == 0 and _pip(lon, lat, poly):
                    grid[r,c] = 1
    return grid

# ─────────────────────────────────────────────────────────────────────────────
# SPHERE GEOMETRY
# ─────────────────────────────────────────────────────────────────────────────

def make_sphere(W, H):
    """Return camera-space hit points (H,W,3), bool mask, r² array."""
    ASP = 2.15          # terminal char aspect correction — eyeballed against my
                        # terminal's font metrics, adjust if your globe looks squashed
    xs  = (np.arange(W, dtype=np.float32) - W/2 + 0.5) / (W/2)
    ys  = ((np.arange(H, dtype=np.float32) - H/2 + 0.5) / (H/2)) * ASP
    xg, yg = np.meshgrid(xs, ys)
    r2   = xg**2 + yg**2
    hit  = r2 <= 1.0
    zg   = np.where(hit, np.sqrt(np.clip(1-r2, 0, 1)), 0.0)
    pts  = np.stack([xg, yg, zg], axis=-1)
    return pts, hit, r2

def rot_y(a):
    c,s = math.cos(a), math.sin(a)
    return np.array([[c,0,s],[0,1,0],[-s,0,c]], dtype=np.float32)

def rot_x(a):
    c,s = math.cos(a), math.sin(a)
    return np.array([[1,0,0],[0,c,-s],[0,s,c]], dtype=np.float32)

def world_pts(pts_cam, Ry, Rx):
    R = Rx @ Ry
    return np.einsum('kl,ijl->ijk', R, pts_cam), R

def sample_land(pts_world, land_mask):
    y = pts_world[...,1]
    x = pts_world[...,0]
    z = pts_world[...,2]
    lat = np.degrees(np.arcsin(np.clip(y, -1, 1)))
    lon = np.degrees(np.arctan2(x, z))
    r = np.clip(((90 - lat)/180*MASK_H).astype(int), 0, MASK_H-1)
    c = np.clip(((lon+180)/360*MASK_W).astype(int), 0, MASK_W-1)
    return land_mask[r, c].astype(bool)

def lighting(pts_world, sun):
    return np.einsum('ijk,k->ij', pts_world, sun)

# ─────────────────────────────────────────────────────────────────────────────
# RENDER ONE FRAME
# ─────────────────────────────────────────────────────────────────────────────

def render_frame(W, H, pts_cam, hit, r2, R, sun, land_mask, frame_no, speed, paused):
    # World space
    Pw = np.einsum('kl,ijl->ijk', R, pts_cam)

    # Per-pixel data
    bright  = lighting(Pw, sun)          # (H,W)  -1..1
    is_land = sample_land(Pw, land_mask) # (H,W)  bool

    # Ocean char cycle (slow shimmer)
    oc_off = (frame_no // 5) % len(OCEAN_CH)

    # decide if this frame gets a static burst, and where. kept separate from
    # the per-pixel loop below so it can't corrupt the ANSI escape sequences
    # (learned that the hard way — splicing into the joined string mid-escape
    # code just spams garbage bytes at the terminal)
    glitch_cells = set()
    if GLITCH and random.random() < GLITCH_CHANCE:
        n_cells = random.randint(8, 24)
        for _ in range(n_cells):
            glitch_cells.add((random.randint(0, H - 1), random.randint(0, W - 1)))

    # Build output: list of row strings + label escape sequences
    rows = []
    for r in range(H):
        buf   = []
        prev  = None
        for c in range(W):
            if (r, c) in glitch_cells:
                col = fg(random.randint(150, 255), random.randint(150, 255), random.randint(150, 255))
                ch  = random.choice(GLITCH_CHARS)
                buf.append(col + ch)
                prev = None   # force next cell to re-emit its own color code
                continue
            if not hit[r, c]:
                col = '\x1b[0m'; ch = ' '
            else:
                b    = float(bright[r, c])
                land = bool(is_land[r, c])
                if land:
                    if   b >  0.30: col = LAND_BRIGHT
                    elif b >  0.00: col = LAND_MID
                    else:           col = LAND_DIM
                    ch = LAND_CH
                else:
                    idx = (c + oc_off) % len(OCEAN_CH)
                    ch  = OCEAN_CH[idx]
                    if   b >  0.15:
                        rv,gv,bv = 65+int(b*45), 95+int(b*55), 140+int(b*55)
                    elif b > -0.10:
                        rv,gv,bv = 38, 62, 108
                    else:
                        rv,gv,bv = 18, 32, 62
                    col = fg(rv,gv,bv)

            if col != prev:
                buf.append(col + ch)
                prev = col
            else:
                buf.append(ch)

        buf.append(RESET)
        rows.append(''.join(buf))

    # ── Country labels ───────────────────────────────────────────────────────
    # Collect (screen_row, globe_col, name) for visible labels
    label_data = []   # (screen_row, land_col, name)
    for name, lon0, lat0 in LABELS:
        phi   = math.radians(90 - lat0)
        theta = math.radians(lon0 + 180)
        wx =  -math.sin(phi)*math.cos(theta)
        wy =   math.cos(phi)
        wz =   math.sin(phi)*math.sin(theta)
        # Rotate to camera space
        cam = R.T @ np.array([wx, wy, wz], dtype=np.float32)
        if cam[2] < 0.08:          # behind globe
            continue
        # Project
        ASP = 2.15
        sx = cam[0] / ASP
        sy = -cam[1]
        pcol = int((sx + 1) * 0.5 * W)
        prow = int((sy + 1) * 0.5 * H)
        if not (0 <= prow < H and 0 <= pcol < W):
            continue
        if not hit[prow, pcol]:    # off sphere surface
            continue
        label_data.append((prow, pcol, name))

    # Deduplicate rows (keep the one with highest pcol per row)
    row_best = {}
    for prow, pcol, name in label_data:
        if prow not in row_best or pcol > row_best[prow][0]:
            row_best[prow] = (pcol, name)

    # Build label escape sequences (drawn after HOME so they overlay)
    label_escapes = []
    for prow, (pcol, name) in row_best.items():
        # Dot line from pcol+2 to label text
        text      = f'← {name}'
        text_col  = W - len(text) - 1
        dot_start = pcol + 2
        dot_count = max(0, text_col - dot_start - 1)
        seq = (
            move(prow, dot_start)
            + ARROW_BLUE + ('·' * dot_count) + ' '
            + LABEL_WHITE + BOLD + text + RESET
        )
        label_escapes.append(seq)

    # ── Status bar ───────────────────────────────────────────────────────────
    state = 'paused' if paused else f'spinning {speed:.1f}x'
    status = STATUS_COL + '  ' + state + RESET

    return rows, label_escapes, status

# ─────────────────────────────────────────────────────────────────────────────
# TERMINAL I/O
# ─────────────────────────────────────────────────────────────────────────────
HIDE    = '\x1b[?25l'
SHOW    = '\x1b[?25h'
HOME    = '\x1b[H'
CLEAR   = '\x1b[2J'
ALT_ON  = '\x1b[?1049h'
ALT_OFF = '\x1b[?1049l'

def term_size():
    try:    return os.get_terminal_size()
    except: return os.terminal_size((80, 24))

def read_key():
    if select.select([sys.stdin], [], [], 0)[0]:
        ch = sys.stdin.read(1)
        if ch == '\x1b' and select.select([sys.stdin], [], [], 0.02)[0]:
            ch += sys.stdin.read(8)
        # print(repr(ch), file=sys.stderr)  # uncomment when debugging arrow-key / escape sequence weirdness
        return ch
    return None

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    out = sys.stdout
    write = out.write
    flush = out.flush

    write('  Building land mask... ')
    flush()
    land_mask = build_land_mask()
    write('\r  Land mask ready.         \n')
    time.sleep(0.3)

    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)

    rot_y_ang = 0.0
    tilt      = 0.15        # slight X tilt (matches video)
    speed     = 1.0
    paused    = False
    frame_no  = 0

    # Sun: from right+slightly front and above (matches video — left side lit)
    sun = np.array([0.65, 0.25, 0.72], dtype=np.float32)
    sun /= np.linalg.norm(sun)

    last_W = last_H = 0
    pts_cam = hit = r2 = None

    TARGET_FPS = 24
    frame_dt   = 1.0 / TARGET_FPS

    _resize = False
    def on_resize(*_): nonlocal _resize; _resize = True
    signal.signal(signal.SIGWINCH, on_resize)
    # heads up: SIGWINCH doesn't reliably fire through some ssh clients / tmux
    # configs, so resizing might lag a frame or two there. not chasing that one.

    try:
        tty.setraw(fd)
        write(ALT_ON + HIDE + CLEAR)
        flush()

        while True:
            t0 = time.perf_counter()

            # Input
            key = read_key()
            if key:
                k = key.strip().lower()
                if k in ('q', '\x03', '\x04'):
                    break
                elif key == ' ':
                    paused = not paused
                elif key in ('+', '='):
                    speed = min(speed + 0.25, 5.0)
                elif key in ('-', '_'):
                    speed = max(speed - 0.25, 0.25)
                elif k == 'r':
                    rot_y_ang = 0.0; speed = 1.0; paused = False

            # Physics
            dt = frame_dt
            if not paused:
                rot_y_ang += speed * dt * 0.42

            # Geometry
            cols, rows = term_size()
            # Globe fits in terminal — square-ish
            GW = min(cols, int(rows * 2.15))
            GH = rows - 1
            GW = min(GW, cols)

            if _resize or GW != last_W or GH != last_H:
                pts_cam, hit, r2 = make_sphere(GW, GH)
                last_W, last_H = GW, GH
                _resize = False
                write(CLEAR)

            Ry = rot_y(rot_y_ang)
            Rx = rot_x(tilt)
            R  = Rx @ Ry

            frame_rows, label_seqs, status = render_frame(
                GW, GH, pts_cam, hit, r2, R, sun,
                land_mask, frame_no, speed, paused
            )

            # Write all at once
            lpad = ' ' * max(0, (cols - GW) // 2)
            buf  = [HOME]
            for row_str in frame_rows:
                buf.append(lpad + row_str + '\r\n')
            # Labels overlay (absolute positioning)
            buf.extend(label_seqs)
            # Status last line
            buf.append(f'\x1b[{rows};1H' + status)
            write(''.join(buf))
            flush()

            frame_no += 1

            if DEBUG and frame_no % 100 == 0:
                print(f'[dbg] frame {frame_no}  size={GW}x{GH}  speed={speed:.2f}', file=sys.stderr)

            # Cap FPS
            elapsed = time.perf_counter() - t0
            wait    = frame_dt - elapsed
            if wait > 0:
                time.sleep(wait)

    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        write(SHOW + ALT_OFF + RESET + '\n')
        flush()
        print('  Goodbye.\n')

if __name__ == '__main__':
    main()
