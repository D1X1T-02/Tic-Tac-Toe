import pygame
import pygame.gfxdraw
import sys, random, math
from typing import List, Tuple, Optional

# ------------------------------------------------------------
# Constants / Colours
# ------------------------------------------------------------
WIDTH, HEIGHT = 720, 720
FPS = 60
CELL = 200
ORIGIN = ((WIDTH - 3 * CELL) // 2, (HEIGHT - 3 * CELL) // 2)

BG_TOP    = (12, 12, 30)
BG_BOTTOM = (30, 20, 55)

GRID_LINE   = (40, 45, 80)
CELL_BG     = (22, 22, 40)
CELL_HOVER  = (255, 255, 255, 25)

X_COL = (255, 80, 80)
O_COL = (80, 200, 255)
X_GLOW = (255, 120, 120, 80)
O_GLOW = (120, 230, 255, 80)

WIN_COL = (255, 215, 0)
WIN_GLOW = (255, 235, 100, 120)

BTN_BASE  = (30, 30, 55)
BTN_HOVER = (45, 45, 80)
BTN_TEXT  = (230, 235, 245)

PARTICLES = 130
PARTICLE_MAX_R = 3

EMPTY, PLAYER, BOT = 0, 1, 2
WIN_COMBOS = [(0,1,2),(3,4,5),(6,7,8),
              (0,3,6),(1,4,7),(2,5,8),
              (0,4,8),(2,4,6)]

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def lerp(a,b,t): return a + (b-a)*t
def clamp(v,lo,hi): return max(lo, min(hi, v))

# ------------------------------------------------------------
# Gradient background surface (created once)
# ------------------------------------------------------------
def make_gradient():
    surf = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y/HEIGHT
        r = int(lerp(BG_TOP[0], BG_BOTTOM[0], t))
        g = int(lerp(BG_TOP[1], BG_BOTTOM[1], t))
        b = int(lerp(BG_TOP[2], BG_BOTTOM[2], t))
        pygame.draw.line(surf, (r,g,b), (0,y), (WIDTH,y))
    return surf

# ------------------------------------------------------------
# Particle system (mouse attraction + fade)
# ------------------------------------------------------------
class Particle:
    __slots__ = ("x","y","vx","vy","r","life","max_life","col")
    def __init__(self):
        self.reset()
    def reset(self):
        self.x = random.uniform(0, WIDTH)
        self.y = random.uniform(0, HEIGHT)
        angle = random.uniform(0, 2*math.pi)
        speed = random.uniform(0.2, 0.6)
        self.vx = math.cos(angle)*speed
        self.vy = math.sin(angle)*speed
        self.r = random.uniform(1, PARTICLE_MAX_R)
        self.max_life = random.uniform(4, 8)
        self.life = self.max_life
        self.col = (120, 180, 255, random.randint(30, 120))
    def update(self, mx, my, dt):
        dx, dy = mx - self.x, my - self.y
        d2 = dx*dx + dy*dy
        if d2 < 40000 and d2>0:
            f = 0.03 * (1 - d2/40000)
            self.vx += dx/math.sqrt(d2) * f
            self.vy += dy/math.sqrt(d2) * f
        self.vx *= 0.985
        self.vy *= 0.985
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.life -= dt
        if self.life <= 0 or not (0<=self.x<=WIDTH and 0<=self.y<=HEIGHT):
            self.reset()
    def draw(self, surf):
        a = int(lerp(0, self.col[3], self.life/self.max_life))
        pygame.gfxdraw.filled_circle(surf, int(self.x), int(self.y),
                                     max(1, int(self.r)), (*self.col[:3], a))

# ------------------------------------------------------------
# Button with gradient, hover‑scale, ripple
# ------------------------------------------------------------
class Button:
    def __init__(self, rect, text, callback):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.callback = callback
        self.hover = False
        self.scale = 1.0
        self.ripple = 0.0
    def update(self, mouse, dt):
        self.hover = self.rect.collidepoint(mouse)
        target = 1.06 if self.hover else 1.0
        self.scale = lerp(self.scale, target, dt*12)
        if self.ripple>0:
            self.ripple = max(0, self.ripple - dt*3)
    def click(self):
        if self.hover and self.callback:
            self.ripple = 1.0
            self.callback()
    def draw(self, surf, font):
        cx, cy = self.rect.center
        w, h = int(self.rect.w*self.scale), int(self.rect.h*self.scale)
        r = pygame.Rect(0,0,w,h); r.center = (cx,cy)

        base = pygame.Surface((w,h), pygame.SRCALPHA)
        for yy in range(h):
            t = yy/h
            col = (int(lerp(BTN_BASE[0], BTN_HOVER[0], t)),
                   int(lerp(BTN_BASE[1], BTN_HOVER[1], t)),
                   int(lerp(BTN_BASE[2], BTN_HOVER[2], t)), 255)
            pygame.draw.line(base, col, (0,yy), (w,yy))
        mask = pygame.Surface((w,h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255,255,255,255), mask.get_rect(), border_radius=14)
        base.blit(mask, (0,0), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(base, r.topleft)

        if self.ripple>0:
            rad = int(lerp(0, max(w,h), self.ripple))
            alpha = int(lerp(80,0,self.ripple))
            ripple_surf = pygame.Surface((rad*2, rad*2), pygame.SRCALPHA)
            pygame.draw.circle(ripple_surf, (255,255,255,alpha), (rad,rad), rad)
            surf.blit(ripple_surf, (cx-rad, cy-rad), special_flags=pygame.BLEND_ADD)

        txt = font.render(self.text, True, BTN_TEXT)
        surf.blit(txt, txt.get_rect(center=(cx,cy)))

# ------------------------------------------------------------
# Minimax (depth‑limited for medium)
# ------------------------------------------------------------
def check_winner(b):
    for a,b1,c in WIN_COMBOS:
        if b[a] and b[a]==b[b1]==b[c]:
            return b[a], (a,c)
    if EMPTY not in b: return -1, None
    return None, None

def minimax(board, depth, maximizing, max_depth):
    w,_ = check_winner(board)
    if w==PLAYER: return -10+depth
    if w==BOT:    return 10-depth
    if w==-1:     return 0
    if max_depth is not None and depth>=max_depth: return 0
    if maximizing:
        best=-math.inf
        for i,v in enumerate(board):
            if v==EMPTY:
                board[i]=BOT
                best=max(best, minimax(board,depth+1,False,max_depth))
                board[i]=EMPTY
        return best
    else:
        best=math.inf
        for i,v in enumerate(board):
            if v==EMPTY:
                board[i]=PLAYER
                best=min(best, minimax(board,depth+1,True,max_depth))
                board[i]=EMPTY
        return best

def bot_move(board, diff):
    if diff==0:
        return random.choice([i for i,v in enumerate(board) if v==EMPTY])
    max_depth = 2 if diff==1 else None
    best=-math.inf; move=None
    for i,v in enumerate(board):
        if v==EMPTY:
            board[i]=BOT
            sc=minimax(board,0,False,max_depth)
            board[i]=EMPTY
            if sc>best: best,move=sc,i
    return move

# ------------------------------------------------------------
# Main Game
# ------------------------------------------------------------
class TicTacToe:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Tic‑Tac‑Toe ✨")
        self.screen = pygame.display.set_mode((WIDTH,HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.SysFont("segoeui", 86, bold=True)
        self.font_ui  = pygame.font.SysFont("segoeui", 30)
        self.font_sm  = pygame.font.SysFont("segoeui", 22)

        self.bg_grad = make_gradient()
        self.particles = [Particle() for _ in range(PARTICLES)]

        self.board = [EMPTY]*9
        self.anim = [0.0]*9          # pop‑in 0‑1
        self.current = PLAYER
        self.winner = None
        self.win_line = None         # will hold (sx,sy,ex,ey) in pixels
        self.line_prog = 0.0
        self.confetti = []
        self.state = "menu"
        self.diff = 1
        self._build_menu()

    # ---- menu ----
    def _build_menu(self):
        cx, cy = WIDTH//2, HEIGHT//2
        self.menu_btns = []
        for i,(lbl,d) in enumerate([("Easy",0),("Medium",1),("Hard",2)]):
            b = Button((cx-130, cy-90+i*80, 260, 56), lbl,
                       lambda d=d: self._start(d))
            self.menu_btns.append(b)

    def _start(self, diff):
        self.diff = diff
        self._reset()
        self.state = "playing"

    # ---- reset ----
    def _reset(self):
        self.board = [EMPTY]*9
        self.anim = [0.0]*9
        self.current = PLAYER
        self.winner = None
        self.win_line = None
        self.line_prog = 0.0
        self.confetti.clear()

    # ---- events ----
    def handle(self, ev):
        if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            if self.state=="menu":
                for b in self.menu_btns: b.click()
            elif self.state=="playing" and self.current==PLAYER and not self.winner:
                self._try_player(ev.pos)
            elif self.state=="over":
                self.state="menu"
        if ev.type==pygame.MOUSEMOTION:
            if self.state=="menu":
                for b in self.menu_btns: b.update(ev.pos,0)

        if ev.type==pygame.USEREVENT:
            self._bot_turn()

    def _try_player(self, pos):
        mx,my=pos; gx,gy=ORIGIN
        if gx<=mx<gx+3*CELL and gy<=my<gy+3*CELL:
            col=(mx-gx)//CELL; row=(my-gy)//CELL
            idx=row*3+col
            if self.board[idx]==EMPTY:
                self.board[idx]=PLAYER
                self.anim[idx]=1.0
                self._check_end()
                if not self.winner:
                    self.current=BOT
                    pygame.time.set_timer(pygame.USEREVENT, 300, True)

    def _bot_turn(self):
        if self.state!="playing" or self.winner: return
        mv=bot_move(self.board, self.diff)
        if mv is not None:
            self.board[mv]=BOT
            self.anim[mv]=1.0
            self._check_end()
            self.current=PLAYER

    # --------------------------------------------------------
    #  Win detection – store **pixel** coordinates, not indices
    # --------------------------------------------------------
    def _check_end(self):
        w, line = check_winner(self.board)
        if w:
            self.winner = w
            self.state = "over"
            self.line_prog = 0.0
            self._spawn_confetti()

            if line:
                a, c = line                       # cell indices 0‑8
                gx, gy = ORIGIN
                ar, ac = divmod(a, 3)              # row, col of first cell
                cr, cc = divmod(c, 3)              # row, col of last cell
                sx = gx + ac * CELL + CELL // 2
                sy = gy + ar * CELL + CELL // 2
                ex = gx + cc * CELL + CELL // 2
                ey = gy + cr * CELL + CELL // 2
                self.win_line = (sx, sy, ex, ey)   # store pixel end‑points
            else:
                self.win_line = None                # draw case – no line

    def _spawn_confetti(self):
        for _ in range(120):
            ang=random.uniform(0,2*math.pi)
            spd=random.uniform(150,300)
            self.confetti.append({
                "x":WIDTH/2, "y":HEIGHT/2,
                "vx":math.cos(ang)*spd, "vy":math.sin(ang)*spd,
                "life":random.uniform(1.5,3.0),
                "col":random.choice([X_COL,O_COL,WIN_COL]),
                "size":random.uniform(3,6)
            })

    # ---- update ----
    def update(self, dt, mouse):
        for p in self.particles: p.update(*mouse, dt)
        for i in range(9):
            if self.anim[i]<1: self.anim[i]=clamp(self.anim[i]+dt*7,0,1)
        if self.winner and self.line_prog<1:
            self.line_prog=clamp(self.line_prog+dt*1.8,0,1)
        for c in self.confetti[:]:
            c["x"]+=c["vx"]*dt; c["y"]+=c["vy"]*dt
            c["vy"]+=400*dt
            c["life"]-=dt
            if c["life"]<=0: self.confetti.remove(c)
        if self.state=="menu":
            for b in self.menu_btns: b.update(mouse, dt)

    # ---- drawing helpers ----
    def _draw_grid(self):
        gx,gy=ORIGIN
        for r in range(3):
            for c in range(3):
                rx=gx+c*CELL; ry=gy+r*CELL
                cell_surf=pygame.Surface((CELL,CELL), pygame.SRCALPHA)
                pygame.draw.rect(cell_surf, CELL_BG, cell_surf.get_rect(), border_radius=18)
                shadow=pygame.Surface((CELL,CELL), pygame.SRCALPHA)
                pygame.draw.rect(shadow, (0,0,0,30), shadow.get_rect(), border_radius=18)
                cell_surf.blit(shadow,(0,0), special_flags=pygame.BLEND_RGBA_SUB)
                self.screen.blit(cell_surf,(rx,ry))
        for i in range(1,3):
            pygame.draw.line(self.screen, GRID_LINE,
                             (gx+i*CELL, gy), (gx+i*CELL, gy+3*CELL), 4)
            pygame.draw.line(self.screen, GRID_LINE,
                             (gx, gy+i*CELL), (gx+3*CELL, gy+i*CELL), 4)

    def _draw_marks(self):
        gx,gy=ORIGIN
        for idx,val in enumerate(self.board):
            if val==EMPTY: continue
            r,c=divmod(idx,3)
            cx=gx+c*CELL+CELL//2
            cy=gy+r*CELL+CELL//2
            scale=self.anim[idx]
            sz=int(CELL*0.38*scale)
            if val==PLAYER:
                gsurf=pygame.Surface((sz*2,sz*2), pygame.SRCALPHA)
                pygame.draw.line(gsurf, X_GLOW,
                                 (sz-sz, sz-sz), (sz+sz, sz+sz), 10)
                pygame.draw.line(gsurf, X_GLOW,
                                 (sz+sz, sz-sz), (sz-sz, sz+sz), 10)
                self.screen.blit(gsurf, (cx-sz, cy-sz), special_flags=pygame.BLEND_ADD)
                pygame.draw.line(self.screen, X_COL,
                                 (cx-sz, cy-sz), (cx+sz, cy+sz), 10)
                pygame.draw.line(self.screen, X_COL,
                                 (cx+sz, cy-sz), (cx-sz, cy+sz), 10)
            else:
                gsurf=pygame.Surface((sz*2,sz*2), pygame.SRCALPHA)
                pygame.draw.circle(gsurf, O_GLOW, (sz,sz), sz, 10)
                self.screen.blit(gsurf, (cx-sz, cy-sz), special_flags=pygame.BLEND_ADD)
                pygame.draw.circle(self.screen, O_COL, (cx,cy), sz, 10)

    # --------------------------------------------------------
    #  Draw the animated win line using the saved pixel points
    # --------------------------------------------------------
    def _draw_win_line(self):
        if not self.win_line:
            return
        sx, sy, ex, ey = self.win_line

        length = math.hypot(ex - sx, ey - sy) * self.line_prog
        angle = math.atan2(ey - sy, ex - sx)
        mx = sx + math.cos(angle) * length
        my = sy + math.sin(angle) * length

        pygame.draw.line(self.screen, WIN_GLOW, (sx, sy), (mx, my), 14)
        pygame.draw.line(self.screen, WIN_COL,  (sx, sy), (mx, my), 8)

    def _draw_confetti(self):
        for c in self.confetti:
            alpha=int(clamp(c["life"]/3*255,0,255))
            surf=pygame.Surface((int(c["size"]*2), int(c["size"]*2)), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*c["col"], alpha), (int(c["size"]), int(c["size"])), int(c["size"]))
            self.screen.blit(surf, (c["x"]-c["size"], c["y"]-c["size"]))

    def _draw_overlay(self):
        dim=pygame.Surface((WIDTH,HEIGHT), pygame.SRCALPHA)
        dim.fill((0,0,0,160))
        self.screen.blit(dim,(0,0))
        if self.winner==-1: txt="Draw!"; col=(200,200,200)
        elif self.winner==PLAYER: txt="You Win!"; col=X_COL
        else: txt="Bot Wins!"; col=O_COL
        surf=self.font_big.render(txt, True, col)
        self.screen.blit(surf, surf.get_rect(center=(WIDTH//2, HEIGHT//2-30)))
        hint=self.font_sm.render("Click anywhere for menu", True, (180,180,180))
        self.screen.blit(hint, hint.get_rect(center=(WIDTH//2, HEIGHT//2+60)))

    # ---- render ----
    def draw(self):
        self.screen.blit(self.bg_grad,(0,0))
        for p in self.particles: p.draw(self.screen)

        if self.state=="menu":
            title=self.font_big.render("TIC‑TAC‑TOE", True, (220,230,255))
            self.screen.blit(title, title.get_rect(center=(WIDTH//2, HEIGHT//2-180)))
            sub=self.font_ui.render("Choose difficulty", True, (150,170,200))
            self.screen.blit(sub, sub.get_rect(center=(WIDTH//2, HEIGHT//2-130)))
            for b in self.menu_btns: b.draw(self.screen, self.font_ui)
        else:
            self._draw_grid()
            self._draw_marks()
            if self.winner:
                self._draw_win_line()
                self._draw_confetti()
                self._draw_overlay()

        pygame.display.flip()

    # ---- loop ----
    def run(self):
        while True:
            dt=self.clock.tick(FPS)/1000.0
            mouse=pygame.mouse.get_pos()
            for ev in pygame.event.get():
                self.handle(ev)
            self.update(dt, mouse)
            self.draw()

if __name__=="__main__":
    TicTacToe().run()