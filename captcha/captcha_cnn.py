#!/usr/bin/env python3
"""Captcha CNN: 5 positional slot heads on 150x50 input (winner of exp2).
Each head reads only its own 30px-wide window (grid 6x20, 4 cols/char),
turning the task into 5 independent clean glyph classifications."""
import json, argparse, random, os
import numpy as np
from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms as T
from torch.utils.data import Dataset, DataLoader

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("CAPTCHA_DATA_DIR", os.path.join(HERE, "data"))
OUT = os.environ.get("CAPTCHA_OUT_DIR", os.path.join(HERE, "cnn_out"))
SEED = 42
TEST_FRAC = 0.05
W, H = 150, 50
N_CHARS = 5

AUG_TRAIN = T.Compose([
    T.RandomAffine(degrees=5, translate=(0.05, 0.05), scale=(0.95, 1.05),
                   shear=3, fill=255),
    T.ColorJitter(brightness=0.15, contrast=0.15),
    T.GaussianBlur(kernel_size=3, sigma=(0.1, 0.5)),
])
BASE = T.Compose([T.Grayscale(), T.ToTensor(), T.Normalize(0.5, 0.5)])

def blk(i, o):
    return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU())

class Net(nn.Module):
    """2 maxpools only: captcha strokes are ~2px; /16 (4 pools) destroys them.
    (6,20) grid -> each of the 5 heads sees exactly its 4-col (30px) window."""
    def __init__(self, n_cls):
        super().__init__()
        self.b1 = nn.Sequential(blk(1, 32), blk(32, 32), nn.MaxPool2d(2))     # 75x25
        self.b2 = nn.Sequential(blk(32, 64), blk(64, 64), nn.MaxPool2d(2))    # 37x12
        self.b3 = nn.Sequential(blk(64, 128), blk(128, 128))                  # 37x12
        self.pool = nn.AdaptiveAvgPool2d((6, 20))
        self.drop = nn.Dropout(0.35)
        self.slots = nn.ModuleList([
            nn.Sequential(nn.Linear(128 * 6 * 4, 256), nn.ReLU(), nn.Linear(256, n_cls))
            for _ in range(N_CHARS)
        ])
    def forward(self, x):
        x = self.pool(self.b3(self.b2(self.b1(x))))          # B,128,6,20
        x = self.drop(x)
        return [self.slots[s](x[:, :, :, 4 * s:4 * s + 4].flatten(1)) for s in range(N_CHARS)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[dev] {dev}")

    mf = json.load(open(f"{DATA}/manifest.json"))
    chars = sorted({c for e in mf for c in e["answer"]})
    c2i = {c: i for i, c in enumerate(chars)}
    print(f"[data] {len(mf)} captchas, alphabet {len(chars)} chars: {''.join(chars)}")

    rng = np.random.RandomState(SEED)
    idx = rng.permutation(len(mf))
    n_test = int(len(mf) * TEST_FRAC)
    te_idx, tr_idx = idx[:n_test], idx[n_test:]
    print(f"[split] train={len(tr_idx)} test={len(te_idx)}")

    def load(ix, aug=False):
        e = mf[ix]
        img = Image.open(f"{DATA}/{e['file']}").convert("RGB")
        if aug: img = AUG_TRAIN(img)
        x = BASE(img)
        y = torch.tensor([c2i[c] for c in e["answer"]])  # exactly 5
        return x, y

    class DS(Dataset):
        def __init__(self, ix, aug=False): self.ix = ix; self.aug = aug
        def __len__(self): return len(self.ix)
        def __getitem__(self, i): return load(self.ix[i], self.aug)

    tr, te = DS(tr_idx, aug=True), DS(te_idx)
    tr_l = DataLoader(tr, batch_size=args.batch, shuffle=True, num_workers=0, drop_last=False)

    net = Net(len(chars)).to(dev)
    print(f"[model] {sum(p.numel() for p in net.parameters())/1e3:.0f}K params")
    opt = torch.optim.Adam(net.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)

    @torch.no_grad()
    def evaluate(ds, name):
        net.eval()
        exact = chars_ok = tot = 0
        for x, y in DataLoader(ds, batch_size=64):
            x, y = x.to(dev), y.to(dev)
            outs = [F.log_softmax(o, 1) for o in net(x)]
            pred = torch.stack([o.argmax(1) for o in outs], 1)
            exact += (pred == y).all(1).sum().item()
            chars_ok += (pred == y).sum().item()
            tot += len(y)
        net.train()
        print(f"    [{name}] exact={exact/tot*100:.1f}% char={chars_ok/(tot*5)*100:.1f}%")
        return exact / tot

    best = 0.0
    for ep in range(args.epochs):
        tot_l = n = 0
        for x, y in tr_l:
            x, y = x.to(dev), y.to(dev)
            outs = net(x)
            loss = sum(F.cross_entropy(o, y[:, i], label_smoothing=0.1) for i, o in enumerate(outs))
            opt.zero_grad(); loss.backward(); opt.step()
            tot_l += loss.item(); n += 1
        sched.step()
        if ep % 2 == 0 or ep == args.epochs - 1:
            acc = evaluate(te, f"ep{ep+1} loss={tot_l/n:.3f}")
            if acc >= best:
                best = acc
                os.makedirs(OUT, exist_ok=True)
                torch.save(net.state_dict(), f"{OUT}/best.pt")
                print(f"    -> saved best {acc*100:.1f}%")
    print(f"[done] best eval exact = {best*100:.1f}%  ({OUT}/best.pt)")

    # final test on best
    net.load_state_dict(torch.load(f"{OUT}/best.pt", map_location=dev))
    net.eval()
    exact = 0
    for i in te_idx:
        x, y = load(i)
        pred = "".join(chars[o.argmax().item()] for o in net(x.unsqueeze(0).to(dev)))
        gold = mf[i]["answer"]
        exact += pred == gold
    print(f"[TEST n={len(te_idx)}] exact captcha acc = {exact/len(te_idx)*100:.2f}%")
    for i in te_idx[:15]:
        x, _ = load(i)
        pred = "".join(chars[o.argmax().item()] for o in net(x.unsqueeze(0).to(dev)))
        print(f"    gold={mf[i]['answer']} pred={pred} {'OK' if pred==mf[i]['answer'] else 'x'}")

if __name__ == "__main__":
    main()
