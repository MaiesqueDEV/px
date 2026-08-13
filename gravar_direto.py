import argparse
import csv
import os
import struct
import sys
import time
import datetime

# Quansheng UV-K5 Custom Firmware (F4HWN / Fusion) Direct Memory Programmer
# Written by Antigravity IDE

# XOR Table used by Quansheng protocol
_OBFUS_TBL = b"\x16\x6c\x14\xe6\x2e\x91\x0d\x40\x21\x35\xd5\x40\x13\x03\xe9\x80"

# Tone configuration options from dcs.c
CTCSS_TONES = [
     67.0,  69.3,  71.9,  74.4,  77.0,  79.7,  82.5,  85.4,  88.5,  91.5,
     94.8,  97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3,
    131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9,
    171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 189.9, 192.8, 196.6, 199.5,
    203.5, 206.5, 210.7, 218.1, 225.7, 229.1, 233.6, 241.8, 250.3, 254.1
]

DCS_CODES = [
    0x0013, 0x0015, 0x0016, 0x0019, 0x001A, 0x001E, 0x0023, 0x0027,
    0x0029, 0x002B, 0x002C, 0x0035, 0x0039, 0x003A, 0x003B, 0x003C,
    0x004C, 0x004D, 0x004E, 0x0052, 0x0055, 0x0059, 0x005A, 0x005C,
    0x0063, 0x0065, 0x006A, 0x006D, 0x006E, 0x0072, 0x0075, 0x007A,
    0x007C, 0x0085, 0x008A, 0x0093, 0x0095, 0x0096, 0x00A3, 0x00A4,
    0x00A5, 0x00A6, 0x00A9, 0x00AA, 0x00AD, 0x00B1, 0x00B3, 0x00B5,
    0x00B6, 0x00B9, 0x00BC, 0x00C6, 0x00C9, 0x00CD, 0x00D5, 0x00D9,
    0x00DA, 0x00E3, 0x00E6, 0x00E9, 0x00EE, 0x00F4, 0x00F5, 0x00F9,
    0x0109, 0x010A, 0x010B, 0x0113, 0x0119, 0x011A, 0x0125, 0x0126,
    0x012A, 0x012C, 0x012D, 0x0132, 0x0134, 0x0135, 0x0136, 0x0143,
    0x0146, 0x014E, 0x0153, 0x0156, 0x015A, 0x0166, 0x0175, 0x0186,
    0x018A, 0x0194, 0x0197, 0x0199, 0x019A, 0x01AC, 0x01B2, 0x01B4,
    0x01C3, 0x01CA, 0x01D3, 0x01D9, 0x01DA, 0x01DC, 0x01E3, 0x01EC
]

def calc_crc(buf: bytes, size: int) -> int:
    crc = 0
    for i in range(size):
        b = buf[i]
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return crc

def make_packet(msg_type: int, payload: bytes) -> bytes:
    msg = bytearray(4 + len(payload))
    struct.pack_into("<HH", msg, 0, msg_type, len(payload))
    msg[4:] = payload

    msg_len = len(msg)
    if msg_len % 2 != 0:
        msg.append(0)
        msg_len += 1

    pkt = bytearray(8 + msg_len)
    struct.pack_into("<H", pkt, 0, 0xCDAB)
    struct.pack_into("<H", pkt, 2, msg_len)
    struct.pack_into("<H", pkt, 6 + msg_len, 0xBADC)
    pkt[4:4+len(msg)] = msg

    crc = calc_crc(pkt[4:4+msg_len], msg_len)
    struct.pack_into("<H", pkt, 4+msg_len, crc)

    for i in range(msg_len + 2):
        pkt[4 + i] ^= _OBFUS_TBL[i % len(_OBFUS_TBL)]

    return bytes(pkt)

def deobfus(buf: bytearray, off: int, size: int):
    for i in range(size):
        buf[off + i] ^= _OBFUS_TBL[i % len(_OBFUS_TBL)]

def parse_packet(buf: bytearray) -> tuple[int, bytes] | None:
    if len(buf) < 8:
        return None
    
    start = buf.find(b"\xab\xcd")
    if start == -1:
        if buf.endswith(b"\xab"):
            del buf[:-1]
        else:
            del buf[:]
        return None
        
    if len(buf) - start < 8:
        return None
        
    msg_len = struct.unpack_from("<H", buf, start + 2)[0]
    end_offset = start + 6 + msg_len
    
    if len(buf) < end_offset + 2:
        return None
        
    if buf[end_offset:end_offset+2] != b"\xdc\xba":
        del buf[:start + 2]
        return None
        
    pkt_part = bytearray(buf[start+4 : end_offset])
    deobfus(pkt_part, 0, len(pkt_part))
    
    msg_type, payload_len = struct.unpack_from("<HH", pkt_part, 0)
    payload = bytes(pkt_part[4 : 4 + payload_len])
    
    del buf[:end_offset + 2]
    return msg_type, payload

def get_band(freq_hz):
    freq_mhz = freq_hz / 1e6
    if freq_mhz < 108.0:
        return 0  # BAND1_50MHz
    elif freq_mhz < 137.0:
        return 1  # BAND2_108MHz
    elif freq_mhz < 174.0:
        return 2  # BAND3_137MHz
    elif freq_mhz < 350.0:
        return 3  # BAND4_174MHz
    elif freq_mhz < 400.0:
        return 4  # BAND5_350MHz
    elif freq_mhz < 470.0:
        return 5  # BAND6_400MHz
    else:
        return 6  # BAND7_470MHz

def get_tone_info(tone_mode: str, r_freq_str: str, c_freq_str: str, dcs_code_str: str):
    tone_mode = tone_mode.strip().upper()
    if not tone_mode or tone_mode in ("OFF", "NONE"):
        return 0, 0, 0, 0  # CodeTypeRX, CodeTypeTX, CodeRX, CodeTX
    
    # 0 = OFF, 1 = CTCSS, 2 = DCS
    if tone_mode == "TONE":
        # Transmit CTCSS enabled, receive none
        try:
            val = float(r_freq_str)
            tx_code = CTCSS_TONES.index(val)
            return 0, 1, 0, tx_code
        except ValueError:
            return 0, 0, 0, 0
    elif tone_mode == "TSQL":
        # Transmit & Receive CTCSS enabled
        try:
            val = float(c_freq_str if c_freq_str else r_freq_str)
            code = CTCSS_TONES.index(val)
            return 1, 1, code, code
        except ValueError:
            return 0, 0, 0, 0
    elif tone_mode == "DTCS":
        # Transmit & Receive DCS enabled
        try:
            # Parse octal DCS string to hex-int
            val = int(dcs_code_str, 8)
            code = DCS_CODES.index(val)
            return 2, 2, code, code
        except ValueError:
            return 0, 0, 0, 0
            
    return 0, 0, 0, 0

def get_step_code(step_str: str):
    try:
        val = float(step_str.lower().replace("khz", "").replace("k", ""))
    except ValueError:
        return 1  # default 5kHz
    step_map = {
        2.5: 0,
        5.0: 1,
        5: 1,
        6.25: 2,
        10.0: 3,
        10: 3,
        12.5: 4,
        25.0: 5,
        25: 5,
        8.33: 6
    }
    return step_map.get(val, 1)

def get_power_code(power_str: str):
    power_str = power_str.strip().lower()
    power_map = {
        "20mw": 0, "0": 0,
        "125mw": 1, "1": 1,
        "250mw": 2, "2": 2,
        "500mw": 3, "3": 3,
        "1w": 4, "1.0w": 4, "4": 4,
        "2w": 5, "2.0w": 5, "5": 5,
        "5w": 6, "5.0w": 6, "6": 6
    }
    return power_map.get(power_str, 6) # Default to High (5W)

def parse_csv_channels(csv_path: str):
    vfo_blocks = []
    name_blocks = []
    attributes = [0xFFFF] * 256 # 256 attribute slots

    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            loc = int(row["Location"])
            idx = loc - 1
            if idx < 0 or idx >= 256:
                continue
            
            # Frequencies
            freq_hz = int(float(row["Frequency"]) * 1e6)
            freq_units = int(freq_hz / 10)
            
            # Duplex & Offset
            duplex = row["Duplex"].strip()
            offset_hz = int(float(row["Offset"]) * 1e6) if row["Offset"] else 0
            offset_units = int(offset_hz / 10)
            offset_dir = 0
            if duplex == "+":
                offset_dir = 1
            elif duplex == "-":
                offset_dir = 2
                
            # Tone settings
            rx_ctype, tx_ctype, rx_code, tx_code = get_tone_info(
                row.get("Tone", ""),
                row.get("rToneFreq", ""),
                row.get("cToneFreq", ""),
                row.get("DtcsCode", "")
            )
            
            # Mode / Modulation
            mode = row.get("Mode", "FM").strip().upper()
            mod_code = 0
            if mode == "AM":
                mod_code = 1
            elif mode == "USB":
                mod_code = 2
                
            # Power
            power = get_power_code(row.get("Power", "5.0W"))
            
            # Step
            step = get_step_code(row.get("TStep", "5.00"))
            
            # Pack VFO structure (16 bytes)
            vfo_data = bytearray(16)
            struct.pack_into("<IIBBBBBBBB", vfo_data, 0,
                freq_units,                # 0..3: RX frequency
                offset_units,              # 4..7: TX offset
                rx_code,                   # 8: RX code
                tx_code,                   # 9: TX code
                (tx_ctype << 4) | rx_ctype,# 10: Code type
                (mod_code << 4) | offset_dir,# 11: Modulation & direction
                (power << 2),              # 12: Power level (bits 2..4)
                0,                         # 13: DTMF/PTT
                step,                      # 14: Step frequency
                0                          # 15: Scrambling type
            )
            vfo_blocks.append((idx * 16, bytes(vfo_data)))
            
            # Pack Name structure (16 bytes)
            name = row.get("Name", "")[:10]
            name_bytes = name.encode("ascii", errors="ignore").ljust(16, b"\x00")
            name_blocks.append((0x4000 + idx * 16, name_bytes))
            
            # Attributes (2 bytes)
            band = get_band(freq_hz)
            scanlist = 1 # list 1
            # attribute struct: band (3 bits), compander (2 bits), unused (3 bits), scanlist (8 bits)
            attr_val = (band & 0x7) | ((scanlist & 0xFF) << 8)
            attributes[idx] = attr_val

    # Group attributes into 16-byte blocks (attributes for 8 channels per block)
    attr_blocks = []
    for block_idx in range(0, 32): # Write attributes for first 256 channels (32 blocks of 8 channels)
        block_addr = 0x8000 + block_idx * 16
        block_data = bytearray(16)
        for i in range(8):
            struct.pack_into("<H", block_data, i * 2, attributes[block_idx * 8 + i])
        attr_blocks.append((block_addr, bytes(block_data)))

    return vfo_blocks, name_blocks, attr_blocks

def main():
    parser = argparse.ArgumentParser(description="Programar Quansheng UV-K5 F4HWN/Fusion diretamente")
    parser.add_argument("--csv", required=True, help="Caminho do CSV de canais")
    parser.add_argument("--port", required=True, help="Porta COM (ex: COM7)")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"Erro: Arquivo CSV {args.csv} nao encontrado.")
        sys.exit(1)

    print("Parseando canais do CSV...")
    vfo_blocks, name_blocks, attr_blocks = parse_csv_channels(args.csv)
    print(f"Carregados {len(vfo_blocks)} canais com sucesso.")

    import serial
    print(f"Abrindo porta {args.port} a 38400 baud...")
    try:
        ser = serial.Serial(args.port, baudrate=38400, timeout=0.1)
    except Exception as e:
        print(f"Erro ao abrir porta: {e}")
        sys.exit(1)

    # Handshake
    print("Enviando sinal de conexao para o radio...")
    ts = int(time.time()) & 0xFFFFFFFF
    pkt = make_packet(0x0514, struct.pack("<I", ts))
    ser.write(pkt)
    ser.flush()

    # Wait for response
    rx_buf = bytearray()
    connected = False
    start_time = time.time()
    while time.time() - start_time < 3.0:
        data = ser.read(100)
        if data:
            rx_buf.extend(data)
            res = parse_packet(rx_buf)
            if res:
                msg_type, payload = res
                if msg_type == 0x0515:
                    print("Conectado ao Quansheng!")
                    # Check version
                    end = payload.find(b"\x00", 4, 20)
                    ver = payload[4:end].decode("ascii", errors="ignore")
                    print(f"Versao do Radio: {ver}")
                    connected = True
                    break
        time.sleep(0.01)

    if not connected:
        print("Erro: Nao recebeu resposta do radio. Certifique-se de que o cabo esta conectado e o radio esta LIGADO.")
        ser.close()
        sys.exit(1)

    # Write all data blocks
    all_blocks = vfo_blocks + name_blocks + attr_blocks
    total_blocks = len(all_blocks)
    print(f"Gravando {total_blocks} blocos de memoria...")

    for count, (addr, data) in enumerate(all_blocks, 1):
        # Format 0x051D message
        # bytes 0..3: msg header
        # payload bytes 0..1: offset
        # payload bytes 2..3: size (16)
        # payload byte 4: allow password (1)
        # payload bytes 4..7: timestamp
        # payload bytes 8..24: 16 bytes data
        payload = bytearray(28)
        struct.pack_into("<HHBI", payload, 0, addr, 16, 1, ts)
        payload[8:24] = data
        pkt = make_packet(0x051D, payload)

        success = False
        for attempt in range(3):
            ser.write(pkt)
            ser.flush()

            # Wait for write ack 0x051E
            rx_buf = bytearray()
            ack_received = False
            write_start = time.time()
            while time.time() - write_start < 0.5:
                res_data = ser.read(100)
                if res_data:
                    rx_buf.extend(res_data)
                    res = parse_packet(rx_buf)
                    if res:
                        msg_type, payload_ack = res
                        if msg_type == 0x051E:
                            ack_addr = struct.unpack_from("<H", payload_ack, 0)[0]
                            if ack_addr == addr:
                                ack_received = True
                                break
                time.sleep(0.01)

            if ack_received:
                success = True
                break
            else:
                print(f"Tentativa {attempt+1} falhou para endereco 0x{addr:04X}, tentando novamente...")
                time.sleep(0.1)

        if not success:
            print(f"Erro grave: Falha ao gravar no endereco 0x{addr:04X}. Abortando.")
            ser.close()
            sys.exit(1)

        # Print progress
        pct = (count * 100) // total_blocks
        print(f"Gravando: {pct}% completo ({count}/{total_blocks} blocos)", end="\r")

    print("\nGravacao finalizada com sucesso!")
    print("Reiniciando o radio...")
    reboot_pkt = make_packet(0x05DD, b"")
    ser.write(reboot_pkt)
    ser.flush()
    ser.close()
    print("Pronto! Os canais foram atualizados.")

if __name__ == "__main__":
    main()
