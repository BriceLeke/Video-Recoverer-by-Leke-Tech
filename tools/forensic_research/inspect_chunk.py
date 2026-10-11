with open('samples/corrupted/original.mp4', 'rb') as f:
    f.seek(0x12051)
    chunk = f.read(0x1321B - 0x12051)
    print(f"Chunk size: {len(chunk)} bytes")
    print("First 64 bytes:", chunk[:64].hex())
    print("Last 64 bytes:", chunk[-64:].hex())
