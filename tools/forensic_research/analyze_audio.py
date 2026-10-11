import sys
import mmap
from struct import unpack

def analyze_interleaving(filepath):
    with open(filepath, 'rb') as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        
    size = len(mm)
    i = 0x30
    
    blocks = []
    
    while i < size - 4 and len(blocks) < 100:
        length = int.from_bytes(mm[i:i+4], 'big')
        
        if length > 0 and i + 4 + length <= size:
            header = mm[i+4]
            forbidden = (header >> 7) & 1
            if forbidden == 0:
                nal_type = header & 0x1F
                if nal_type in (1, 5, 7, 8):
                    blocks.append(("VIDEO", nal_type, length, i))
                    i += 4 + length
                    continue
        
        # If it's not a valid video NALU, let's see if it's AAC.
        # AAC in MP4 is usually raw frames. But maybe it's chunk interleaved?
        # Let's just find the next video NALU to see the gap size.
        gap_start = i
        
        # Scan forward for next 4-byte length prefix that looks like a NALU
        found_next_video = False
        while i < size - 4:
            length = int.from_bytes(mm[i:i+4], 'big')
            if 10 < length < 2000000 and i + 4 + length <= size:
                header = mm[i+4]
                forbidden = (header >> 7) & 1
                if forbidden == 0:
                    nal_type = header & 0x1F
                    if nal_type in (1, 5, 7, 8):
                        # Verify the next one too just to be sure it's not random noise
                        next_i = i + 4 + length
                        if next_i < size - 4:
                            next_length = int.from_bytes(mm[next_i:next_i+4], 'big')
                            if 10 < next_length < 2000000 and next_i + 4 + next_length <= size:
                                next_header = mm[next_i+4]
                                if ((next_header >> 7) & 1) == 0 and (next_header & 0x1F) in (1, 5, 7, 8):
                                    found_next_video = True
                                    break
            i += 1
            
        if found_next_video:
            gap_size = i - gap_start
            if gap_size > 0:
                blocks.append(("GAP", gap_size, gap_start))
        else:
            break
            
    mm.close()
    
    for b in blocks:
        if b[0] == "VIDEO":
            print(f"VIDEO NAL_{b[1]:02d} size={b[2]} offset={b[3]}")
        else:
            print(f"--- GAP size={b[1]} offset={b[2]} ---")

if __name__ == '__main__':
    analyze_interleaving(sys.argv[1])
