import struct
import mmap
import os

class ForensicScanner:
    """
    Core scanner for extracting forensic metadata from truncated MP4 files.
    """
    def __init__(self, filepath):
        self.filepath = filepath
        self.size = os.path.getsize(filepath)
        self.boxes = []
        self.mdat_start = -1
        self.mdat_claimed_size = -1

    def scan_top_level_boxes(self):
        with open(self.filepath, 'rb') as f:
            while True:
                offset = f.tell()
                if offset >= self.size:
                    break
                
                size_bytes = f.read(4)
                if len(size_bytes) < 4:
                    break
                box_size = int.from_bytes(size_bytes, 'big')
                box_type = f.read(4).decode('ascii', errors='ignore')
                
                header_size = 8
                if box_size == 1:
                    box_size = int.from_bytes(f.read(8), 'big')
                    header_size = 16
                elif box_size == 0:
                    box_size = self.size - offset
                    
                self.boxes.append({
                    "type": box_type,
                    "offset": offset,
                    "size": box_size,
                    "header_size": header_size
                })
                
                if box_type == 'mdat':
                    self.mdat_start = offset + header_size
                    self.mdat_claimed_size = box_size
                    break # Stop at mdat for now
                    
                f.seek(offset + box_size)
        return self.boxes

    def scan_video_nalus(self):
        if self.mdat_start == -1:
            raise ValueError("Run scan_top_level_boxes first, or no mdat found.")
            
        stats = {"sps": 0, "pps": 0, "idr": 0, "non_idr": 0}
        valid_types = {1, 5, 7, 8}
        
        with open(self.filepath, 'rb') as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            
            i = self.mdat_start
            while i < self.size - 4:
                length = int.from_bytes(mm[i:i+4], 'big')
                if 2 < length < 2000000:
                    nal_header = mm[i+4]
                    if (nal_header >> 7) & 1 == 0:
                        nal_type = nal_header & 0x1F
                        if nal_type in valid_types:
                            # Quick heuristic check for next NALU
                            next_idx = i + 4 + length
                            if next_idx + 4 < self.size:
                                next_len = int.from_bytes(mm[next_idx:next_idx+4], 'big')
                                if 2 < next_len < 2000000:
                                    next_header = mm[next_idx+4]
                                    if (next_header >> 7) & 1 == 0:
                                        if nal_type == 7: stats['sps'] += 1
                                        elif nal_type == 8: stats['pps'] += 1
                                        elif nal_type == 5: stats['idr'] += 1
                                        elif nal_type == 1: stats['non_idr'] += 1
                                        i += 4 + length
                                        continue
                i += 1
            mm.close()
        return stats
