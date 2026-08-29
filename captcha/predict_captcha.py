#!/usr/bin/env python3
"""Predict the 5-char answer of a 150x50 Edusp captcha image.

Usage:
    python3 predict_captcha.py /path/to/captcha.png
    python3 predict_captcha.py /path/to/captcha.png --model cnn_out/best.pt
    echo /path/to/captcha.png | python3 predict_captcha.py

Standalone: no imports from the training script. Model definition is embedded
here and MUST match captcha_cnn.py's Net architecture (slot heads, 6x20 grid).
Requires: torch, torchvision, Pillow, numpy.
"""
import argparse, json, os, sys
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms as T

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL = os.environ.get("CAPTCHA_MODEL_WEIGHTS", os.path.join(HERE, "best.pt"))
MANIFEST = os.path.join(HERE, "data", "manifest.json")
ALPHABET = "23456789abcdefghijklmnopqrstuvwxyz"  # fallback if manifest missing

N_CHARS = 5
BASE = T.Compose([T.Grayscale(), T.ToTensor(), T.Normalize(0.5, 0.5)])


def blk(i, o):
    return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU())


class Net(nn.Module):
    def __init__(self, n_cls):
        super().__init__()
        self.b1 = nn.Sequential(blk(1, 32), blk(32, 32), nn.MaxPool2d(2))
        self.b2 = nn.Sequential(blk(32, 64), blk(64, 64), nn.MaxPool2d(2))
        self.b3 = nn.Sequential(blk(64, 128), blk(128, 128))
        self.pool = nn.AdaptiveAvgPool2d((6, 20))
        self.drop = nn.Dropout(0.35)
        self.slots = nn.ModuleList([
            nn.Sequential(nn.Linear(128 * 6 * 4, 256), nn.ReLU(), nn.Linear(256, n_cls))
            for _ in range(N_CHARS)
        ])

    def forward(self, x):
        x = self.pool(self.b3(self.b2(self.b1(x))))
        x = self.drop(x)
        return [self.slots[s](x[:, :, :, 4 * s:4 * s + 4].flatten(1)) for s in range(N_CHARS)]


def load_alphabet():
    if os.path.isfile(MANIFEST):
        try:
            mf = json.load(open(MANIFEST))
            chars = sorted({c for e in mf for c in e["answer"]})
            if chars:
                return "".join(chars)
        except Exception:
            pass
    return ALPHABET


def predict(net, chars, img_path, dev):
    img = Image.open(img_path).convert("RGB")
    x = BASE(img).unsqueeze(0).to(dev)
    with torch.no_grad():
        outs = net(x)
    return "".join(chars[o.argmax().item()] for o in outs)


def main():
    ap = argparse.ArgumentParser(description="Predict 5-char answer of a captcha image")
    ap.add_argument("image", nargs="?", help="path to captcha PNG (or pipe it via stdin)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"model weights (default: {DEFAULT_MODEL})")
    args = ap.parse_args()

    path = args.image
    if not path:
        path = sys.stdin.read().strip()
    if not path:
        ap.error("no image path given")

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    chars = load_alphabet()
    net = Net(len(chars))
    net.load_state_dict(torch.load(args.model, map_location=dev))
    net.to(dev).eval()

    print(predict(net, chars, path, dev))


if __name__ == "__main__":
    main()
