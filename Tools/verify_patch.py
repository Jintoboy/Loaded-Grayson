import struct

def verify_patched_asset(path):
    with open(path, 'rb') as f:
        d = f.read()

    print(f"Verifying {path} (size: {len(d)}):")
    
    # 1. Names
    pos = 390
    name_count = 55
    names = []
    for i in range(name_count):
        str_len, = struct.unpack_from('<i', d, pos)
        pos += 4
        if str_len > 0:
            s = d[pos:pos+str_len-1].decode('utf-8', errors='replace')
            pos += str_len
        elif str_len < 0:
            s = d[pos:pos+(-str_len*2)-2].decode('utf-16le', errors='replace')
            pos += -str_len*2
        else:
            s = ""
        pos += 4
        names.append(s)

    def fname(idx, num):
        s = names[idx]
        if num > 0:
            return f"{s}_{num-1}"
        return s

    # 2. Header offsets
    bulk_offset, = struct.unpack_from('<q', d, 350)
    footer_offset, = struct.unpack_from('<q', d, 378)
    print(f"Header: BulkDataStartOffset = {bulk_offset}, FooterOffset = {footer_offset}")
    
    # Check that PACKAGE_FILE_TAG is at bulk_offset
    tag, = struct.unpack_from('<I', d, bulk_offset)
    assert tag == 0x9e2a83c1, f"Expected PACKAGE_FILE_TAG at {bulk_offset}, got {hex(tag)}"
    print(f"Verified PACKAGE_FILE_TAG at bulk_offset ({bulk_offset})")
    
    # Check end of file tag
    end_tag, = struct.unpack_from('<I', d, len(d) - 4)
    assert end_tag == 0x9e2a83c1, f"Expected end tag at {len(d)-4}, got {hex(end_tag)}"
    print(f"Verified PACKAGE_FILE_TAG at end of file ({len(d)-4})")

    # 3. Export table
    serial_size, = struct.unpack_from('<q', d, 1980)
    serial_offset, = struct.unpack_from('<q', d, 1988)
    print(f"Export 2: SerialOffset = {serial_offset}, SerialSize = {serial_size}, End = {serial_offset + serial_size}")
    assert serial_offset + serial_size == bulk_offset, f"Export end ({serial_offset + serial_size}) != bulk_offset ({bulk_offset})"
    print(f"Verified Export 2 fits exactly before bulk data!")

    # Verify ScriptSerializationEndOffset
    script_end_offset, = struct.unpack_from('<q', d, 2056)
    print(f"Export 2: ScriptSerializationEndOffset = {script_end_offset}")
    assert script_end_offset == serial_size - 4, f"ScriptSerializationEndOffset ({script_end_offset}) != serial_size - 4 ({serial_size - 4})"
    print(f"Verified ScriptSerializationEndOffset matches SerialSize - 4!")

    # 4. Row struct
    row_size, = struct.unpack_from('<i', d, 2567)
    print(f"Row struct size: {row_size}")

    # 5. BuyableItems
    buyable_size, = struct.unpack_from('<i', d, 2628)
    buyable_count, = struct.unpack_from('<i', d, 2633)
    print(f"BuyableItems: size = {buyable_size}, count = {buyable_count}")
    assert buyable_size == 4 + buyable_count * 311, f"Expected {4 + buyable_count*311}, got {buyable_size}"

    # 6. TradeableItems
    tradeable_tag_pos = 2637 + buyable_count * 311
    tr_name_idx, tr_name_num = struct.unpack_from('<ii', d, tradeable_tag_pos)
    assert fname(tr_name_idx, tr_name_num) == 'TradeableItems', f"Expected TradeableItems tag at {tradeable_tag_pos}, got {fname(tr_name_idx, tr_name_num)}"
    
    # Within TradeableItems tag, size is at +56, count is at +61, elements start at +65
    tradeable_size, = struct.unpack_from('<i', d, tradeable_tag_pos + 56)
    tradeable_count, = struct.unpack_from('<i', d, tradeable_tag_pos + 61)
    print(f"TradeableItems: size = {tradeable_size}, count = {tradeable_count}")
    assert tradeable_count == buyable_count, f"Count mismatch: {buyable_count} vs {tradeable_count}"
    assert tradeable_size == 4 + tradeable_count * 127, f"Expected {4 + tradeable_count*127}, got {tradeable_size}"

    # 7. Verify RowName and bOverrideExistingRow
    row_end = tradeable_tag_pos + 65 + buyable_count * 127
    none_idx, none_num = struct.unpack_from('<ii', d, row_end)
    assert fname(none_idx, none_num) == 'None', f"Expected None at {row_end}, got {fname(none_idx, none_num)}"
    
    rowname_pos = row_end + 8
    rn_idx, rn_num = struct.unpack_from('<ii', d, rowname_pos)
    assert fname(rn_idx, rn_num) == 'RowName', f"Expected RowName at {rowname_pos}, got {fname(rn_idx, rn_num)}"
    rn_val_idx, rn_val_num = struct.unpack_from('<ii', d, rowname_pos + 25)
    assert fname(rn_val_idx, rn_val_num) == 'trader_grayson', f"Expected trader_grayson at {rowname_pos + 25}, got {fname(rn_val_idx, rn_val_num)}"

    override_pos = rowname_pos + 33
    ov_idx, ov_num = struct.unpack_from('<ii', d, override_pos)
    assert fname(ov_idx, ov_num) == 'bOverrideExistingRow', f"Expected bOverrideExistingRow at {override_pos}, got {fname(ov_idx, ov_num)}"
    
    # 8. Print all trades
    print(f"\n--- All {buyable_count} Parsed Trades ---")
    for i in range(buyable_count):
        b = d[2637 + i*311 : 2637 + (i+1)*311]
        out_idx, out_num = struct.unpack_from('<ii', b, 131)
        out_count, = struct.unpack_from('<i', b, 172)
        flag_idx, flag_num = struct.unpack_from('<ii', b, 258)
        stock, = struct.unpack_from('<i', b, 299)
        
        tb = d[tradeable_tag_pos + 65 + i*127 : tradeable_tag_pos + 65 + (i+1)*127]
        cost_idx, cost_num = struct.unpack_from('<ii', tb, 74)
        cost_count, = struct.unpack_from('<i', tb, 115)
        
        print(f"Trade [{i:2d}]: {fname(out_idx, out_num):24s} x{out_count:3d} (stock {stock:2d}, flag {fname(flag_idx, flag_num):24s})  <=>  {fname(cost_idx, cost_num):15s} x{cost_count:3d}")

import sys
from pathlib import Path

DEFAULT_ASSET = Path(__file__).resolve().parent.parent / "MyProjecty8BQn" / "Content" / "DataTables" / "DT_NPC_TraderItems" / "trader_MyProject.uasset"

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_ASSET)
    verify_patched_asset(path)
