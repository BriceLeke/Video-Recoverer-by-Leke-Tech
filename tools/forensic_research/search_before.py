with open('samples/corrupted/original.mp4', 'rb') as f:
    f.seek(0)
    data = f.read(0x1321B + 10)

print(f"Total bytes read: {len(data)}")

# Let's search backwards from 0x1321B for any NALU length or audio header
# What is right before 0x1321B?
print("Bytes right before 0x1321B (0x131F0 - 0x1321B):", data[0x131F0:0x1321B].hex())
