"""Parse an Android btsnoop_hci.log and print all ATT Write PDUs (the app's
commands to the LED controller), with handle, value bytes, and timestamp."""
import struct
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "btsnoop_hci.log"

with open(PATH, "rb") as f:
    data = f.read()

# --- btsnoop header ---
assert data[:8] == b"btsnoop\x00", "not a btsnoop file"
version, datalink = struct.unpack(">II", data[8:16])
off = 16

ATT_OPS = {0x12: "Write Request", 0x52: "Write Command",
           0x1B: "Handle Value Notification", 0x1D: "Handle Value Indication",
           0x0A: "Read Request", 0x0B: "Read Response"}

rows = []
while off + 24 <= len(data):
    orig_len, incl_len, flags, drops, ts = struct.unpack(">IIIIq", data[off:off+24])
    off += 24
    pkt = data[off:off+incl_len]
    off += incl_len
    if not pkt:
        continue

    # datalink 1002 = HCI UART (H4): first byte is the packet-type indicator
    h4 = pkt[0]
    body = pkt[1:]
    if h4 != 0x02:          # 0x02 = ACL data; ATT rides on ACL
        continue
    if len(body) < 8:
        continue
    handle_pb, acl_len = struct.unpack("<HH", body[:4])
    l2cap = body[4:4+acl_len]
    if len(l2cap) < 4:
        continue
    l2_len, cid = struct.unpack("<HH", l2cap[:4])
    if cid != 0x0004:        # 0x0004 = ATT
        continue
    att = l2cap[4:4+l2_len]
    if not att:
        continue
    opcode = att[0]
    if opcode not in ATT_OPS:
        continue
    direction = "TX(app->dev)" if (flags & 0x01) == 0 else "RX(dev->app)"
    if opcode in (0x12, 0x52):          # write: handle(2) + value
        if len(att) < 3:
            continue
        val_handle = struct.unpack("<H", att[1:3])[0]
        value = att[3:]
        rows.append((ts, direction, ATT_OPS[opcode], val_handle, value.hex()))
    elif opcode in (0x1B, 0x1D):        # notification/indication: handle(2)+value
        if len(att) < 3:
            continue
        val_handle = struct.unpack("<H", att[1:3])[0]
        value = att[3:]
        rows.append((ts, direction, ATT_OPS[opcode], val_handle, value.hex()))

print(f"btsnoop v{version} datalink={datalink}  total ATT pkts: {len(rows)}\n")
t0 = rows[0][0] if rows else 0
for ts, d, op, h, v in rows:
    dt = (ts - t0) / 1e6
    print(f"+{dt:7.2f}s  {d:<13} {op:<26} handle=0x{h:04x}  value={v}")
