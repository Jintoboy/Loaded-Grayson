"""
patch_uasset_trades.py

Automated binary patcher for UE5 NPCTraderItemModRowAsset (trader_MyProject.uasset).
Allows appending new trades to BuyableItems and TradeableItems without requiring manual
Unreal Editor clickops, ensuring complete header/export/array offset consistency.
"""

import os
import shutil
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = REPO_ROOT / "MyProjecty8BQn"
DEFAULT_ASSET_PATH = PROJECT_ROOT / "Content" / "DataTables" / "DT_NPC_TraderItems" / "trader_MyProject.uasset"
BACKUP_PATH = REPO_ROOT / "Backups" / "trader_MyProject.uasset.bak"

FNAME_MAP = {
    'ammo_9mm': (5, 0),
    'ammo_12g': (4, 0),
    'ammo_Magnum': (6, 0),
    'ammo_308': (3, 309),
    'ammo_556': (3, 557),
    'Manufacturing_Arrived': (29, 0),
    'Labs_Containment_Entered': (27, 0),
    'Dams_ReachedCentral': (19, 0),
}

def load_names(data):
    name_count, = struct.unpack_from('<i', data, 143)
    name_offset, = struct.unpack_from('<i', data, 147)
    pos = name_offset
    names = []
    for _ in range(name_count):
        str_len, = struct.unpack_from('<i', data, pos)
        pos += 4
        if str_len > 0:
            s = data[pos:pos+str_len-1].decode('utf-8', errors='replace')
            pos += str_len
        elif str_len < 0:
            s = data[pos:pos+(-str_len*2)-2].decode('utf-16le', errors='replace')
            pos += -str_len*2
        else:
            s = ""
        pos += 4
        names.append(s)
    return names

def parse_trades(asset_path=DEFAULT_ASSET_PATH):
    with open(asset_path, 'rb') as f:
        d = f.read()
    names = load_names(d)

    def fname(idx, num):
        if idx < 0 or idx >= len(names):
            return f"UNKNOWN({idx})"
        s = names[idx]
        return f"{s}_{num-1}" if num > 0 else s

    buyable_count, = struct.unpack_from('<i', d, 2633)
    tradeable_tag_pos = 2637 + buyable_count * 311
    tradeable_count, = struct.unpack_from('<i', d, tradeable_tag_pos + 61)

    trades = []
    for i in range(buyable_count):
        b = d[2637 + i*311 : 2637 + (i+1)*311]
        out_idx, out_num = struct.unpack_from('<ii', b, 131)
        out_count, = struct.unpack_from('<i', b, 172)
        flag_idx, flag_num = struct.unpack_from('<ii', b, 258)
        stock, = struct.unpack_from('<i', b, 299)

        tb = d[tradeable_tag_pos + 65 + i*127 : tradeable_tag_pos + 65 + (i+1)*127]
        cost_idx, cost_num = struct.unpack_from('<ii', tb, 74)
        cost_count, = struct.unpack_from('<i', tb, 115)

        trades.append({
            'index': i,
            'out_item': fname(out_idx, out_num),
            'out_count': out_count,
            'cost_item': fname(cost_idx, cost_num),
            'cost_count': cost_count,
            'stock': stock,
            'flag': fname(flag_idx, flag_num),
        })
    return trades

def print_trades(asset_path=DEFAULT_ASSET_PATH):
    trades = parse_trades(asset_path)
    print(f"\n--- Current Trades in {asset_path.name} (Total: {len(trades)}) ---")
    for t in trades:
        print(f"[{t['index']:2d}] {t['out_item']:24s} x{t['out_count']:3d} (stock {t['stock']:2d}, flag {t['flag']:24s})  <=>  {t['cost_item']:15s} x{t['cost_count']:3d}")

def apply_patch(new_trades, asset_path=DEFAULT_ASSET_PATH, backup_path=BACKUP_PATH):
    # Ensure backup exists from vanilla/original template
    if not backup_path.exists():
        shutil.copyfile(asset_path, backup_path)
        print(f"Created backup at {backup_path}")

    # Always base the patch from the clean 9-trade backup or reset point
    with open(backup_path, 'rb') as f:
        d = bytearray(f.read())

    orig_len = len(d)
    assert orig_len == 6774, f"Expected 6774-byte base asset, got {orig_len}"

    buyable_template = bytes(d[2637 : 2637 + 311])
    tradeable_template = bytes(d[5501 : 5501 + 127])

    num_new = len(new_trades)
    added_buyable_bytes = num_new * 311
    added_tradeable_bytes = num_new * 127
    total_added_bytes = added_buyable_bytes + added_tradeable_bytes

    new_buyable_elements = bytearray()
    new_tradeable_elements = bytearray()

    for t in new_trades:
        be = bytearray(buyable_template)
        out_item_idx, out_item_num = FNAME_MAP[t['out_item']]
        struct.pack_into('<ii', be, 131, out_item_idx, out_item_num)
        struct.pack_into('<i', be, 172, t['out_count'])
        flag_idx, flag_num = FNAME_MAP[t['flag']]
        struct.pack_into('<ii', be, 258, flag_idx, flag_num)
        struct.pack_into('<i', be, 299, t['stock'])
        new_buyable_elements.extend(be)

        te = bytearray(tradeable_template)
        cost_item_idx, cost_item_num = FNAME_MAP[t['cost_item']]
        struct.pack_into('<ii', te, 74, cost_item_idx, cost_item_num)
        struct.pack_into('<i', te, 115, t['cost_count'])
        new_tradeable_elements.extend(te)

    # Update summary and headers
    struct.pack_into('<q', d, 350, 6722 + total_added_bytes)
    struct.pack_into('<q', d, 378, 6726 + total_added_bytes)
    struct.pack_into('<q', d, 1980, 4200 + total_added_bytes)
    struct.pack_into('<q', d, 2056, 4196 + total_added_bytes)  # ScriptSerializationEndOffset
    struct.pack_into('<i', d, 2567, 4080 + total_added_bytes)
    struct.pack_into('<i', d, 2628, 2803 + added_buyable_bytes)
    struct.pack_into('<i', d, 2633, 9 + num_new)

    part1 = d[:5436]

    struct.pack_into('<i', d, 5492, 1147 + added_tradeable_bytes)
    struct.pack_into('<i', d, 5497, 9 + num_new)

    part2 = d[5436:6644]
    part3 = d[6644:]

    final_data = part1 + new_buyable_elements + part2 + new_tradeable_elements + part3

    with open(asset_path, 'wb') as f:
        f.write(final_data)

    print(f"Patched {asset_path} successfully (+{total_added_bytes} bytes, total {len(final_data)} bytes).")

def restore_backup(asset_path=DEFAULT_ASSET_PATH, backup_path=BACKUP_PATH):
    if not backup_path.exists():
        print(f"No backup found at {backup_path}")
        return False
    shutil.copyfile(backup_path, asset_path)
    print(f"Restored {asset_path} from {backup_path}")
    return True

if __name__ == '__main__':
    if '--restore' in sys.argv:
        restore_backup()
    elif '--status' in sys.argv or '--verify' in sys.argv:
        print_trades()
    else:
        print("Usage: python patch_uasset_trades.py [--status | --restore]")
