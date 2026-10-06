#!/usr/bin/env python3
"""galaga-lite —— 迷你 Galaga 克隆：敌机编队 + 俯冲攻击。

纯标准库。小巧取舍：回合制行输入交互 + --auto 无头演示，无实时键盘输入。
"""

import argparse
import math
import random
import sys

W, H = 30, 20          # 场地
PLAYER_Y = H - 2       # 玩家行
ENEMY_ROWS, ENEMY_COLS = 3, 8
DIVE_EVERY = 40        # 每隔多少帧派出一架俯冲
PLAYER_BULLET_VY = -2.0
ENEMY_BULLET_VY = 1.0
DUAL_SCORE = 500       # 双打机奖励（击杀俯冲中敌机一定概率掉落）


class Enemy:
    __slots__ = ("x", "y", "diving", "t", "sx", "score")

    def __init__(self, x, y, score=50):
        self.x, self.y = float(x), float(y)
        self.diving = False   # 是否俯冲中
        self.t = 0.0          # 俯冲相位
        self.sx = x           # 俯冲起点 x
        self.score = score


class Bullet:
    __slots__ = ("x", "y", "vy", "enemy")

    def __init__(self, x, y, vy, enemy=False):
        self.x, self.y = float(x), float(y)
        self.vy = vy
        self.enemy = enemy


class Game:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.px = W // 2
        self.dual = False      # 双打机
        self.lives = 3
        self.score = 0
        self.frame = 0
        self.over = False
        self.win = False
        self.enemies = []
        for r in range(ENEMY_ROWS):
            for c in range(ENEMY_COLS):
                x = 3 + c * 3
                y = 2 + r * 2
                sc = 50 if r == 2 else (100 if r == 1 else 150)
                self.enemies.append(Enemy(x, y, sc))
        self.bullets = []
        self._cool = 0

    # ---------- 玩家 ----------
    def move_player(self, dx):
        self.px = max(1, min(W - 2, self.px + dx))

    def player_shoot(self):
        if self._cool > 0:
            return False
        xs = [self.px - 1, self.px + 1] if self.dual else [self.px]
        for x in xs:
            self.bullets.append(Bullet(x, PLAYER_Y - 1, PLAYER_BULLET_VY))
        self._cool = 4
        return True

    # ---------- 敌机 ----------
    def _formation_cx(self):
        return W / 2 + 4 * math.sin(self.frame * 0.02)

    def _step_enemies(self):
        cx = self._formation_cx()
        for e in self.enemies:
            if e.diving:
                # 俯冲：正弦曲线向下
                e.t += 0.12
                e.y += 0.9
                e.x = e.sx + 6 * math.sin(e.t * 2)
                if e.y >= PLAYER_Y:      # 冲到底部，返回编队顶部
                    e.diving = False
                    e.y = 2.0
                    e.x = cx + (e.sx - W / 2)
            else:
                e.x += (cx - W / 2) * 0.02
                e.x = max(1.0, min(W - 2.0, e.x))
        # 定期派俯冲
        if self.frame % DIVE_EVERY == 0 and self.frame > 0:
            cands = [e for e in self.enemies if not e.diving]
            if cands:
                e = self.rng.choice(cands)
                e.diving = True
                e.t = 0.0
                e.sx = e.x

    def _enemy_fire(self):
        # 每列最下一架有概率开火
        if self.frame % 25 != 0:
            return
        cols = {}
        for e in self.enemies:
            key = round(e.x)
            if key not in cols or e.y > cols[key].y:
                cols[key] = e
        for e in cols.values():
            if self.rng.random() < 0.25:
                self.bullets.append(Bullet(e.x, e.y + 1, ENEMY_BULLET_VY, enemy=True))

    # ---------- 主循环 ----------
    def step(self, cmd=None):
        """cmd: 'a' 左移 / 'd' 右移 / 's' 开火 / None 不动。"""
        if self.over:
            return
        self.frame += 1
        if self._cool > 0:
            self._cool -= 1
        if cmd == "a":
            self.move_player(-1)
        elif cmd == "d":
            self.move_player(1)
        elif cmd == "s":
            self.player_shoot()

        self._step_enemies()
        self._enemy_fire()

        # 子弹移动 + 碰撞
        keep_b, keep_e = [], []
        hit_enemy = set()
        for b in self.bullets:
            b.y += b.vy
            if b.y < 0 or b.y >= H:
                continue
            if b.enemy:
                # 敌方子弹命中玩家
                if abs(b.x - self.px) < 1.0 and abs(b.y - PLAYER_Y) < 1.0:
                    self._lose_life()
                    continue
                keep_b.append(b)
            else:
                # 玩家子弹命中敌机（含俯冲中）
                hit = None
                for e in self.enemies:
                    if id(e) in hit_enemy:
                        continue
                    if abs(b.x - e.x) < 1.0 and abs(b.y - e.y) < 1.0:
                        hit = e
                        break
                if hit is not None:
                    hit_enemy.add(id(hit))
                    self.score += hit.score * (2 if hit.diving else 1)
                    if hit.diving and self.rng.random() < 0.3 and not self.dual:
                        self.dual = True
                        self.score += DUAL_SCORE
                else:
                    keep_b.append(b)
        self.bullets = keep_b
        self.enemies = [e for e in self.enemies if id(e) not in hit_enemy]

        # 俯冲敌机撞玩家
        for e in self.enemies:
            if e.diving and abs(e.x - self.px) < 1.0 and abs(e.y - PLAYER_Y) < 1.0:
                self._lose_life()
                self.enemies.remove(e)
                break

        if not self.enemies:
            self.win = True
            self.over = True

    def _lose_life(self):
        self.lives -= 1
        self.dual = False
        if self.lives <= 0:
            self.over = True


def render(g):
    grid = [[" " for _ in range(W)] for _ in range(H)]
    for e in g.enemies:
        x, y = int(e.x), int(e.y)
        if 0 <= x < W and 0 <= y < H:
            grid[y][x] = "V" if e.diving else ("W" if e.y < 4 else "M")
    for b in g.bullets:
        x, y = int(b.x), int(b.y)
        if 0 <= x < W and 0 <= y < H:
            grid[y][x] = "!" if b.enemy else "|"
    x = int(g.px)
    grid[PLAYER_Y][x] = "A"
    if g.dual and x + 1 < W:
        grid[PLAYER_Y][x + 1] = "A"
    bar = f" 分数 {g.score}  生命 {g.lives}  敌机 {len(g.enemies)}" + ("  双打!" if g.dual else "")
    return bar + "\n" + "\n".join("".join(row) for row in grid)


def auto_play(seed=None, frames=800, verbose=False):
    g = Game(seed)
    f = 0
    while not g.over and f < frames:
        # AI：躲俯冲敌机/敌方子弹，瞄准最近敌机开火
        danger = None
        for e in g.enemies:
            if e.diving and e.y > PLAYER_Y - 6 and abs(e.x - g.px) < 3:
                danger = e.x
                break
        if danger is not None:
            g.step("a" if danger > g.px else "d")
        else:
            # 瞄准编队中心
            alive = [e for e in g.enemies if not e.diving]
            if alive:
                tx = sum(e.x for e in alive) / len(alive)
                if abs(tx - g.px) > 1:
                    g.step("a" if tx < g.px else "d")
                else:
                    g.step("s")
            else:
                g.step()
        f += 1
        if verbose and f % 100 == 0:
            print(render(g))
    status = "胜利" if g.win else ("失败" if g.over else "未结束")
    print(f"自动演示结束：{status}，得分 {g.score}，剩余敌机 {len(g.enemies)}，生命 {g.lives}，帧数 {f}")
    return g


def play_interactive(seed=None):
    if not sys.stdin.isatty():
        print("交互模式需要终端；请用 --auto 观看演示。", file=sys.stderr)
        sys.exit(2)
    g = Game(seed)
    print("galaga-lite：a 左移 / d 右移 / s 开火 / q 退出，每行一个命令。")
    while not g.over:
        print(render(g))
        try:
            cmd = input("> ").strip().lower()
        except EOFError:
            break
        if cmd == "q":
            break
        g.step(cmd if cmd in "ads" else None)
    print(render(g))
    print("胜利！" if g.win else "游戏结束。", f"得分 {g.score}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="galaga-lite：迷你 Galaga 克隆")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--auto", action="store_true", help="无头自动演示")
    ap.add_argument("--frames", type=int, default=800)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)
    if a.auto:
        auto_play(a.seed, a.frames, a.verbose)
    else:
        play_interactive(a.seed)


if __name__ == "__main__":
    main()
