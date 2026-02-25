from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def plot_leverage_vs_roe(path: Path, leverage: np.ndarray, curves: dict[str, np.ndarray]) -> None:
    plt.figure(figsize=(8, 5))
    for label, vals in curves.items():
        plt.plot(leverage, vals * 100, label=label)
    plt.xlabel("Leverage (Notional / Equity)")
    plt.ylabel("Equity ROE (%)")
    plt.title("Leverage vs Equity ROE")
    plt.legend()
    plt.grid(True, alpha=0.3)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def plot_loss_exceedance(path: Path, losses: np.ndarray) -> None:
    sorted_losses = np.sort(losses)
    p = 1 - np.arange(1, len(sorted_losses) + 1) / len(sorted_losses)
    plt.figure(figsize=(8, 5))
    plt.plot(sorted_losses, p)
    plt.xlabel("Loss")
    plt.ylabel("Exceedance Probability")
    plt.title("Loss Exceedance Curve")
    plt.grid(True, alpha=0.3)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
