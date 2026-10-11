import sys
import mmap

def count_video_samples(filepath):
    with open(filepath, 'rb') as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        
    size = len(mm)
    valid_nalu_types = {1, 5}
    video_count = 0
    
    # We will just do a heuristic fast count of valid 4-byte prefixes that point to valid NALUs
    i = 0x30
    while i < size - 4:
        length = int.from_bytes(mm[i:i+4], 'big')
        if 10 < length < 2000000:
            nal_header = mm[i+4]
            forbidden = (nal_header >> 7) & 1
            if forbidden == 0:
                nal_type = nal_header & 0x1F
                if nal_type in valid_nalu_types:
                    # check if the next NALU is valid to confirm this isn't audio noise
                    next_idx = i + 4 + length
                    if next_idx + 4 < size:
                        next_len = int.from_bytes(mm[next_idx:next_idx+4], 'big')
                        if 10 < next_len < 2000000:
                            next_header = mm[next_idx+4]
                            if (next_header >> 7) & 1 == 0:
                                next_type = next_header & 0x1F
                                if next_type in valid_nalu_types:
                                    video_count += 1
                                    i += 4 + length
                                    continue
        i += 1
        
    print(f"Estimated Video Samples: {video_count}")
    mm.close()

if __name__ == '__main__':
    count_video_samples(sys.argv[1])
