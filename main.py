import sys, os, socket, threading
import tkinter as tk
from tkinter import font as tkfont

PORT = 18888
CHECK_INTERVAL = 3000  # 每 3 秒检查一次各项目 agent 进程是否存活

# 支持的 agent CLI：命令行关键字 → 显示名
AGENTS = {
    "claude": "claude",
    "codex":  "codex",
}

# 马赛克配色：高饱和度像素风
COLORS = {
    "run":     "#FFD93D",  # 明黄
    "success": "#6BCB77",  # 嫩绿
    "error":   "#FF6B6B",  # 暖红
}
LABELS = {
    "run":     "RUNNING",
    "success": "SUCCESS",
    "error":   "FAILED",
    "dead":    "DEAD",
}
DARK   = "#1A1B26"   # 背景深色（夜空）
PANEL  = "#24283B"   # 卡片底色
BORDER = "#414868"   # 卡片边
DIM    = "#3B4261"   # 未点亮灯体
TEXT   = "#C0CAF5"   # 主文字
SUB    = "#7AA2F7"   # 副文字/边框高亮
GRID_L = "#2A2E44"   # 网格线

# --- 工具：沿父进程链找到 agent (claude / codex) 进程的 PID ---
def find_agent_pid():
    """从当前进程往上找，返回命令行含 'claude' 或 'codex' 的祖先进程 PID；找不到返回 0。"""
    pid = os.getppid()
    seen = set()
    while pid and pid not in seen:
        seen.add(pid)
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\x00", b" ").decode("utf-8", "ignore")
        except Exception:
            # macOS / 无 /proc：用 ps
            try:
                cmd = os.popen(f"ps -p {pid} -o command=").read().strip()
            except Exception:
                cmd = ""
        # 排除自身脚本，匹配已知 agent CLI
        if "main.py" not in cmd and any(k in cmd for k in AGENTS):
            return pid
        # 走到父进程
        try:
            ppid = int(os.popen(f"ps -p {pid} -o ppid=").read().strip())
        except Exception:
            break
        pid = ppid if ppid != pid else 0
    return 0

def pid_alive(pid):
    if not pid:
        return True  # 没拿到 PID 时不贸然判死
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False

# --- 核心：发送端 ---
def send_signal(action, name):
    pid = find_agent_pid()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(f"{action}|{name}|{pid}".encode('utf-8'), ('127.0.0.1', PORT))
    sys.exit(0)

# --- 核心：接收端 (GUI) ---
# 三色灯：红=error / 黄=run / 绿=success
LAMP_ORDER  = ["error", "run", "success"]
LAMP_COLORS = {
    "error":   "#FF5C5C",
    "run":     "#FFD23F",
    "success": "#3DDC84",
}
LAMP_GLOW = {
    "error":   "#FF8A8A",
    "run":     "#FFE680",
    "success": "#7CEFB3",
}

LAMP_R   = 18          # 灯半径
LAMP_GAP = 14          # 灯之间间距
HOUSE_PAD_X = 20       # 灯箱左右内边距
HOUSE_PAD_TOP = 16     # 灯箱上内边距
HOUSE_PAD_BOT = 16     # 灯箱下内边距
HOUSE_W = (LAMP_R + HOUSE_PAD_X) * 2
HOUSE_H = LAMP_R * 2 * 3 + LAMP_GAP * 2 + HOUSE_PAD_TOP + HOUSE_PAD_BOT

CARD_W = max(HOUSE_W + 28, 150)
CARD_H = HOUSE_H + 86   # 灯箱 + 标题/状态文字
CARD_PAD = 18

DIM_LAMP = "#2B2F45"
HOUSE_BG = "#0F1018"
HOUSE_BORDER = "#3A3F5C"
ACCENT = "#5E6BFF"

# 每个 agent 的品牌强调色，用于给卡片底色/边框染色，便于一眼区分
AGENT_ACCENT = {
    "claude": "#D97757",   # Anthropic 暖橙
    "codex":  "#10A37F",   # OpenAI 青绿
}
DEFAULT_ACCENT = "#5E6BFF"

def _agent_accent(name):
    """按名字匹配 agent 强调色；未命中走默认。"""
    n = (name or "").lower()
    for key, color in AGENT_ACCENT.items():
        if key in n:
            return color
    return DEFAULT_ACCENT

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def _mix(c1, c2, t):
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return f"#{int(r1+(r2-r1)*t):02X}{int(g1+(g2-g1)*t):02X}{int(b1+(b2-b1)*t):02X}"

def _draw_lamp(c, cx, cy, state_key, active, dead, tags="lit"):
    """画一盏灯。active=True 时点亮，否则熄灭（暗灰）。dead=True 时所有灯更暗。"""
    if state_key is None:
        base = DIM_LAMP
        glow = DIM_LAMP
    else:
        if dead:
            base = _mix(DARK, LAMP_COLORS[state_key], 0.18)
            glow = base
        elif active:
            base = LAMP_COLORS[state_key]
            glow = LAMP_GLOW[state_key]
        else:
            # 未点亮但同色系：保留极淡色彩提示
            base = _mix(DARK, LAMP_COLORS[state_key], 0.12)
            glow = base

    r = LAMP_R
    # 外光晕（仅点亮时）
    if active and not dead:
        for i, alpha_r in enumerate([r + 10, r + 6, r + 3]):
            halo = _mix(DARK, LAMP_COLORS[state_key], 0.10 + 0.05 * (2 - i))
            c.create_oval(cx - alpha_r, cy - alpha_r,
                          cx + alpha_r, cy + alpha_r,
                          fill=halo, outline="", tags=(tags,))
    # 灯体外圈
    c.create_oval(cx - r, cy - r, cx + r, cy + r,
                  fill=_mix(base, "#000000", 0.25), outline="", tags=(tags,))
    # 灯体主色
    c.create_oval(cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2,
                  fill=base, outline="", tags=(tags,))
    # 高光（点亮时）
    if active and not dead:
        hi_r = r - 6
        c.create_oval(cx - hi_r - 2, cy - hi_r - 4,
                      cx - hi_r + 4, cy - hi_r + 2,
                      fill=glow, outline="", tags=(tags,))

def _lamp_centers(ox, oy):
    """返回三盏灯的圆心坐标，顺序 = LAMP_ORDER。"""
    centers = []
    y = oy + HOUSE_PAD_TOP + LAMP_R
    for _ in LAMP_ORDER:
        centers.append((ox + HOUSE_W / 2, y))
        y += LAMP_R * 2 + LAMP_GAP
    return centers

def _draw_housing(c, hx, hy):
    """画灯箱外壳。"""
    pad = 4
    c.create_rectangle(hx - pad, hy - pad,
                       hx + HOUSE_W + pad, hy + HOUSE_H + pad,
                       fill=HOUSE_BORDER, outline="", tags="house")
    c.create_rectangle(hx, hy, hx + HOUSE_W, hy + HOUSE_H,
                       fill=HOUSE_BG, outline="", tags="house")
    # 顶部小帽檐
    c.create_rectangle(hx - pad, hy - pad,
                       hx + HOUSE_W + pad, hy + 2,
                       fill=ACCENT, outline="", tags="house")

def _parse_active(action):
    """action 可以是单灯（run/success/error），也可逗号分隔多灯（error,success）。返回点亮的灯集合。"""
    if not action:
        return set()
    return {k.strip() for k in str(action).split(",") if k.strip() in LAMP_ORDER}

def _paint_state(c, ox, oy, active_set, dead, tag="lit"):
    """根据 active_set 点亮对应灯，其余熄灭。tag 用于限定只清除本卡的灯。"""
    c.delete(tag)
    centers = _lamp_centers(ox, oy)
    for i, key in enumerate(LAMP_ORDER):
        cx, cy = centers[i]
        _draw_lamp(c, cx, cy, key, active=(key in active_set), dead=dead, tags=tag)

class TrafficLightApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.configure(bg=DARK)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        # 起始位置
        self._start_x, self._start_y = 80, 80
        self.root.geometry(f"+{self._start_x}+{self._start_y}")

        # 字体
        self._f_title = tkfont.Font(family="Menlo", size=12, weight="bold")
        self._f_sub   = tkfont.Font(family="Menlo", size=9)
        self._f_head  = tkfont.Font(family="Menlo", size=11, weight="bold")

        # 主容器
        self.canvas = tk.Canvas(self.root, bg=DARK, highlightthickness=0,
                                borderwidth=0)
        self.canvas.pack(fill="both", expand=True)

        self.cards = {}   # name -> {frame_id, canvas, lit_items..., ...}
        self._title_id = None
        self._hint_id = None
        self._relayout()

        # 拖拽整个窗口
        self._drag_dx = 0
        self._drag_dy = 0
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        # 双击退出
        self.canvas.bind("<Double-Button-1>", self.quit)
        # 右键也退出
        self.canvas.bind("<ButtonPress-3>", lambda e: self.quit())

    # ---- 布局 ----
    def _relayout(self):
        n = len(self.cards)
        if n == 0:
            # 没有任何 agent → 直接隐藏窗口，避免空框残留
            self.root.withdraw()
            return
        self.root.deiconify()
        cols = max(1, min(3, n))
        rows = max(1, (n + cols - 1) // cols)
        w = cols * (CARD_W + CARD_PAD) + CARD_PAD
        h = rows * (CARD_H + CARD_PAD) + CARD_PAD + 26
        self.root.geometry(f"{w}x{h}+{self.root.winfo_x()}+{self.root.winfo_y()}")
        self._draw_all()

    def _draw_all(self):
        self.canvas.delete("all")
        # 顶部标题
        self._title_id = self.canvas.create_text(
            CARD_PAD + 2, 10, anchor="nw",
            text="🚦  AGENT MONITOR",
            fill=ACCENT, font=self._f_head)
        # 卡片们
        for i, (name, info) in enumerate(self.cards.items()):
            self._draw_card(i, name, info)

    def _draw_card(self, index, name, info):
        cols = max(1, min(3, len(self.cards)))
        cx = CARD_PAD + (index % cols) * (CARD_W + CARD_PAD)
        cy = 32 + (index // cols) * (CARD_H + CARD_PAD)

        # 按 agent 取强调色，并据此染色卡片底色/边框
        accent = _agent_accent(name)
        panel_fill  = _mix(PANEL, accent, 0.22)   # 卡片底：品牌色微染
        border_fill = _mix(BORDER, accent, 0.45)  # 卡片边：更亮一点
        info["accent"] = accent

        # 卡片阴影
        self.canvas.create_rectangle(cx - 1, cy,
                                     cx + CARD_W + 3, cy + CARD_H + 3,
                                     fill="#0A0B12", outline="", tags="card")
        # 卡片底板
        self.canvas.create_rectangle(cx, cy,
                                     cx + CARD_W, cy + CARD_H,
                                     fill=panel_fill, outline="", tags="card")
        # 卡片描边
        self.canvas.create_rectangle(cx, cy,
                                     cx + CARD_W, cy + CARD_H,
                                     fill="", outline=border_fill, width=1, tags="card")
        # 卡片顶部装饰条（渐变感，用三段拼接）
        seg = CARD_W / 3
        for i, key in enumerate(LAMP_ORDER):
            self.canvas.create_rectangle(cx + i * seg, cy,
                                         cx + (i + 1) * seg, cy + 3,
                                         fill=LAMP_COLORS[key], outline="", tags="card")

        # 项目名（卡片顶部）—— 用 agent 强调色，进一步区分
        disp = name if len(name) <= 14 else name[:13] + "…"
        self.canvas.create_text(cx + CARD_W / 2, cy + 20,
                                text=disp, fill=accent,
                                font=self._f_title, tags="card")

        # 灯箱位置（水平居中）
        hx = cx + (CARD_W - HOUSE_W) / 2
        hy = cy + 38
        _draw_housing(self.canvas, hx, hy)
        ox, oy = hx, hy
        info["ox"] = ox
        info["oy"] = oy
        tag = info.get("tag", "lit")
        _paint_state(self.canvas, ox, oy, info.get("active", set()),
                     info.get("dead", False), tag=tag)

        # 状态文字（灯箱下方）
        label, color = self._label_for(info.get("active", set()),
                                       info.get("dead", False))
        info["label_id"] = self.canvas.create_text(
            cx + CARD_W / 2, cy + CARD_H - 14,
            text=label, fill=color, font=self._f_sub, tags="card")

    def _label_for(self, active, dead=False):
        if dead:
            return LABELS["dead"], "#565F89"
        if not active:
            return "IDLE", SUB
        if len(active) == 1:
            k = next(iter(active))
            return LABELS.get(k, "IDLE"), COLORS.get(k, SUB)
        joined = "+".join(LABELS.get(k, k.upper())
                          for k in LAMP_ORDER if k in active)
        return joined, ACCENT

    # ---- 信号处理 ----
    def update(self, action, name, pid=0):
        if action == "quit":
            self.quit()
            return
        if action == "hide":
            # 完全隐藏窗口，但 mainloop 继续运行，进程不退出
            self.root.withdraw()
            return
        if action == "show":
            # 恢复窗口显示（仅当有卡片时才有意义）
            if self.cards:
                self.root.deiconify()
            return
        active = _parse_active(action)
        if name not in self.cards:
            self.cards[name] = {
                "action": action, "pid": pid, "dead": False,
                "active": active,
                "tag": f"lit_{len(self.cards)}",
            }
            self._relayout()
            return
        info = self.cards[name]
        info["action"] = action
        info["pid"] = pid
        info["dead"] = False
        info["active"] = active
        # 多卡并存时，缓存的 ox/oy 可能已因其它卡增删而过期，
        # 局部重画会把灯画到错误位置 → 直接全量重排，保证灯与文字一致。
        self._relayout()

    def quit(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def watch_claude(self):
        # 收集已退出的 agent 对应的卡片名，统一移除
        to_remove = []
        for name, info in self.cards.items():
            if info.get("dead"):
                continue
            if not pid_alive(info["pid"]):
                to_remove.append(name)
                print(f"👻 检测到 [{name}] 的 agent 已退出，卡片已销毁。")
        if to_remove:
            for name in to_remove:
                del self.cards[name]
            # 所有红绿灯都关了 → GUI 一起消失
#             if not self.cards:
#                 print("👋 所有 agent 已退出，监控窗口关闭。")
#                 self.quit()
#                 return
            # _relayout 内部会 delete("all") + 重画所有剩余卡片，
            # 不要在这里 delete("card")——那会把所有卡的底板/标题/label 一起删掉。
            self._relayout()
        self.root.after(CHECK_INTERVAL, self.watch_claude)

    # ---- 拖拽 ----
    def _on_press(self, e):
        self._drag_dx = e.x
        self._drag_dy = e.y
    def _on_drag(self, e):
        x = self.root.winfo_x() + (e.x - self._drag_dx)
        y = self.root.winfo_y() + (e.y - self._drag_dy)
        self.root.geometry(f"+{x}+{y}")

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        # 模式一：发送信号 (例如: python .light.py run my_project)
        send_signal(sys.argv[1], sys.argv[2])
    else:
        # 模式二：启动桌面端
        app = TrafficLightApp()
        def listen():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('127.0.0.1', PORT))
            while True:
                data, _ = sock.recvfrom(1024)
                parts = data.decode('utf-8').split('|')
                action = parts[0] if len(parts) > 0 else ""
                name   = parts[1] if len(parts) > 1 else ""
                pid    = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
                app.root.after(0, app.update, action, name, pid)
        threading.Thread(target=listen, daemon=True).start()
        print("🚦 红绿灯界面已启动，请将此窗口留在后台。")
        app.root.after(CHECK_INTERVAL, app.watch_claude)
        app.root.mainloop()
