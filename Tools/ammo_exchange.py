"""
Ammo exchange ratio generator for the Grayson trader override (trader_grayson).

Generates integer "give X rounds of A -> get Y rounds of B" trades such that NO
sequence of exchanges can ever end with more ammo than you started with
(every cycle A -> ... -> A has a product of rates strictly < 1).

Why 5 Circular Trades?
----------------------
Grayson's trader screen (W_TraderScreen) uses a 2-column by 7-row ShopGridPanel,
providing exactly 14 display slots (Column 0: 7 slots, Column 1: 7 slots).
Vanilla Grayson has 9 trades. Adding a 5-node circular cycle:
    9mm -> Magnum -> 12g -> .308 -> 5.56 -> 9mm
brings the total to exactly 14 trades (9 vanilla + 5 circular), perfectly filling
both columns with zero overflow.

High Efficiency (95% - 99% Value Retention):
--------------------------------------------
Every trade keeps 95% - 99% of the fair trade value (only 1% - 5% fee), using
the mathematically minimal integer lots:
- Give 21 9mm    -> Get 10 Magnum  (95.24% eff, fee 4.76%) [Unlocks: Manufacturing_Arrived]
- Give 11 Magnum -> Get  7 12g     (95.45% eff, fee 4.55%) [Unlocks: Labs_Containment_Entered]
- Give  7 12g    -> Get 10 .308    (95.24% eff, fee 4.76%) [Unlocks: Dams_ReachedCentral]
- Give  4 .308   -> Get 13 5.56    (97.50% eff, fee 2.50%) [Unlocks: Dams_ReachedCentral]
- Give  7 5.56   -> Get  4 9mm     (95.24% eff, fee 4.76%) [Unlocks: Dams_ReachedCentral]

Full Cycle Return: 80.40% (strictly no arbitrage).

Usage:
    python Tools/ammo_exchange.py            # inspect circular cycle (default, 14 total trades)
    python Tools/ammo_exchange.py --apply    # automatically patch trader_MyProject.uasset!
    python Tools/ammo_exchange.py --restore  # restores vanilla trader_MyProject.uasset from backup
    python Tools/ammo_exchange.py --verify   # checks trader_MyProject.uasset for existing trades
    python Tools/ammo_exchange.py --mode hub # hub-and-spoke via 9mm (8 trades)
    python Tools/ammo_exchange.py --mode full# all pairs (20 trades)
"""

from __future__ import annotations

import argparse
import itertools
import math
import os
import struct
import sys
from pathlib import Path

# Add Tools directory to sys.path so we can import patch_uasset_trades
tools_dir = Path(__file__).resolve().parent
if str(tools_dir) not in sys.path:
    sys.path.insert(0, str(tools_dir))

import patch_uasset_trades

DEFAULT_UASSET_PATH = str(patch_uasset_trades.DEFAULT_ASSET_PATH)
BACKUP_UASSET_PATH = str(patch_uasset_trades.BACKUP_PATH)

FALLBACK_ROUNDS_PER_TRADE = {
    "ammo_9mm": (42, "oil_robot"),
    "ammo_12g": (14, "woodplank"),
    "ammo_Magnum": (21, "chains"),
    "ammo_308": (21, "growth"),
    "ammo_556": (70, "magalloy"),
}

ITEM_VALUE = {
    "oil_robot": 1.0,
    "woodplank": 1.0,
    "chains": 1.0,
    "growth": 1.0,
    "magalloy": 1.0,
}

FALLBACK_WORLD_FLAG = {
    "ammo_9mm": "Manufacturing_Arrived",
    "ammo_12g": "Labs_Containment_Entered",
    "ammo_Magnum": "Manufacturing_Arrived",
    "ammo_308": "Dams_ReachedCentral",
    "ammo_556": "Dams_ReachedCentral",
}

FLAG_ORDER = ["Manufacturing_Arrived", "Labs_Containment_Entered", "Dams_ReachedCentral"]
HUB = "ammo_9mm"

# Progression-aligned circular cycle
CYCLE_PAIRS = [
    ("ammo_9mm", "ammo_Magnum"),
    ("ammo_Magnum", "ammo_12g"),
    ("ammo_12g", "ammo_308"),
    ("ammo_308", "ammo_556"),
    ("ammo_556", "ammo_9mm"),
]


# ---------------------------------------------------------------------------
# Dynamic Asset Reader
# ---------------------------------------------------------------------------

def get_base_ammo_data(uasset_path: str):
    """Extracts ammo base trades (ammo output for non-ammo cost) and world flags."""
    check_path = uasset_path
    if os.path.exists(BACKUP_UASSET_PATH):
        check_path = BACKUP_UASSET_PATH

    rounds_per_trade = dict(FALLBACK_ROUNDS_PER_TRADE)
    world_flags = dict(FALLBACK_WORLD_FLAG)
    source = "fallback constants"

    try:
        trades = patch_uasset_trades.parse_trades(Path(check_path))
        if trades:
            loaded = {}
            flags = {}
            for t in trades:
                out_item = t["out_item"]
                cost_item = t["cost_item"]
                if out_item.startswith("ammo") and not cost_item.startswith("ammo"):
                    loaded[out_item] = (t["out_count"], cost_item)
                    flags[out_item] = t["flag"]
            if loaded:
                rounds_per_trade = loaded
                world_flags = flags
                source = f"{Path(check_path).name} ({len(loaded)} base ammo trades detected)"
            return rounds_per_trade, world_flags, source, trades
    except Exception:
        pass

    return rounds_per_trade, world_flags, source, []


# ---------------------------------------------------------------------------
# Core Ratio Logic
# ---------------------------------------------------------------------------

def compute_ammo_values(rounds_per_trade: dict[str, tuple[int, str]]) -> dict[str, float]:
    """Value per round, normalised so hub ammo = 1.0."""
    raw = {}
    for a, (rounds, item) in rounds_per_trade.items():
        item_val = ITEM_VALUE.get(item, 1.0)
        raw[a] = item_val / rounds
    base = raw.get(HUB, 1.0)
    return {a: v / base for a, v in raw.items()}


def find_optimal_lot(va: float, vb: float, min_eff: float = 0.95, max_eff: float = 0.99, max_give: int = 35) -> tuple[int, int, float]:
    """
    Finds the integer lot (give, get) with minimal total items (give + get)
    whose efficiency (get * vb) / (give * va) is in [min_eff, max_eff].
    """
    candidates = []
    for give in range(1, max_give + 1):
        for get in range(1, 45):
            eff = (get * vb) / (give * va)
            if min_eff <= eff <= max_eff:
                candidates.append((give + get, -eff, give, get, eff))

    if not candidates:
        # Fallback if no exact match in [min_eff, max_eff]: take highest eff < 1.0
        for give in range(1, max_give + 1):
            get = int(max_eff * give * va / vb)
            if get >= 1:
                eff = (get * vb) / (give * va)
                if eff < 1.0:
                    candidates.append((give + get, -eff, give, get, eff))

    if not candidates:
        raise ValueError(f"No valid lot with give <= {max_give}")

    candidates.sort()
    _, _, give, get, eff = candidates[0]
    return give, get, eff


def best_cycle_product(nodes, edges) -> tuple[float, list[str]]:
    """Max product of rates over any cycle. Uses Floyd-Warshall on log-rates."""
    idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    NEG = -math.inf
    dist = [[NEG] * n for _ in range(n)]
    nxt = [[None] * n for _ in range(n)]
    for (a, b), (give, get, _) in edges.items():
        i, j = idx[a], idx[b]
        w = math.log(get / give)
        if w > dist[i][j]:
            dist[i][j] = w
            nxt[i][j] = j
    for k, i, j in itertools.product(range(n), repeat=3):
        if dist[i][k] > NEG and dist[k][j] > NEG and dist[i][k] + dist[k][j] > dist[i][j] + 1e-12:
            dist[i][j] = dist[i][k] + dist[k][j]
            nxt[i][j] = nxt[i][k]
    best_i = max(range(n), key=lambda i: dist[i][i])
    if dist[best_i][best_i] == NEG:
        return 0.0, []
    path, cur = [nodes[best_i]], nxt[best_i][best_i]
    for _ in range(n + 1):
        path.append(nodes[cur])
        if cur == best_i:
            break
        cur = nxt[cur][best_i]
    return math.exp(dist[best_i][best_i]), path


def later_flag(a: str, b: str, world_flags: dict[str, str]) -> str:
    flag_a = world_flags.get(a, FLAG_ORDER[0])
    flag_b = world_flags.get(b, FLAG_ORDER[0])
    idx_a = FLAG_ORDER.index(flag_a) if flag_a in FLAG_ORDER else 0
    idx_b = FLAG_ORDER.index(flag_b) if flag_b in FLAG_ORDER else 0
    return FLAG_ORDER[max(idx_a, idx_b)]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uasset", default=DEFAULT_UASSET_PATH, help="path to trader_MyProject.uasset")
    ap.add_argument("--mode", choices=["cycle", "hub", "full"], default="cycle",
                    help="cycle = 5 circular trades (14 total, fills 2x7 UI perfectly; default); hub = 8 trades via 9mm; full = 20 trades")
    ap.add_argument("--min-eff", type=float, default=0.95, help="minimum value kept per trade (default 0.95 = 95%%)")
    ap.add_argument("--max-eff", type=float, default=0.99, help="maximum value kept per trade (default 0.99 = 99%%)")
    ap.add_argument("--max-give", type=int, default=35, help="max rounds player gives in one trade (default: 35)")
    ap.add_argument("--stock", type=int, default=5, help="AvailableStock for each exchange row (default: 5)")
    ap.add_argument("--start-index", type=int, default=9, help="starting array index for new trades (default: 9)")
    ap.add_argument("--apply", action="store_true", help="automatically patch trader_MyProject.uasset with generated trades")
    ap.add_argument("--restore", action="store_true", help="restore trader_MyProject.uasset from backup")
    ap.add_argument("--verify", action="store_true", help="verify current trades inside trader_MyProject.uasset")
    args = ap.parse_args()

    if args.restore:
        patch_uasset_trades.restore_backup(Path(args.uasset))
        patch_uasset_trades.print_trades(Path(args.uasset))
        return

    if args.verify:
        patch_uasset_trades.print_trades(Path(args.uasset))
        return

    rounds_per_trade, world_flags, source, all_trades = get_base_ammo_data(args.uasset)
    nodes = list(rounds_per_trade.keys())
    values = compute_ammo_values(rounds_per_trade)

    if args.mode == "cycle":
        pairs = CYCLE_PAIRS
    elif args.mode == "full":
        pairs = [(a, b) for a in nodes for b in nodes if a != b]
    else:  # hub
        pairs = [(a, HUB) for a in nodes if a != HUB] + [(HUB, b) for b in nodes if b != HUB]

    edges = {}
    for a, b in pairs:
        edges[(a, b)] = find_optimal_lot(values[a], values[b], args.min_eff, args.max_eff, args.max_give)

    product, cycle = best_cycle_product(nodes, edges)

    print("================================================================================")
    print("                    ABIOTIC FACTOR AMMO EXCHANGE GENERATOR")
    print("================================================================================")
    print(f"Data source: {source}")
    print(f"Mode: {args.mode.upper()} ({len(pairs)} exchange trades; Total trades: {9 + len(pairs)})")
    if args.mode == "cycle":
        print(f"UI Layout: Exactly 14 items (Column 0: 7 rows, Column 1: 7 rows) -> ZERO UI OVERFLOW!")
    print(f"Value Retention Target: {args.min_eff:.1%} to {args.max_eff:.1%} (Fee: {(1-args.max_eff):.1%} to {(1-args.min_eff):.1%})")
    print(f"Max Give Bound: {args.max_give} | Default Stock: {args.stock}")

    print("\n[Base Ammo Valuation (Hub 9mm = 1.00)]:")
    for a in nodes:
        cnt, mat = rounds_per_trade[a]
        print(f"  {a:<14} : {values[a]:6.3f} val/round  ({cnt:2d} rounds per 1 {mat})")

    print("\n[Exchange Trades to Add]:")
    print(f"Target Asset: Content/DataTables/DT_NPC_TraderItems/trader_MyProject.uasset")
    print("-" * 115)
    print(f"{'Idx':<5} | {'Shop Slot':<12} | {'Buyable Items (Output)':<24} {'Qty':<5} {'Stock':<6} {'World Flag':<25} | {'Tradeable Items (Cost)':<22} {'Qty':<5} | {'Value Kept':<10}")
    print("-" * 115)

    cur_idx = args.start_index
    trades_to_patch = []
    for (a, b), (give, get, eff) in edges.items():
        flag = later_flag(a, b, world_flags)
        grid_col = cur_idx // 7
        grid_row = cur_idx % 7
        slot_str = f"Col {grid_col}, Row {grid_row}"
        print(f"[{cur_idx:2d}]  | {slot_str:<12} | {b:<24} {get:<5} {args.stock:<6} {flag:<25} | {a:<22} {give:<5} | {eff:6.2%}")
        trades_to_patch.append({
            'out_item': b,
            'out_count': get,
            'cost_item': a,
            'cost_count': give,
            'stock': args.stock,
            'flag': flag,
        })
        cur_idx += 1
    print("-" * 115)

    print("\n[Arbitrage Mathematical Verification]:")
    if cycle:
        print(f"  Cycle analyzed:        {' -> '.join(c.replace('ammo_', '') for c in cycle)}")
        print(f"  Rate product:          {product:.4f} ({product:.2%} return per full round trip)")
    if product >= 1.0:
        print("  [ERROR]: Arbitrage cycle detected!")
    else:
        print("  [PASS]: No arbitrage possible. Every circular path strictly destroys value.")

    if args.apply:
        print("\n[Applying Patch to uasset...]")
        patch_uasset_trades.apply_patch(trades_to_patch, Path(args.uasset))
        print("\n[Verifying Patched Asset]:")
        patch_uasset_trades.print_trades(Path(args.uasset))
    else:
        print("\n[Status]: Asset not modified. Run with '--apply' to automatically patch trader_MyProject.uasset!")


if __name__ == "__main__":
    main()
