import os
import struct

def build_mp4_with_one_sample(raw_file, out_mp4):
    with open(raw_file, 'rb') as f:
        data = f.read()

    with open(out_mp4, 'wb') as f:
        # ftyp
        ftyp = b"isom\x00\x00\x02\x00isomiso2mp41"
        f.write(struct.pack(">I4s", len(ftyp) + 8, b"ftyp") + ftyp)
        
        # mdat
        f.write(struct.pack(">I4s", len(data) + 8, b"mdat") + data)
        
        # moov
        moov_data = bytearray()
        mvhd = struct.pack(">BBHL LLL L H H 10x 36x 24x L", 
            0, 0, 0, # version, flags
            0, 0, 1000, 1000, # ctime, mtime, timescale, duration
            0x00010000, 0x0100, 0, # rate, volume, reserved
            2) # next track id
            0, 0, 1000, 1000, # ctime, mtime, timescale, duration
            0x00010000, 0x0100, # rate, volume
            2) # next track id
        moov_data += struct.pack(">I4s", len(mvhd) + 8, b"mvhd") + mvhd
        
        # trak
        trak_data = bytearray()
        
        # tkhd
        tkhd = struct.pack(">BBHL LLL 8x L 8x H H 36x L L", 
            0, 0, 7, # version, flags (track enabled, in movie, in preview)
            0, 0, 1, 1000, # ctime, mtime, track id, duration
            0, 0, 0, 0) # layer, alt group, volume, width, height
        trak_data += struct.pack(">I4s", len(tkhd) + 8, b"tkhd") + tkhd
        
        # mdia
        mdia_data = bytearray()
        
        # mdhd
        mdhd = struct.pack(">BBHL LLL H H", 
            0, 0, 0, 0, 0, 44100, 44100, 0, 0) # timescale 44100, duration 44100
        mdia_data += struct.pack(">I4s", len(mdhd) + 8, b"mdhd") + mdhd
        
        # hdlr
        hdlr = struct.pack(">BBHL 4s 4s 12x 5s", 
            0, 0, 0, b"", b"soun", b"Sound")
        mdia_data += struct.pack(">I4s", len(hdlr) + 8, b"hdlr") + hdlr
        
        # minf
        minf_data = bytearray()
        smhd = struct.pack(">BBHL H H", 0, 0, 0, 0, 0)
        minf_data += struct.pack(">I4s", len(smhd) + 8, b"smhd") + smhd
        
        dinf = struct.pack(">I4s I4s BBHL I", 28, b"dinf", 20, b"dref", 0, 0, 0, 1) + struct.pack(">I4s BBHL", 12, b"url ", 0, 0, 1)
        minf_data += dinf
        
        # stbl
        stbl_data = bytearray()
        
        # stsd
        esds = b"\x03\x19\x00\x00\x00\x04\x11\x40\x15\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x05\x02\x12\x10\x06\x01\x02"
        mp4a = struct.pack(">6x H H H L H H H H", 1, 1, 0, 0, 2, 16, 0, 44100) + struct.pack(">I4s BBHL", len(esds) + 12, b"esds", 0, 0, 0) + esds
        stsd = struct.pack(">BBHL I", 0, 0, 0, 1) + struct.pack(">I4s", len(mp4a) + 8, b"mp4a") + mp4a
        stbl_data += struct.pack(">I4s", len(stsd) + 8, b"stsd") + stsd
        
        # stts
        stts = struct.pack(">BBHL I L L", 0, 0, 0, 1, 1, 1024)
        stbl_data += struct.pack(">I4s", len(stts) + 8, b"stts") + stts
        
        # stsz
        stsz = struct.pack(">BBHL L I L", 0, 0, 0, 0, 1, len(data))
        stbl_data += struct.pack(">I4s", len(stsz) + 8, b"stsz") + stsz
        
        # stsc
        stsc = struct.pack(">BBHL I L L L", 0, 0, 0, 1, 1, 1, 1)
        stbl_data += struct.pack(">I4s", len(stsc) + 8, b"stsc") + stsc
        
        # stco
        stco = struct.pack(">BBHL I L", 0, 0, 0, 1, 8 + len(ftyp) + 8)
        stbl_data += struct.pack(">I4s", len(stco) + 8, b"stco") + stco
        
        minf_data += struct.pack(">I4s", len(stbl_data) + 8, b"stbl") + stbl_data
        mdia_data += struct.pack(">I4s", len(minf_data) + 8, b"minf") + minf_data
        trak_data += struct.pack(">I4s", len(mdia_data) + 8, b"mdia") + mdia_data
        
        moov_data += struct.pack(">I4s", len(trak_data) + 8, b"trak") + trak_data
        
        f.write(struct.pack(">I4s", len(moov_data) + 8, b"moov") + moov_data)

if __name__ == "__main__":
    build_mp4_with_one_sample("gap.bin", "gap.mp4")
