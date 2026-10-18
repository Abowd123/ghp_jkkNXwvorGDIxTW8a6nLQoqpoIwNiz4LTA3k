"""Animated GIFs: buckling modes, beam deflection, vibration modes."""
from __future__ import annotations
import io
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from ..core import fmt
from .plots import BLUE, RED, GREEN, DARK, GREY


def _frames_to_gif(frames, ms=70) -> bytes:
    buf = io.BytesIO()
    imgs = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in frames]
    imgs[0].save(buf, format="GIF", save_all=True, append_images=imgs[1:], duration=ms, loop=0, optimize=True)
    return buf.getvalue()


def _fig_img(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=80, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).copy()


CASES = [("Pinned–Pinned", 1.0, lambda y: np.sin(np.pi * y)),
         ("Fixed–Free", 2.0, lambda y: 1 - np.cos(np.pi * y / 2)),
         ("Fixed–Pinned", 0.699, None),
         ("Fixed–Fixed", 0.5, lambda y: 1 - np.cos(2 * np.pi * y))]


def _fixed_pinned(y):
    """Exact fixed (y=0) – pinned (y=1) buckling mode, kL = 4.4934 (root of tan kL = kL)."""
    k = 4.4934
    v = (k * y - np.sin(k * y)) - (k - np.sin(k)) / (1 - np.cos(k)) * (1 - np.cos(k * y))
    return -v / np.max(np.abs(v))


def buckling_gif(E=200e6, I=8e-6, L=4.0, A=None) -> bytes:
    frames = []
    y = np.linspace(0, 1, 120)
    for t in np.linspace(0, 2 * np.pi, 28, endpoint=False):
        amp = 0.18 * math.sin(t)
        fig, axs = plt.subplots(1, 4, figsize=(10, 4.6))
        for ax, (name, K, f) in zip(axs, CASES):
            shape = (_fixed_pinned(y) if f is None else f(y))
            shape = shape / np.max(np.abs(shape))
            Pcr = math.pi**2 * E * I / (K * L) ** 2
            ax.plot([0, 0], [0, 1], color=GREY, ls="--", lw=1)
            ax.plot(amp * shape, y, color=RED, lw=3)
            # supports
            ax.plot([-0.12, 0.12], [0, 0], color=DARK, lw=3)
            if name in ("Fixed–Free", "Fixed–Pinned", "Fixed–Fixed"):
                for k in np.linspace(-0.12, 0.12, 6):
                    ax.plot([k, k - 0.04], [0, -0.04], color=DARK, lw=1)
            if name != "Fixed–Free":
                tip = amp * shape[-1]
                ax.plot([-0.12 + tip, 0.12 + tip], [1, 1], color=DARK, lw=3 if name == "Fixed–Fixed" else 1.5)
            ax.annotate("", xy=(amp * shape[-1], 1.0), xytext=(amp * shape[-1], 1.18), arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=2))
            ax.set_title(f"{name}\nK = {K}", fontsize=10, fontweight="bold")
            ax.text(0, -0.15, f"Pcr = {fmt(Pcr, 1)} kN", ha="center", fontsize=9)
            ax.set_xlim(-0.35, 0.35); ax.set_ylim(-0.22, 1.25); ax.axis("off")
        fig.suptitle(f"Euler buckling modes  (EI = {fmt(E*I)} kN·m², L = {fmt(L)} m)   Pcr = π²EI/(KL)²", fontweight="bold")
        frames.append(_fig_img(fig))
    return _frames_to_gif(frames, 80)


def beam_deflection_gif(res) -> bytes:
    """Load ramp animation of the deflected shape from a BeamResult."""
    frames = []
    d = res.defl
    dm = np.max(np.abs(d)) or 1
    L = res.beam.L
    sc = 0.12 * L / dm
    steps = list(np.linspace(0, 1, 14)) + [1.0] * 6 + list(np.linspace(1, 0, 8))
    for k in steps:
        fig, ax = plt.subplots(figsize=(8, 3.2))
        ax.plot([0, L], [0, 0], color=GREY, ls="--")
        ax.plot(res.x, d * sc * k, color=GREEN, lw=4)
        for s in res.beam.supports:
            ax.plot([s.x], [-0.01 * L], marker="^", ms=14, color=DARK)
        i = int(np.argmax(np.abs(d)))
        ax.text(res.x[i], d[i] * sc * k + (0.03 * L if d[i] < 0 else -0.05 * L), f"{fmt(abs(d[i]) * 1000 * k, 2)} mm", ha="center", color=GREEN, fontweight="bold")
        ax.set_xlim(-0.05 * L, 1.05 * L); ax.set_ylim(-0.2 * L, 0.2 * L); ax.axis("off")
        ax.set_title(f"Deflection under increasing load ({int(k * 100)}%)", fontweight="bold")
        frames.append(_fig_img(fig))
    return _frames_to_gif(frames, 90)


def vibration_gif(L=6.0, EI=5e4, m=500.0, modes=3) -> bytes:
    """Simply supported beam modes: ωn = (nπ/L)²·√(EI/m)."""
    x = np.linspace(0, L, 200)
    frames = []
    for t in np.linspace(0, 2 * np.pi, 32, endpoint=False):
        fig, axs = plt.subplots(modes, 1, figsize=(8, 2 * modes))
        for n, ax in enumerate(np.atleast_1d(axs), 1):
            w = (n * np.pi / L) ** 2 * math.sqrt(EI * 1e3 / m)
            f = w / (2 * np.pi)
            ax.plot([0, L], [0, 0], color=GREY, ls="--", lw=1)
            ax.plot(x, 0.6 * np.sin(n * np.pi * x / L) * math.sin(n * t), color=[BLUE, RED, GREEN][(n - 1) % 3], lw=3)
            ax.plot([0, L], [-0.08, -0.08], ls="none", marker="^", ms=10, color=DARK)
            ax.set_ylim(-0.9, 0.9); ax.axis("off")
            ax.set_title(f"Mode {n}: f = {fmt(f, 2)} Hz", fontsize=10, loc="left", fontweight="bold")
        fig.suptitle(f"Free vibration, simply supported beam (L = {fmt(L)} m, EI = {fmt(EI)} kN·m², m = {fmt(m)} kg/m)", fontsize=10)
        fig.tight_layout()
        frames.append(_fig_img(fig))
    return _frames_to_gif(frames, 70)
