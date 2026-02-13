import socket
import threading
import json
import queue
import time
import math
import pygame
import pygame.gfxdraw  # 引入進階繪圖庫以獲得更好畫質
import copy

# =====================Q=====================
#               系統參數設定
# ==========================================
SERVER_IP = "10.1.2.107"
PORT = 5001

WIDTH, HEIGHT = 1000, 750  
HUD_H = 140                # UI 高度
WINDOW_BG = (45, 45, 48)   # VS Code 風格深灰色
CANVAS_BG = (255, 255, 255)
ACCENT_COLOR = (0, 122, 204) # 科技藍

BRUSH_MIN, BRUSH_MAX = 2, 60
ERASER_SIZES = [16, 32, 64]
ERASER_SNAP_COUNT = 3

incoming = queue.Queue()

# ============112==============================
#               網路通訊模組 (維持不變)
# ==========================================
def send_json(sock: socket.socket, obj: dict):
    try:
        payload = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
        sock.sendall(payload)
    except Exception as e:
        print(f"Send Error: {e}")

def recv_loop(sock: socket.socket):
    buf = b""
    while True:
        try:
            data = sock.recv(4096)
            if not data: break
            buf += data
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line: continue
                try: incoming.put(json.loads(line))
                except: pass
        except: break

# ==========================================
#               幾何與繪圖核心
# ==========================================
def segment_intersects_rect(ax, ay, bx, by, rect: pygame.Rect) -> bool:
    if rect.collidepoint(ax, ay) or rect.collidepoint(bx, by): return True
    dist = math.hypot(bx - ax, by - ay)
    if dist == 0: return False
    steps = max(4, int(dist / 6))
    for i in range(1, steps):
        t = i / steps
        x = ax + (bx - ax) * t
        y = ay + (by - ay) * t
        if rect.collidepoint(x, y): return True
    return False

def draw_line_round_cap(surface, color, start, end, width):
    x1, y1 = start
    x2, y2 = end
    pygame.draw.line(surface, color, start, end, width)
    if width > 2:
        pygame.draw.circle(surface, color, (int(x1), int(y1)), width // 2)
        pygame.draw.circle(surface, color, (int(x2), int(y2)), width // 2)

def draw_square_stamp(surface, center, size, color):
    x, y = center
    r = pygame.Rect(x - size // 2, y - size // 2, size, size)
    pygame.draw.rect(surface, color, r)

def redraw_all(canvas: pygame.Surface, all_strokes: list):
    canvas.fill(CANVAS_BG)
    for st in all_strokes:
        pts = st["points"]
        color = st["color"]
        if len(pts) < 1: continue
        if st["shape"] == "line":
            if len(pts) == 1: pygame.draw.circle(canvas, color, pts[0], st["w"] // 2)
            else:
                for i in range(1, len(pts)):
                    draw_line_round_cap(canvas, color, pts[i-1], pts[i], st["w"])
        elif st["shape"] == "square":
            for p in pts: draw_square_stamp(canvas, p, st["size"], color)

# ==========================================
#               現代化 UI 元件
# ==========================================
def draw_rounded_rect(surface, rect, color, radius=0.4):
    """
    繪製高品質圓角矩形
    radius: 0.0 ~ 1.0 (相對於高度的比例)
    """
    rect = pygame.Rect(rect)
    color = pygame.Color(*color)
    alpha = color.a
    color.a = 0
    pos = rect.topleft
    rect.topleft = 0,0
    rectangle = pygame.Surface(rect.size, pygame.SRCALPHA)
    
    circle = pygame.Surface([min(rect.size)*3]*2, pygame.SRCALPHA)
    pygame.draw.ellipse(circle, (0, 0, 0), circle.get_rect(), 0)
    circle = pygame.transform.smoothscale(circle, [int(min(rect.size)*radius)]*2)
    
    radius = rectangle.blit(circle, (0, 0))
    radius.bottomright = rect.bottomright
    rectangle.blit(circle, radius)
    radius.topright = rect.topright
    rectangle.blit(circle, radius)
    radius.bottomleft = rect.bottomleft
    rectangle.blit(circle, radius)

    rectangle.fill((0, 0, 0), rect.inflate(-radius.w, 0))
    rectangle.fill((0, 0, 0), rect.inflate(0, -radius.h))

    rectangle.fill(color, special_flags=pygame.BLEND_RGBA_MAX)
    rectangle.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MIN)

    surface.blit(rectangle, pos)

def draw_panel_card(screen, rect, title, font):
    """繪製帶有陰影和標題的區域卡片"""
    # 陰影
    shadow_rect = rect.copy()
    shadow_rect.x += 4
    shadow_rect.y += 4
    draw_rounded_rect(screen, shadow_rect, (30, 30, 30), radius=0.2)
    
    # 本體
    draw_rounded_rect(screen, rect, (60, 60, 65), radius=0.2)
    
    # 標題 (置中)
    title_surf = font.render(title, True, (200, 200, 200))
    title_rect = title_surf.get_rect(centerx=rect.centerx, top=rect.top + 10)
    screen.blit(title_surf, title_rect)
    
    # 分隔線
    pygame.draw.line(screen, (80, 80, 80), (rect.left + 15, rect.top + 35), (rect.right - 15, rect.top + 35), 1)

class ModernButton:
    def __init__(self, rect, label, on_click, *, kind="text", fill=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.kind = kind
        self.fill = fill
        self.selected = False
        self.hovered = False

    def draw(self, screen, font):
        # 決定顏色
        if self.kind == "color":
            base_color = self.fill
            if self.selected:
                pygame.draw.rect(screen, (255, 255, 255), self.rect.inflate(6, 6), border_radius=6)
            draw_rounded_rect(screen, self.rect, base_color, radius=0.5)
            
        else: # Text Button
            if self.selected:
                bg_color = ACCENT_COLOR
                txt_color = (255, 255, 255)
            elif self.hovered:
                bg_color = (80, 80, 80)
                txt_color = (255, 255, 255)
            else:
                bg_color = (50, 50, 50) # 與卡片背景微差
                txt_color = (180, 180, 180)
            
            draw_rounded_rect(screen, self.rect, bg_color, radius=0.3)
            # 邊框
            if not self.selected:
                pygame.draw.rect(screen, (100, 100, 100), self.rect, 1, border_radius=int(self.rect.height * 0.3))

            txt_surf = font.render(self.label, True, txt_color)
            txt_rect = txt_surf.get_rect(center=self.rect.center)
            screen.blit(txt_surf, txt_rect)

    def check_hover(self, pos):
        self.hovered = self.rect.collidepoint(pos)

    def hit(self, pos):
        return self.rect.collidepoint(pos)

class MinimalSlider:
    def __init__(self, rect, *, min_v=0, max_v=1, value=0.5, snap_steps=None, on_change=None):
        self.rect = pygame.Rect(rect)
        self.min_v = min_v
        self.max_v = max_v
        self.value = value
        self.snap_steps = snap_steps
        self.on_change = on_change
        self.dragging = False

    def _pos_to_value(self, x):
        padding = 8
        w = self.rect.width - (padding * 2)
        if w <= 0: return self.min_v
        rel_x = x - (self.rect.left + padding)
        t = max(0.0, min(1.0, rel_x / w))
        return self.min_v + t * (self.max_v - self.min_v)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
                self.update_value(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.update_value(event.pos[0])

    def update_value(self, mouse_x):
        raw = self._pos_to_value(mouse_x)
        if self.snap_steps:
            steps = self.snap_steps - 1
            if steps > 0:
                step_size = (self.max_v - self.min_v) / steps
                idx = round((raw - self.min_v) / step_size)
                self.value = self.min_v + idx * step_size
        else:
            self.value = raw
        if self.on_change: self.on_change(self.value)

    def get_snap_index(self):
        if not self.snap_steps: return 0
        t = (self.value - self.min_v) / (self.max_v - self.min_v)
        return int(round(t * (self.snap_steps - 1)))

    def draw(self, screen):
        # 背景軌道
        cy = self.rect.centery
        padding = 8
        track_w = self.rect.width - 2 * padding
        track_rect = pygame.Rect(self.rect.left + padding, cy - 2, track_w, 4)
        pygame.draw.rect(screen, (80, 80, 80), track_rect, border_radius=2)

        # 進度顏色
        t = (self.value - self.min_v) / (self.max_v - self.min_v)
        fill_w = track_w * t
        fill_rect = pygame.Rect(track_rect.left, track_rect.top, fill_w, 4)
        pygame.draw.rect(screen, ACCENT_COLOR, fill_rect, border_radius=2)

        # 圓形把手
        thumb_x = track_rect.left + fill_w
        pygame.draw.circle(screen, (220, 220, 220), (int(thumb_x), cy), 8)
        # 把手陰影效果
        pygame.draw.circle(screen, (100, 100, 100), (int(thumb_x), cy), 8, 1)


# ==========================================
#               主程式
# ==========================================
def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((SERVER_IP, PORT))
        threading.Thread(target=recv_loop, args=(sock,), daemon=True).start()
    except: pass

    pygame.init()
    # 開啟反鋸齒和硬體加速提示
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Pro Paint")
    clock = pygame.time.Clock()

    # 字體優化：嘗試使用系統字體
    fonts = pygame.font.get_fonts()
    font_name = "arial" if "arial" in fonts else None
    # 標題字體 (大)
    font_title = pygame.font.SysFont(font_name, 20, bold=True)
    # UI 字體 (中)
    font_ui = pygame.font.SysFont(font_name, 16)

    canvas = pygame.Surface((WIDTH, HEIGHT - HUD_H))
    canvas.fill(CANVAS_BG)

    # State
    tool = "pen"
    brush_color = (0, 0, 0)
    brush_w = 6
    eraser_idx = 1
    eraser_size = ERASER_SIZES[eraser_idx]
    
    my_id = None
    all_strokes = []
    stroke_index = {}
    undo_stack = []
    remote_cursor = None
    last_cursor_send = 0.0

    # ================= 介面佈局 (3 Zones) =================
    buttons = []
    
    # 1. Pen Zone (Left)
    PEN_ZONE = pygame.Rect(20, 10, 400, 120)
    
    # Color Palette (2 rows of 5)
    PALETTE = [
        (0, 0, 0), (231, 76, 60), (52, 152, 219), (46, 204, 113), (241, 196, 15),
        (155, 89, 182), (230, 126, 34), (52, 73, 94), (149, 165, 166), (255, 255, 255)
    ]
    cx, cy = PEN_ZONE.left + 20, PEN_ZONE.top + 45
    color_btns = []
    for i, c in enumerate(PALETTE):
        b = ModernButton((cx, cy, 30, 30), "", lambda cc=c: set_color(cc), kind="color", fill=c)
        buttons.append(b)
        color_btns.append(b)
        cx += 38
        if i == 4: # Next row
            cx = PEN_ZONE.left + 20
            cy += 38

    # Brush Slider (Right side of Pen Zone)
    slider_brush = MinimalSlider(
        (PEN_ZONE.left + 220, PEN_ZONE.top + 55, 160, 30),
        min_v=BRUSH_MIN, max_v=BRUSH_MAX, value=brush_w,
        on_change=lambda v: update_brush(v)
    )

    # 2. Eraser Zone (Middle)
    ERASER_ZONE = pygame.Rect(440, 10, 300, 120)
    
    btn_pix = ModernButton((ERASER_ZONE.left + 20, ERASER_ZONE.top + 45, 80, 35), "Pixel", lambda: set_tool("pixel_eraser"))
    btn_itm = ModernButton((ERASER_ZONE.left + 110, ERASER_ZONE.top + 45, 80, 35), "Item", lambda: set_tool("item_eraser"))
    buttons.extend([btn_pix, btn_itm])

    slider_eraser = MinimalSlider(
        (ERASER_ZONE.left + 20, ERASER_ZONE.top + 90, 260, 20),
        min_v=0, max_v=1, value=eraser_idx/(ERASER_SNAP_COUNT-1), snap_steps=ERASER_SNAP_COUNT,
        on_change=lambda v: update_eraser(v)
    )

    # 3. System Zone (Right)
    SYS_ZONE = pygame.Rect(760, 10, 220, 120)
    
    btn_undo = ModernButton((SYS_ZONE.left + 20, SYS_ZONE.top + 45, 80, 50), "Undo", lambda: do_undo())
    btn_clear = ModernButton((SYS_ZONE.left + 120, SYS_ZONE.top + 45, 80, 50), "Clear", lambda: do_clear())
    buttons.extend([btn_undo, btn_clear])

    # Logic Helpers
    def refresh_ui():
        for b in buttons: b.selected = False
        if tool == "pixel_eraser": btn_pix.selected = True
        elif tool == "item_eraser": btn_itm.selected = True
        elif tool == "pen":
            for b in color_btns:
                if b.fill == brush_color: b.selected = True

    def set_tool(t):
        nonlocal tool
        tool = t
        refresh_ui()

    def set_color(c):
        nonlocal tool, brush_color
        brush_color = c
        tool = "pen"
        refresh_ui()

    def update_brush(v):
        nonlocal brush_w
        brush_w = int(round(v))

    def update_eraser(v):
        nonlocal eraser_size, eraser_idx
        idx = slider_eraser.get_snap_index()
        eraser_idx = idx
        eraser_size = ERASER_SIZES[idx]

    def do_undo():
        nonlocal all_strokes, stroke_index

        if not undo_stack:
            return

        action = undo_stack.pop()

        # Undo 畫筆
        if action["type"] == "stroke":
            sid = action["stroke_id"]
            if sid in stroke_index:
                stroke_index.pop(sid)
                all_strokes = [s for s in all_strokes if s["id"] != sid]
                redraw_all(canvas, all_strokes)
                send_json(sock, {"type": "delete_stroke", "stroke_id": sid})

        # Undo Clear
        elif action["type"] == "clear":
            all_strokes = copy.deepcopy(action["strokes"])
            stroke_index = {s["id"]: s for s in all_strokes}
            redraw_all(canvas, all_strokes)

            # 同步給其他人
            send_json(sock, {
                "type": "full_state",
                "strokes": all_strokes
            })


    def do_clear():
        # 1. 記錄 undo
        undo_stack.append({
            "type": "clear",
            "strokes": copy.deepcopy(all_strokes)
        })

        # 2. 本地先 clear（關鍵）
        all_strokes.clear()
        stroke_index.clear()
        redraw_all(canvas, all_strokes)

        # 3. 再通知 server
        send_json(sock, {"type": "clear"})



    refresh_ui()

    # Geometry & Event Loop (簡化版，邏輯同前)
    def get_pos(mp):
        mx, my = mp
        if my > HUD_H: return (mx, my - HUD_H)
        return None

    running = True
    drawing = False
    curr_sid = None
    last_draw_pos = None

    while running:
        # Networking (接收)
        while True:
            try: msg = incoming.get_nowait()
            except: break
            t = msg.get("type")
            if t == "hello": my_id = int(msg["client_id"])
            elif t == "cursor": remote_cursor = (int(msg["x"]), int(msg["y"]))
            elif t == "stroke_begin":
                sid = msg["stroke_id"]
                s_shape = msg.get("shape", "line")
                st = {
                    "id": sid, "owner": int(msg["owner"]), "shape": s_shape,
                    "color": tuple(msg["color"]), 
                    "points": [(int(msg["x"]), int(msg["y"]))]
                }
                if s_shape == "line": st["w"] = int(msg["w"])
                else: st["size"] = int(msg["size"])
                stroke_index[sid] = st
                all_strokes.append(st)
                if s_shape == "square": draw_square_stamp(canvas, st["points"][0], st["size"], st["color"])
            
            elif t == "stroke_point":
                sid = msg["stroke_id"]
                st = stroke_index.get(sid)
                if st:
                    p = (int(msg["x"]), int(msg["y"]))
                    st["points"].append(p)
                    if st["shape"] == "line" and len(st["points"]) >= 2:
                        draw_line_round_cap(canvas, st["color"], st["points"][-2], st["points"][-1], st["w"])
                    elif st["shape"] == "square":
                        draw_square_stamp(canvas, p, st["size"], st["color"])

            elif t == "delete_stroke":
                sid = msg["stroke_id"]
                if sid in stroke_index:
                    stroke_index.pop(sid)
                    all_strokes = [s for s in all_strokes if s["id"] != sid]
                    redraw_all(canvas, all_strokes)

            elif t == "full_state":
                all_strokes = []
                stroke_index = {}

                for st in msg["strokes"]:
                    stroke_index[st["id"]] = st
                    all_strokes.append(st)

                redraw_all(canvas, all_strokes)

            elif t == "clear":
                all_strokes.clear()
                stroke_index.clear()
                redraw_all(canvas, all_strokes)


        # Input
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            
            slider_brush.handle_event(event)
            slider_eraser.handle_event(event)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if my < HUD_H:
                    for b in buttons:
                        if b.hit((mx, my)):
                            b.on_click()
                            break
                else: # Canvas
                    cpos = get_pos((mx, my))
                    if cpos:
                        drawing = True
                        last_draw_pos = cpos
                        # Item Eraser Logic
                        if tool == "item_eraser":
                            r = pygame.Rect(cpos[0]-eraser_size//2, cpos[1]-eraser_size//2, eraser_size, eraser_size)
                            for s in list(all_strokes)[::-1]:
                                if s["owner"] == my_id:
                                    hit = False
                                    if s["shape"]=="square" and any(r.collidepoint(p) for p in s["points"]): hit = True
                                    elif s["shape"]=="line":
                                        for i in range(1, len(s["points"])):
                                            if segment_intersects_rect(*s["points"][i-1], *s["points"][i], r):
                                                hit = True; break
                                    if hit:
                                        send_json(sock, {"type": "delete_stroke", "stroke_id": s["id"]})
                                        # Local delete
                                        stroke_index.pop(s["id"])
                                        all_strokes.remove(s)
                                        redraw_all(canvas, all_strokes)
                                        break
                        else:
                            # Start drawing
                            curr_sid = f"{my_id}-{int(time.time()*1000)}"
                            msg = {"type": "stroke_begin", "stroke_id": curr_sid, "owner": my_id, "x": cpos[0], "y": cpos[1]}
                            
                            if tool == "pen":
                                st = {"id": curr_sid, "owner": my_id, "shape": "line", "color": brush_color, "w": brush_w, "points": [cpos]}
                                msg.update({"shape": "line", "color": list(brush_color), "w": brush_w})
                                pygame.draw.circle(canvas, brush_color, cpos, brush_w//2)
                            else:
                                st = {"id": curr_sid, "owner": my_id, "shape": "square", "color": CANVAS_BG, "size": eraser_size, "points": [cpos]}
                                msg.update({"shape": "square", "color": list(CANVAS_BG), "size": eraser_size})
                                draw_square_stamp(canvas, cpos, eraser_size, CANVAS_BG)
                            
                            stroke_index[curr_sid] = st
                            all_strokes.append(st)
                            undo_stack.append({
                                "type": "stroke",
                                "stroke_id": curr_sid
                            })
                            send_json(sock, msg)

            elif event.type == pygame.MOUSEBUTTONUP:
                drawing = False
                curr_sid = None

            elif event.type == pygame.MOUSEMOTION:
                # Hover effect check
                for b in buttons: b.check_hover((mx, my))

                cpos = get_pos((mx, my))
                if cpos and my_id:
                    if time.time() - last_cursor_send > 0.05:
                        send_json(sock, {"type": "cursor", "x": cpos[0], "y": cpos[1]})
                        last_cursor_send = time.time()
                
                if drawing and cpos and curr_sid:
                    st = stroke_index.get(curr_sid)
                    if st:
                        st["points"].append(cpos)
                        if tool == "pen":
                            if len(st["points"]) >= 2:
                                draw_line_round_cap(canvas, st["color"], st["points"][-2], st["points"][-1], st["w"])
                        elif tool == "pixel_eraser":
                            # Simple interpolation
                            dist = math.hypot(cpos[0]-last_draw_pos[0], cpos[1]-last_draw_pos[1])
                            step = max(2, eraser_size//3)
                            n = int(dist/step)
                            for i in range(1, n+1):
                                t = i/n
                                px = int(last_draw_pos[0] + (cpos[0]-last_draw_pos[0])*t)
                                py = int(last_draw_pos[1] + (cpos[1]-last_draw_pos[1])*t)
                                draw_square_stamp(canvas, (px, py), eraser_size, CANVAS_BG)
                                send_json(sock, {"type": "stroke_point", "stroke_id": curr_sid, "x": px, "y": py})
                            last_draw_pos = cpos
                        
                        if tool == "pen":
                            send_json(sock, {"type": "stroke_point", "stroke_id": curr_sid, "x": cpos[0], "y": cpos[1]})

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_z: do_undo()

        # Render
        screen.fill(WINDOW_BG)
        
        # Draw Zones (Cards)
        draw_panel_card(screen, PEN_ZONE, "PEN", font_title)
        draw_panel_card(screen, ERASER_ZONE, "ERASER", font_title)
        draw_panel_card(screen, SYS_ZONE, "SYSTEM", font_title)

        # UI Elements
        for b in buttons: b.draw(screen, font_ui)
        slider_brush.draw(screen)
        slider_eraser.draw(screen)

        # Canvas
        screen.blit(canvas, (0, HUD_H))

        # Cursors
        if my < HUD_H: pass # Mouse in UI
        else:
            # Custom Cursor Preview
            cpos = (mx, my - HUD_H)
            p_y = my
            if tool == "pen":
                pygame.draw.circle(screen, brush_color, (mx, my), brush_w//2, 1)
                pygame.draw.circle(screen, (200, 200, 200), (mx, my), brush_w//2+1, 1)
            else:
                s = eraser_size
                pygame.draw.rect(screen, (0,0,0), (mx-s//2, my-s//2, s, s), 1)

        if remote_cursor:
            rx, ry = remote_cursor
            pygame.draw.circle(screen, (0, 255, 0), (rx, ry+HUD_H), 5)

        pygame.display.flip()
        clock.tick(120)

    pygame.quit()

if __name__ == "__main__":
    main()