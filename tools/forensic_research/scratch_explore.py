with open('samples/corrupted/original.mp4', 'rb') as f:
    # 0x23BE1 + 4 + 20115 = 0x28A78. Next is 0x28A84 (diff = 12 bytes)
    f.seek(0x28A78)
    b12 = f.read(12)
    print("Between 0x28A78 and 0x28A84 (12 bytes):", b12.hex(), [chr(x) if 32<=x<=126 else '.' for x in b12])
    
    # Also check between 0x28A84 + 4 + 19387 = 0x2D643 and 0x2D649 (6 bytes)
    f.seek(0x2D643)
    b6 = f.read(6)
    print("Between 0x2D643 and 0x2D649 (6 bytes):", b6.hex(), [chr(x) if 32<=x<=126 else '.' for x in b6])
    
    # Also check between 0x1EECC + 4 + 19717 = 0x23BD5 and 0x23BE1 (12 bytes)
    f.seek(0x23BD5)
    b_prev = f.read(12)
    print("Between 0x23BD5 and 0x23BE1 (12 bytes):", b_prev.hex(), [chr(x) if 32<=x<=126 else '.' for x in b_prev])
