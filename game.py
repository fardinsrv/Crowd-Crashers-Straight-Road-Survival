from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from OpenGL.GLUT import GLUT_BITMAP_HELVETICA_18
import math
WINDOW_W, WINDOW_H = (1000, 800)
fovY = 120
camera_pos = (0.0, 200.0, 160.0)
camera_target = (0.0, 260.0, 40.0)
CAM_BACK = 70.0
CAM_HEIGHT = 40.0
CAM_AHEAD = 170.0
CAM_SMOOTH = 12.0
GROUND_Z = 0
GRID_LENGTH = 600
ROAD_HALF = 140
VIEW_NEAR = -60
VIEW_FAR = 1400
LANE_MARGIN = 12
SEG_LEN = 400
CAR_HALF_LEN = 22
CAR_HALF_WID = 14
CAR_HALF_HGT = 10
CAR_Z = 12
PLAYER_COLOR = (0.2, 0.9, 0.3)
NPC_COLORS = [(0.95, 0.2, 0.2), (0.2, 0.6, 0.95), (0.95, 0.85, 0.2), (0.8, 0.4, 0.8), (0.4, 0.8, 0.4), (0.8, 0.8, 0.4)]
MAX_HEALTH = 100
MAX_SPEED = 250
PLAYER_MAX_SPEED = 200
ACCEL_RATE = 300
BRAKE_RATE = 220
LATERAL_RATE = 400
FRICTION = 0.985
SPAWN_INTERVAL_DECAY = 0.01
HAZARD_MIN_GAP = 320
BASE_SPAWN_INTERVAL = 11.0
MIN_SPAWN_INTERVAL = 8.0
MAX_HAZARDS = 4
MAX_PROJECTILES = 8
THROW_INTERVAL = 3.0
MAX_THROWS_PER_TICK = 1
BROKEN_DAMAGE_PER_SEC = 3
OIL_LATERAL_DRIFT = 16
WRECK_HIT_DAMAGE = 18
CAR_HIT_DAMAGE_RATE = 26.0
BUMP_TAP_DAMAGE = 6.0
OFFROAD_DAMAGE_PER_SEC = 12
GRAVITY = -380.0
CROWD_STEP = 28
CROWD_LINES = 3
CROWD_LINE_OFFSET = 12
CROWD_ANIM_DECAY = 0.02
CROWD_BOB_AMP = 4.0
CROWD_BOB_SPEED = 3.0
CROWD_SWAY_AMP = 6.0
CROWD_WAVE_SPEED = 0.12
CROWD_FLAG_RATE = 0.35
CROWD_SHIRT_COLORS = [(0.9, 0.3, 0.3), (0.3, 0.6, 0.95), (0.95, 0.85, 0.2), (0.8, 0.4, 0.8), (0.4, 0.85, 0.45), (0.85, 0.75, 0.4)]

def crowd_rand(side, line, y_pos):
    seed = int(side * 97 + line * 131 + y_pos * 17) & 4294967295
    seed = (seed ^ 2654435769) & 4294967295
    seed = seed * 1664525 + 1013904223 & 4294967295
    return seed / 4294967296.0
MAX_SLOW_CARS = 4
SLOW_DESPAWN_MARGIN = 150
SLOW_CAR_INTERVAL = 9.0
_rand_state = 305441741

def lcg_randf():
    global _rand_state
    _rand_state = 1664525 * _rand_state + 1013904223 & 4294967295
    return _rand_state / 4294967296.0

class Car:
    __slots__ = ('is_player', 'color', 'pos_x', 'pos_y', 'vx', 'speed', 'health', 'alive', 'ai_type', 'name', 'spin_timer', 'blur_timer')

    def __init__(self, is_player, color, x, y, speed, ai_type=None, name=''):
        self.is_player = is_player
        self.color = color
        self.pos_x = x
        self.pos_y = y
        self.vx = 0.0
        self.speed = speed
        self.health = MAX_HEALTH
        self.alive = True
        self.ai_type = ai_type
        self.name = name
        self.spin_timer = 0.0
        self.blur_timer = 0.0

    def aabb(self):
        x = self.pos_x
        y = self.pos_y
        z = CAR_Z
        w, h = (CAR_HALF_WID * 2, CAR_HALF_LEN * 2)
        return (x - w * 0.5, y - h * 0.5, z - CAR_HALF_HGT, w, h, CAR_HALF_HGT * 2)

class Hazard:
    __slots__ = ('kind', 'x', 'y', 'half_w', 'half_l', 'z')

    def __init__(self, kind, x, y, width, length):
        self.kind = kind
        self.x = x
        self.y = y
        self.half_w = width * 0.5
        self.half_l = length * 0.5
        self.z = 2

    def aabb(self):
        return (self.x - self.half_w, self.y - self.half_l, 0, self.half_w * 2, self.half_l * 2, self.z)

class Projectile:
    __slots__ = ('kind', 'x', 'y', 'z', 'vx', 'vy', 'vz', 'r', 'alive')

    def __init__(self, kind, x, y, z, vx, vy, vz, r=6):
        self.kind = kind
        self.x, self.y, self.z = (x, y, z)
        self.vx, self.vy, self.vz = (vx, vy, vz)
        self.r = r
        self.alive = True
throw_anims = []
cars = []
hazards = []
projectiles = []
spawn_interval = BASE_SPAWN_INTERVAL
spawn_accum = 0.0
throw_accum = 0.0
slow_car_accum = 0.0
last_time_sec = 0.0
running = True
score = 0.0
has_won = False
last_hazard_y = -1000000000.0
keys_down = set()

def clamp(x, a, b):
    return a if x < a else b if x > b else x

def apply_damage(c, amount):
    if not c.alive or amount <= 0:
        return
    c.health -= amount
    if c.health <= 0:
        c.health = 0
        c.alive = False

def aabb_overlap(a, b):
    ax, ay, az, aw, ah, ad = a
    bx, by, bz, bw, bh, bd = b
    return ax < bx + bw and ax + aw > bx and (ay < by + bh) and (ay + ah > by) and (az < bz + bd) and (az + ad > bz)

def sphere_aabb_intersect(center, radius, aabb):
    cx, cy, cz = center
    ax, ay, az, aw, ah, ad = aabb
    px = clamp(cx, ax, ax + aw)
    py = clamp(cy, ay, ay + ah)
    pz = clamp(cz, az, az + ad)
    dx = cx - px
    dy = cy - py
    dz = cz - pz
    return dx * dx + dy * dy + dz * dz <= radius * radius

def _aabb_center_size(a):
    ax, ay, az, aw, ah, ad = a
    return (ax + aw * 0.5, ay + ah * 0.5, aw, ah)

def separate_car_from_box(c, box):
    a = c.aabb()
    b = box
    acx, acy, aw, ah = _aabb_center_size(a)
    bcx, bcy, bw, bh = _aabb_center_size(b)
    dx = acx - bcx
    dy = acy - bcy
    overlap_x = aw * 0.5 + bw * 0.5 - abs(dx)
    overlap_y = ah * 0.5 + bh * 0.5 - abs(dy)
    if overlap_x <= 0 or overlap_y <= 0:
        return False
    if overlap_x < overlap_y:
        push_x = overlap_x if dx >= 0 else -overlap_x
        c.pos_x += push_x
        c.vx *= -0.4
    else:
        push_y = overlap_y if dy >= 0 else -overlap_y
        c.pos_y += push_y
        c.speed *= 0.8
    return True

def separate_cars(a, b):
    A = a.aabb()
    B = b.aabb()
    acx, acy, aw, ah = _aabb_center_size(A)
    bcx, bcy, bw, bh = _aabb_center_size(B)
    dx = acx - bcx
    dy = acy - bcy
    overlap_x = aw * 0.5 + bw * 0.5 - abs(dx)
    overlap_y = ah * 0.5 + bh * 0.5 - abs(dy)
    if overlap_x <= 0 or overlap_y <= 0:
        return False
    if overlap_x < overlap_y:
        push = overlap_x * (1 if dx >= 0 else -1)
        a.pos_x += push * 0.5
        b.pos_x -= push * 0.5
        a.vx *= -0.4
        b.vx *= -0.4
    else:
        push = overlap_y * (1 if dy >= 0 else -1)
        a.pos_y += push * 0.5
        b.pos_y -= push * 0.5
        a.speed *= 0.85
        b.speed *= 0.85
    return True

def spawn_slow_car(player):
    slow_count = sum((1 for c in cars if not c.is_player and c.ai_type == 'slow' and c.alive))
    if slow_count >= MAX_SLOW_CARS:
        return
    x = (lcg_randf() * 2 - 1) * (ROAD_HALF - LANE_MARGIN - 20)
    y = player.pos_y + 300 + lcg_randf() * 800
    spd = 40 + lcg_randf() * 40
    c = Car(False, (0.6, 0.6, 0.6), x, y, spd, ai_type='slow', name='SlowCar')
    cars.append(c)

def spawn_hazard_random(player):
    global last_hazard_y
    if len(hazards) >= MAX_HAZARDS:
        return
    r = lcg_randf()
    if r < 0.4:
        kind = 'broken'
        width, length = (60, 80)
    elif r < 0.7:
        kind = 'oil'
        width, length = (66, 70)
    else:
        kind = 'wreck'
        width, length = (70, 90)
    x = (lcg_randf() * 2 - 1) * (ROAD_HALF - LANE_MARGIN - 8)
    y = player.pos_y + 220 + lcg_randf() * 900
    if y - last_hazard_y < HAZARD_MIN_GAP:
        y = last_hazard_y + HAZARD_MIN_GAP
    hazards.append(Hazard(kind, x, y, width, length))
    last_hazard_y = y

def spawn_projectile_towards(car):
    player = next((c for c in cars if c.is_player), None)
    if not player:
        return
    side = -1 if lcg_randf() < 0.5 else 1
    stand_x = ROAD_HALF + 30
    x0 = side * stand_x
    z0 = 60 + lcg_randf() * 20
    if car.pos_y < player.pos_y:
        t_flight = 1.0 + lcg_randf() * 0.5
        y0 = car.pos_y - 200 - lcg_randf() * 900
    else:
        t_flight = 2.0 + lcg_randf() * 1.0
        y0 = car.pos_y + 200 + lcg_randf() * 900
    target_x = car.pos_x + car.vx * 0.4 + (lcg_randf() - 0.5) * 40
    target_y = car.pos_y + max(80.0, car.speed * t_flight)
    vx = (target_x - x0) / t_flight
    vy = (target_y - y0) / t_flight
    vz = (CAR_Z - z0) / t_flight - 0.5 * GRAVITY * t_flight
    r = lcg_randf()
    if r < 0.2:
        kind = 'rock'
        rad = 8
    elif r < 0.4:
        kind = 'bottle'
        rad = 6
    elif r < 0.7:
        kind = 'banana'
        rad = 6
    elif r < 0.8:
        kind = 'tire'
        rad = 10
    else:
        kind = 'firebomb'
        rad = 8
    if len(projectiles) >= MAX_PROJECTILES:
        return
    projectiles.append(Projectile(kind, x0, y0, z0, vx, vy, vz, r=rad))
    throw_anims.append([side, y0, 1.0])
    if len(throw_anims) > 40:
        trim = len(throw_anims) - 40
        del throw_anims[:trim]

def update_projectiles(dt, player):
    for p in list(projectiles):
        if not p.alive:
            continue
        p.x += p.vx * dt
        p.y += p.vy * dt
        p.z += p.vz * dt
        p.vz += GRAVITY * dt
        if p.z <= 2:
            if p.kind == 'tire':
                p.z = 2
                p.vz = -p.vz * 0.45
                p.vx *= 0.96
                p.vy *= 0.98
                if abs(p.vz) < 15:
                    p.vz = 0
            elif p.kind == 'firebomb':
                hazards.append(Hazard('fire', p.x, p.y, 70, 70))
                p.alive = False
            else:
                if p.kind == 'banana':
                    hazards.append(Hazard('oil', p.x, p.y, 46, 46))
                if p.kind in ('rock', 'bottle'):
                    hazards.append(Hazard('wreck', p.x, p.y, 30, 30))
                p.alive = False
        if p.alive:
            hit = False
            for c in cars:
                if not c.alive:
                    continue
                if sphere_aabb_intersect((p.x, p.y, p.z), p.r, c.aabb()):
                    hit = True
                    if p.kind == 'rock':
                        c.vx += 90 * (1 if p.x < c.pos_x else -1)
                        apply_damage(c, 10)
                    elif p.kind == 'bottle':
                        if c.is_player:
                            c.blur_timer = 1.0
                        apply_damage(c, 4)
                    elif p.kind == 'banana':
                        c.spin_timer = 0.8
                    elif p.kind == 'tire':
                        apply_damage(c, 14)
                        c.vx += 60 * (1 if p.x < c.pos_x else -1)
                    elif p.kind == 'firebomb':
                        apply_damage(c, 18)
            if hit:
                p.alive = False
    projectiles[:] = [p for p in projectiles if p.alive and p.y > player.pos_y - 60]
    py = player.pos_y
    kept = []
    for i in range(len(throw_anims)):
        side, y_mark, timer = throw_anims[i]
        if py + VIEW_NEAR - 40 <= y_mark <= py + VIEW_FAR + 40:
            kept.append([side, y_mark, timer])
    throw_anims[:] = kept

def hazard_avoid(c):
    nearest = None
    nearest_dy = 1000000000.0
    for h in hazards:
        dy = h.y - c.pos_y
        if -40 <= dy <= 180:
            dx = h.x - c.pos_x
            if abs(dx) < h.half_w + 24 and abs(dy) < nearest_dy:
                nearest_dy = abs(dy)
                nearest = h
    if nearest is None:
        if c.pos_x > ROAD_HALF - LANE_MARGIN - 8:
            return -0.8
        if c.pos_x < -ROAD_HALF + LANE_MARGIN + 8:
            return 0.8
        return 0.0
    hazard_push = -0.7 if nearest.x > c.pos_x else 0.7
    if c.pos_x > ROAD_HALF - LANE_MARGIN - 8:
        hazard_push -= 0.5
    elif c.pos_x < -ROAD_HALF + LANE_MARGIN + 8:
        hazard_push += 0.5
    return hazard_push

def enforce_collisions(dt):
    for c in cars:
        if not c.alive:
            continue
        for h in hazards:
            if h.kind in ('wreck', 'fire'):
                if separate_car_from_box(c, h.aabb()):
                    apply_damage(c, BUMP_TAP_DAMAGE)
    n = len(cars)
    for i in range(n):
        a = cars[i]
        if not a.alive:
            continue
        for j in range(i + 1, n):
            b = cars[j]
            if not b.alive:
                continue
            if separate_cars(a, b):
                apply_damage(a, CAR_HIT_DAMAGE_RATE * dt)
                apply_damage(b, CAR_HIT_DAMAGE_RATE * dt)

def update(dt):
    global spawn_accum, spawn_interval, running, throw_accum, slow_car_accum, score, has_won
    if not running:
        return
    player = next((c for c in cars if c.is_player and c.alive), None)
    if not player:
        running = False
        has_won = False
        return
    score += dt * 10.0
    throttle = 0.0
    steer = 0.0
    if b'w' in keys_down:
        throttle += 1.0
    if b's' in keys_down:
        throttle -= 1.0
    if b'a' in keys_down:
        steer -= 1.0
    if b'd' in keys_down:
        steer += 1.0
    if player.spin_timer > 0.0:
        steer = 0.0
        throttle *= 0.6
        player.spin_timer -= dt
    if throttle > 0:
        player.speed += ACCEL_RATE * throttle * dt
    elif throttle < 0:
        player.speed += BRAKE_RATE * throttle * dt
    player.speed = clamp(player.speed, 0, PLAYER_MAX_SPEED)
    player.speed *= FRICTION
    player.vx += steer * LATERAL_RATE * dt
    player.vx *= 0.9
    player.pos_y += player.speed * dt
    player.pos_x += player.vx * dt
    max_lat = ROAD_HALF - LANE_MARGIN
    if player.pos_x > max_lat:
        player.pos_x = max_lat
        player.vx *= -0.3
    if player.pos_x < -max_lat:
        player.pos_x = -max_lat
        player.vx *= -0.3
    if player.blur_timer > 0.0:
        player.blur_timer -= dt
    for c in cars:
        if c.is_player or not c.alive:
            continue
        if c.ai_type == 'aggressive':
            target = MAX_SPEED * 0.7
            wander = 1.0
        elif c.ai_type == 'cautious':
            target = MAX_SPEED * 0.4
            wander = 0.6
        elif c.ai_type == 'slow':
            target = 60.0
            wander = 0.2
        else:
            target = MAX_SPEED * 0.5
            wander = 0.8
        if c.speed < target:
            c.speed += ACCEL_RATE * 0.6 * dt
        else:
            c.speed -= ACCEL_RATE * 0.3 * dt
        c.vx += (lcg_randf() - 0.5) * LATERAL_RATE * 0.4 * wander * dt
        c.vx += hazard_avoid(c) * LATERAL_RATE * 0.6 * dt
        c.vx *= 0.9
        c.pos_y += c.speed * dt
        c.pos_x += c.vx * dt
        if c.pos_x > max_lat:
            c.pos_x, c.vx = (max_lat, -abs(c.vx) * 0.3)
        if c.pos_x < -max_lat:
            c.pos_x, c.vx = (-max_lat, abs(c.vx) * 0.3)
    spawn_accum += dt
    if spawn_accum >= spawn_interval:
        spawn_accum = 0.0
        spawn_hazard_random(player)
        if spawn_interval > MIN_SPAWN_INTERVAL:
            spawn_interval = max(MIN_SPAWN_INTERVAL, spawn_interval - SPAWN_INTERVAL_DECAY)
    throw_accum += dt
    if throw_accum >= THROW_INTERVAL:
        throw_accum = 0.0
        for target in cars:
            if target.alive and (target.is_player or target.ai_type != 'slow'):
                spawn_projectile_towards(target)
    update_projectiles(dt, player)
    for c in cars:
        if not c.alive:
            continue
        car_box = c.aabb()
        for h in hazards:
            if aabb_overlap(car_box, h.aabb()):
                if h.kind == 'broken':
                    apply_damage(c, BROKEN_DAMAGE_PER_SEC * dt)
                    c.speed *= 0.96
                elif h.kind == 'fire':
                    apply_damage(c, BROKEN_DAMAGE_PER_SEC * 1.2 * dt)
                elif h.kind == 'oil':
                    c.vx += (1 if lcg_randf() > 0.5 else -1) * OIL_LATERAL_DRIFT
                    c.speed *= 0.95
    enforce_collisions(dt)
    back_cut = player.pos_y - 120
    hazards[:] = [h for h in hazards if h.y > back_cut]
    cars[:] = [c for c in cars if c.is_player or c.ai_type != 'slow' or player.pos_y - SLOW_DESPAWN_MARGIN <= c.pos_y <= player.pos_y + VIEW_FAR + SLOW_DESPAWN_MARGIN]
    for c in cars:
        if not c.is_player and c.alive:
            if player.pos_y - c.pos_y > 1000:
                apply_damage(c, 5 * dt)
    racers_alive = [c for c in cars if c.alive and (c.is_player or (not c.is_player and c.ai_type != 'slow'))]
    player_alive = any((c.is_player and c.alive for c in cars))
    if player_alive and len(racers_alive) == 1:
        running = False
        has_won = True
    elif not player_alive:
        running = False
        has_won = False

def setupCamera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(fovY, WINDOW_W / float(WINDOW_H), 0.1, 3000.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    x, y, z = camera_pos
    tx, ty, tz = camera_target
    gluLookAt(x, y, z, tx, ty, tz, 0, 0, 1)

def draw_track():
    glColor3f(0.2, 0.2, 0.2)
    player = next((c for c in cars if c.is_player), None)
    py = 0 if player is None else player.pos_y
    start_y = int((py + VIEW_NEAR) // SEG_LEN) * SEG_LEN
    end_y = py + VIEW_FAR
    y = start_y
    while y < end_y:
        y0 = y
        y1 = y + SEG_LEN
        glBegin(GL_QUADS)
        glVertex3f(-ROAD_HALF, y0, GROUND_Z)
        glVertex3f(ROAD_HALF, y0, GROUND_Z)
        glVertex3f(ROAD_HALF, y1, GROUND_Z)
        glVertex3f(-ROAD_HALF, y1, GROUND_Z)
        glEnd()
        glColor3f(1, 1, 0.6)
        dash_w = 3
        for k in range(0, SEG_LEN, 40):
            dy0 = y0 + k + 6
            dy1 = y0 + k + 26
            glBegin(GL_QUADS)
            glVertex3f(-dash_w, dy0, GROUND_Z + 0.2)
            glVertex3f(dash_w, dy0, GROUND_Z + 0.2)
            glVertex3f(dash_w, dy1, GROUND_Z + 0.2)
            glVertex3f(-dash_w, dy1, GROUND_Z + 0.2)
            glEnd()
        glColor3f(0.2, 0.2, 0.2)
        y += SEG_LEN
    glColor3f(0.15, 0.35, 0.15)
    glBegin(GL_QUADS)
    glVertex3f(-GRID_LENGTH, py + VIEW_NEAR, GROUND_Z - 0.1)
    glVertex3f(-ROAD_HALF, py + VIEW_NEAR, GROUND_Z - 0.1)
    glVertex3f(-ROAD_HALF, py + VIEW_FAR, GROUND_Z - 0.1)
    glVertex3f(-GRID_LENGTH, py + VIEW_FAR, GROUND_Z - 0.1)
    glVertex3f(ROAD_HALF, py + VIEW_NEAR, GROUND_Z - 0.1)
    glVertex3f(GRID_LENGTH, py + VIEW_NEAR, GROUND_Z - 0.1)
    glVertex3f(GRID_LENGTH, py + VIEW_FAR, GROUND_Z - 0.1)
    glVertex3f(ROAD_HALF, py + VIEW_FAR, GROUND_Z - 0.1)
    glEnd()
    for side in (-1, 1):
        base_x = side * (ROAD_HALF + 100)
        for y_prop in range(int(start_y), int(end_y), 200):
            glColor3f(0.1, 0.5, 0.1)
            draw_box_centered(base_x + (lcg_randf() - 0.5) * 50, y_prop + (lcg_randf() - 0.5) * 50, 10, 8, 8, 20)
            glColor3f(0.6, 0.4, 0.2)
            draw_box_centered(base_x + 50 + (lcg_randf() - 0.5) * 50, y_prop + 50 + (lcg_randf() - 0.5) * 50, 15, 20, 20, 30)

def draw_hazards():
    for h in hazards:
        if h.kind == 'wreck':
            glColor3f(0.45, 0.45, 0.45)
            draw_box_centered(h.x, h.y, 6, h.half_w * 2, h.half_l * 2, 12)
        elif h.kind == 'oil':
            glColor3f(0.05, 0.05, 0.05)
            draw_plate(h.x - h.half_w, h.y - h.half_l, h.half_w * 2, h.half_l * 2, thickness=1.5)
        elif h.kind == 'broken':
            glColor3f(0.45, 0.3, 0.18)
            draw_plate(h.x - h.half_w, h.y - h.half_l, h.half_w * 2, h.half_l * 2, thickness=2.5)
        elif h.kind == 'fire':
            glColor3f(0.85, 0.25, 0.05)
            draw_plate(h.x - h.half_w, h.y - h.half_l, h.half_w * 2, h.half_l * 2, thickness=3)

def draw_projectiles():
    for p in projectiles:
        if not p.alive:
            continue
        if p.kind == 'tire':
            glColor3f(0.1, 0.1, 0.1)
        elif p.kind == 'firebomb':
            glColor3f(0.9, 0.3, 0.1)
        elif p.kind == 'banana':
            glColor3f(1.0, 1.0, 0.2)
        elif p.kind == 'bottle':
            glColor3f(0.2, 0.6, 1.0)
        else:
            glColor3f(0.5, 0.5, 0.5)
        glPushMatrix()
        glTranslatef(p.x, p.y, max(2, p.z))
        quad = gluNewQuadric()
        gluSphere(quad, float(max(4, p.r)), 10, 10)
        glPopMatrix()

def draw_crowd():
    player = next((c for c in cars if c.is_player), None)
    if not player:
        return
    time_sec = glutGet(GLUT_ELAPSED_TIME) / 1000.0
    py = player.pos_y
    start = py + VIEW_NEAR
    end = py + VIEW_FAR
    stand_x = ROAD_HALF + 30
    step = CROWD_STEP
    glColor3f(0.35, 0.2, 0.1)
    glBegin(GL_QUADS)
    glVertex3f(-stand_x - 10, start, 0)
    glVertex3f(-stand_x + 10, start, 0)
    glVertex3f(-stand_x + 10, end, 0)
    glVertex3f(-stand_x - 10, end, 0)
    glVertex3f(stand_x - 10, start, 0)
    glVertex3f(stand_x + 10, start, 0)
    glVertex3f(stand_x + 10, end, 0)
    glVertex3f(stand_x - 10, end, 0)
    glEnd()
    for i in range(len(throw_anims) - 1, -1, -1):
        side_i, y_mark_i, timer_i = throw_anims[i]
        timer_i -= CROWD_ANIM_DECAY
        if timer_i <= 0:
            throw_anims.pop(i)
        else:
            throw_anims[i] = [side_i, y_mark_i, timer_i]
    for side in (-1, 1):
        for line in range(CROWD_LINES):
            base_x = side * stand_x + side * (line * CROWD_LINE_OFFSET)
            for y_person in range(int(start), int(end), step):
                phase = y_person * CROWD_WAVE_SPEED + time_sec * CROWD_BOB_SPEED
                bob = math.sin(phase + line * 0.4 + (0.5 if side < 0 else 0.0)) * CROWD_BOB_AMP
                sway = math.sin(phase * 0.9 + line * 0.7) * (CROWD_SWAY_AMP * 0.2) * side
                color_pick = int(crowd_rand(side, line, y_person) * len(CROWD_SHIRT_COLORS)) % len(CROWD_SHIRT_COLORS)
                shirt_r, shirt_g, shirt_b = CROWD_SHIRT_COLORS[color_pick]
                glColor3f(shirt_r, shirt_g, shirt_b)
                draw_box_centered(base_x + sway, y_person, 20 + bob, 6, 6, 28)
                glColor3f(0.95, 0.85, 0.7)
                draw_box_centered(base_x + sway, y_person, 34 + bob, 4, 4, 4)
                raising = any((abs(y_person - ta[1]) < 20 and ta[0] == side for ta in throw_anims))
                arm_len = 10 if raising else 6
                arm_z0 = 26 + bob
                arm_z1 = arm_z0 + arm_len
                draw_box_centered(base_x + sway - 4 * side, y_person, (arm_z0 + arm_z1) * 0.5, 1.8, 2.2, abs(arm_z1 - arm_z0))
                arm_len_r = 10 if raising else 6
                arm_z0_r = 26 + bob
                arm_z1_r = arm_z0_r + arm_len_r
                draw_box_centered(base_x + sway + 4 * side, y_person, (arm_z0_r + arm_z1_r) * 0.5, 1.8, 2.2, abs(arm_z1_r - arm_z0_r))
                has_flag = crowd_rand(side + 11, line + 5, y_person + 3) < CROWD_FLAG_RATE
                if has_flag:
                    glColor3f(1.0, 1.0, 1.0)
                    draw_box_centered(base_x + sway + 5 * side, y_person, 40 + bob, 1.2, 1.2, 12)
                    wobble = 4 + 2 * math.sin(phase * 1.7)
                    glColor3f(0.9, 0.1, 0.1)
                    draw_plate(base_x + sway + 5 * side + 0.6 * side, y_person - 3, wobble * side, 6, thickness=1.2)

def draw_cars():
    for c in cars:
        x, y, z = (c.pos_x, c.pos_y, CAR_Z)
        yaw = 90
        if not c.alive:
            glColor3f(0.2, 0.2, 0.2)
        else:
            glColor3f(*c.color)
        glPushMatrix()
        glTranslatef(x, y, z)
        glRotatef(yaw, 0, 0, 1)
        glPushMatrix()
        glScalef(CAR_HALF_LEN * 2, CAR_HALF_WID * 2, CAR_HALF_HGT * 1.2)
        glutSolidCube(1.0)
        glPopMatrix()
        glPushMatrix()
        glTranslatef(0, 0, CAR_HALF_HGT * 0.7)
        glScalef(CAR_HALF_LEN * 1.1, CAR_HALF_WID * 1.2, CAR_HALF_HGT * 0.7)
        glColor3f(0.8, 0.8, 0.8)
        glutSolidCube(1.0)
        glPopMatrix()
        if c.is_player:
            glColor3f(0.1, 0.1, 0.1)
            wheel_size = 4

            def wheel(dx, dy):
                glPushMatrix()
                glTranslatef(dx, dy, -CAR_HALF_HGT)
                glScalef(wheel_size, wheel_size, wheel_size)
                glutSolidCube(1.0)
                glPopMatrix()
            wheel(-CAR_HALF_LEN + 2, -CAR_HALF_WID + 2)
            wheel(CAR_HALF_LEN - 2, -CAR_HALF_WID + 2)
            wheel(-CAR_HALF_LEN + 2, CAR_HALF_WID - 2)
            wheel(CAR_HALF_LEN - 2, CAR_HALF_WID - 2)
            glColor3f(0.2, 0.2, 0.2)
            glPushMatrix()
            glTranslatef(-CAR_HALF_LEN, 0, CAR_HALF_HGT + 2)
            glScalef(2, CAR_HALF_WID * 2, 1)
            glutSolidCube(1.0)
            glPopMatrix()
        glPopMatrix()
        if c.alive:
            draw_world_health_bar(x, y, z + CAR_HALF_HGT * 1.6, c.health / MAX_HEALTH)

def draw_world_health_bar(x, y, z, ratio):
    w = 34
    h = 4
    glColor3f(0.1, 0.1, 0.1)
    draw_box_centered(x, y, z, w, h, 1)
    glColor3f(1.0 - ratio, ratio, 0.1)
    draw_box_centered(x - w * 0.5 + w * ratio * 0.5, y, z + 0.5, w * ratio, h - 1, 1)

def draw_box_centered(cx, cy, cz, w, h, d):
    x0 = cx - w * 0.5
    y0 = cy - h * 0.5
    z0 = cz - d * 0.5
    x1 = cx + w * 0.5
    y1 = cy + h * 0.5
    z1 = cz + d * 0.5
    glBegin(GL_QUADS)
    glVertex3f(x0, y0, z1)
    glVertex3f(x1, y0, z1)
    glVertex3f(x1, y1, z1)
    glVertex3f(x0, y1, z1)
    glVertex3f(x0, y0, z0)
    glVertex3f(x1, y0, z0)
    glVertex3f(x1, y1, z0)
    glVertex3f(x0, y1, z0)
    glVertex3f(x0, y1, z0)
    glVertex3f(x1, y1, z0)
    glVertex3f(x1, y1, z1)
    glVertex3f(x0, y1, z1)
    glVertex3f(x0, y0, z0)
    glVertex3f(x1, y0, z0)
    glVertex3f(x1, y0, z1)
    glVertex3f(x0, y0, z1)
    glVertex3f(x0, y0, z0)
    glVertex3f(x0, y1, z0)
    glVertex3f(x0, y1, z1)
    glVertex3f(x0, y0, z1)
    glVertex3f(x1, y0, z0)
    glVertex3f(x1, y1, z0)
    glVertex3f(x1, y1, z1)
    glVertex3f(x1, y0, z1)
    glEnd()

def draw_plate(x0, y0, w, h, thickness=2):
    glBegin(GL_QUADS)
    glVertex3f(x0, y0, GROUND_Z + 0.3)
    glVertex3f(x0 + w, y0, GROUND_Z + 0.3)
    glVertex3f(x0 + w, y0 + h, GROUND_Z + 0.3)
    glVertex3f(x0, y0 + h, GROUND_Z + 0.3)
    glEnd()

def draw_hud_rect(x, y, w, h):
    glBegin(GL_QUADS)
    glVertex2f(x, y)
    glVertex2f(x + w, y)
    glVertex2f(x + w, y + h)
    glVertex2f(x, y + h)
    glEnd()

def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))

def draw_hud():
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    player = next((c for c in cars if c.is_player), None)
    enemies_left = sum((1 for c in cars if c.alive and (not c.is_player)))
    if player is not None:
        ratio = max(0.0, player.health / MAX_HEALTH)
        glColor3f(0.2, 0.2, 0.2)
        draw_hud_rect(20, WINDOW_H - 40, 260, 18)
        glColor3f(1.0 - ratio, ratio, 0.15)
        draw_hud_rect(20, WINDOW_H - 40, 260 * ratio, 18)
    glColor3f(1, 1, 1)
    draw_text(20, WINDOW_H - 70, 'Crowd Crashers - Straight Road')
    if player is not None:
        draw_text(20, WINDOW_H - 100, f'Health: {int(player.health)}  Speed: {int(player.speed)}')
        draw_text(20, WINDOW_H - 120, f'Score: {int(score)}')
    draw_text(20, WINDOW_H - 150, f'Racers Left: {enemies_left}')
    draw_text(20, WINDOW_H - 190, 'Controls: W/S throttle, A/D steer, R reset; Arrows: cam dist/height')
    if player is not None and player.blur_timer > 0.0:
        glColor3f(0, 0, 0)
        glBegin(GL_QUADS)
        glVertex2f(0, 0)
        glVertex2f(WINDOW_W, 0)
        glVertex2f(WINDOW_W, WINDOW_H)
        glVertex2f(0, WINDOW_H)
        glEnd()
    if not running and (not (player is not None and player.blur_timer > 0.0)):
        msg = 'YOU WIN!' if has_won else 'GAME OVER'
        glColor3f(1, 1, 1)
        draw_text(WINDOW_W * 0.45, WINDOW_H * 0.55, msg)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def keyboardListener(key, x, y):
    if isinstance(key, (bytes, bytearray)):
        k = key.lower()
    else:
        k = bytes([key]).lower()
    keys_down.add(k)
    if k == b'r':
        reset_game()

def keyboardUpListener(key, x, y):
    if isinstance(key, (bytes, bytearray)):
        k = key.lower()
    else:
        k = bytes([key]).lower()
    if k in keys_down:
        keys_down.remove(k)

def specialKeyListener(key, x, y):
    global CAM_BACK, CAM_HEIGHT
    if key == GLUT_KEY_LEFT:
        CAM_BACK = max(60.0, CAM_BACK - 6.0)
    elif key == GLUT_KEY_RIGHT:
        CAM_BACK = min(320.0, CAM_BACK + 6.0)
    elif key == GLUT_KEY_UP:
        CAM_HEIGHT = min(260.0, CAM_HEIGHT + 6.0)
    elif key == GLUT_KEY_DOWN:
        CAM_HEIGHT = max(40.0, CAM_HEIGHT - 6.0)

def mouseListener(button, state, x, y):
    pass

def update_camera_follow(dt):
    global camera_pos, camera_target
    p = next((c for c in cars if c.is_player), None)
    if not p:
        return
    fx, fy = (0.0, 1.0)
    px, py, pz = (p.pos_x, p.pos_y, CAR_Z)
    des_eye = (px - fx * CAM_BACK, py - fy * CAM_BACK, pz + CAM_HEIGHT)
    des_tgt = (px + fx * CAM_AHEAD, py + fy * CAM_AHEAD, pz + 3)
    cx, cy, cz = camera_pos
    tx, ty, tz = camera_target
    alpha = min(1.0, CAM_SMOOTH * dt)
    cx = cx + (des_eye[0] - cx) * alpha
    cy = cy + (des_eye[1] - cy) * alpha
    cz = cz + (des_eye[2] - cz) * alpha
    tx = tx + (des_tgt[0] - tx) * alpha
    ty = ty + (des_tgt[1] - ty) * alpha
    tz = tz + (des_tgt[2] - tz) * alpha
    camera_pos = (cx, cy, cz)
    camera_target = (tx, ty, tz)

def idle():
    global last_time_sec
    now_ms = glutGet(GLUT_ELAPSED_TIME)
    now = now_ms / 1000.0
    dt = now - last_time_sec
    if dt < 0:
        dt = 0
    if dt > 0.05:
        dt = 0.05
    last_time_sec = now
    update(dt)
    update_camera_follow(dt)
    glutPostRedisplay()

def showScreen():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glViewport(0, 0, WINDOW_W, WINDOW_H)
    setupCamera()
    draw_track()
    draw_hazards()
    draw_projectiles()
    draw_crowd()
    draw_cars()
    draw_hud()
    glutSwapBuffers()

def reset_game():
    global cars, hazards, projectiles, spawn_interval, spawn_accum
    global throw_accum, running, last_time_sec, slow_car_accum
    global score, has_won, last_hazard_y
    cars = []
    hazards = []
    projectiles = []
    spawn_interval = BASE_SPAWN_INTERVAL
    spawn_accum = 0.0
    throw_accum = 0.0
    slow_car_accum = 0.0
    running = True
    score = 0.0
    has_won = False
    last_time_sec = glutGet(GLUT_ELAPSED_TIME) / 1000.0
    player = Car(True, PLAYER_COLOR, x=0.0, y=0.0, speed=120, name='Player')
    cars.append(player)
    last_hazard_y = player.pos_y
    npc_specs = [('aggressive', -40, 80, 162), ('balanced', 30, 160, 137), ('cautious', 60, -40, 118), ('aggressive', -80, 200, 175), ('balanced', 80, 280, 125), ('cautious', -60, -80, 112)]
    for i in range(len(npc_specs)):
        ai, x, y, spd = npc_specs[i]
        c = Car(False, NPC_COLORS[i % len(NPC_COLORS)], x, y, spd, ai_type=ai, name=f'NPC{i + 1}')
        c.health = 100
        cars.append(c)
    for i in range(1):
        spawn_hazard_random(player)
    spawn_slow_car(player)

def init_gl():
    return

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_W, WINDOW_H)
    glutInitWindowPosition(100, 60)
    glutCreateWindow(b'Crowd Crashers - Straight Road')
    init_gl()
    reset_game()
    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardListener)
    glutKeyboardUpFunc(keyboardUpListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    glutIdleFunc(idle)
    glutMainLoop()
if __name__ == '__main__':
    main()

def check_3d_collision(x1, y1, z1, w1, h1, d1, x2, y2, z2, w2, h2, d2):
    return x1 < x2 + w2 and x1 + w1 > x2 and (y1 < y2 + h2) and (y1 + h1 > y2) and (z1 < z2 + d2) and (z1 + d1 > z2)
