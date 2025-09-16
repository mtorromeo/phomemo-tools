#! /usr/bin/env python3

import os
import sys
from io import BufferedWriter
from struct import unpack
from typing import NamedTuple

from PIL import Image, ImageOps

ESC = b'\x1b'
GS  = b'\x1d'

class CupsRasterPageHeader(NamedTuple):
    # Documentation at https://www.cups.org/doc/spec-raster.html
    # Order MUST match the unpack format string below
    MediaClass: str
    MediaColor: str
    MediaType: str
    OutputType: str
    AdvanceDistance: int
    AdvanceMedia: int
    Collate: int
    CutMedia: int
    Duplex: int
    HWResolutionH: int
    HWResolutionV: int
    ImagingBoundingBoxL: int
    ImagingBoundingBoxB: int
    ImagingBoundingBoxR: int
    ImagingBoundingBoxT: int
    InsertSheet: int
    Jog: int
    LeadingEdge: int
    MarginsL: int
    MarginsB: int
    ManualFeed: int
    MediaPosition: int
    MediaWeight: int
    MirrorPrint: int
    NegativePrint: int
    NumCopies: int
    Orientation: int
    OutputFaceUp: int
    PageSizeW: int
    PageSizeH: int
    Separations: int
    TraySwitch: int
    Tumble: int
    cupsWidth: int
    cupsHeight: int
    cupsMediaType: int
    cupsBitsPerColor: int
    cupsBitsPerPixel: int
    cupsBitsPerLine: int
    cupsColorOrder: int
    cupsColorSpace: int
    cupsCompression: int
    cupsRowCount: int
    cupsRowFeed: int
    cupsRowStep: int
    cupsNumColors: int
    cupsBorderlessScalingFactor: float
    cupsPageSizeW: float
    cupsPageSizeH: float
    cupsImagingBBoxL: float
    cupsImagingBBoxB: float
    cupsImagingBBoxR: float
    cupsImagingBBoxT: float
    cupsInteger1: int
    cupsInteger2: int
    cupsInteger3: int
    cupsInteger4: int
    cupsInteger5: int
    cupsInteger6: int
    cupsInteger7: int
    cupsInteger8: int
    cupsInteger9: int
    cupsInteger10: int
    cupsInteger11: int
    cupsInteger12: int
    cupsInteger13: int
    cupsInteger14: int
    cupsInteger15: int
    cupsInteger16: int
    cupsReal1: float
    cupsReal2: float
    cupsReal3: float
    cupsReal4: float
    cupsReal5: float
    cupsReal6: float
    cupsReal7: float
    cupsReal8: float
    cupsReal9: float
    cupsReal10: float
    cupsReal11: float
    cupsReal12: float
    cupsReal13: float
    cupsReal14: float
    cupsReal15: float
    cupsReal16: float
    cupsString1: str
    cupsString2: str
    cupsString3: str
    cupsString4: str
    cupsString5: str
    cupsString6: str
    cupsString7: str
    cupsString8: str
    cupsString9: str
    cupsString10: str
    cupsString11: str
    cupsString12: str
    cupsString13: str
    cupsString14: str
    cupsString15: str
    cupsString16: str
    cupsMarkerType: str
    cupsRenderingIntent: str
    cupsPageSizeName: str

def read_ras3(rdata: bytes):
    if not rdata:
        raise ValueError('No data received')

    # Check for magic word (either big-endian or little-endian)
    magic: bytes = unpack('@4s', rdata[0:4])[0]
    if magic != b'RaS3' and magic != b'3SaR':
        raise ValueError("This is not in RaS3 format")
    rdata = rdata[4:]  # Strip magic word
    pages: list[tuple[CupsRasterPageHeader, bytes]] = []

    while rdata:  # Loop over all pages
        struct_data = unpack(
            '@64s 64s 64s 64s I I I I I II IIII I I I II I I I I I I I I II I I I I I I I I I I I I I I I I f ff ffff IIIIIIIIIIIIIIII ffffffffffffffff 64s 64s 64s 64s 64s 64s 64s 64s 64s 64s 64s 64s 64s 64s 64s 64s 64s 64s 64s',
            rdata[0:1796]
        )
        data = [
            # Strip trailing null-bytes of strings
            b.decode().rstrip('\x00') if isinstance(b, bytes) else b
            for b in struct_data
        ]
        header = CupsRasterPageHeader._make(data)

        # Read image data of this page into a bytearray
        imgdata = rdata[1796:1796 + (header.cupsWidth * header.cupsHeight * header.cupsBitsPerPixel // 8)]
        pages.append((header, imgdata))

        # Remove this page from the data stream, continue with the next page
        rdata = rdata[1796 + (header.cupsWidth * header.cupsHeight * header.cupsBitsPerPixel // 8):]

    return pages

def select_speed(file: BufferedWriter, speed: int = 5):
    _ = file.write(ESC + b'\x4e' + b'\x0d') # select Print Speed
    _ = file.write(speed.to_bytes(1, 'little'))
    return

def select_density(file: BufferedWriter, density: int = 10):
    _ = file.write(ESC + b'\x4e' + b'\x04') # select Print Speed
    _ = file.write(density.to_bytes(1, 'little'))
    return

def select_media_type(file: BufferedWriter, media_type: int):
    _ = file.write(b'\x1f' + b'\x11') # select Media Type,
    _ = file.write(media_type.to_bytes(1, 'little'))
    return

def print_header(file: BufferedWriter, media_type: int = 10):
    select_speed(file, 5)
    select_density(file, 10)
    select_media_type(file, media_type)
    return

def print_raster(file: BufferedWriter, image: Image.Image, line: int, lines: int = 0xff, mode: int = 0):
    _ = file.write(GS + b'v0')   # GS v 0 : print raster bit image
    # 0: normal, 1 double width, 2 double heigh, 3 quadruple
    _ = file.write(mode.to_bytes(1, 'little'))
    # number of bytes / line
    _ = file.write(int((image.width + 7) / 8).to_bytes(2, 'little'))
    # nulber of lines in the image
    _ = file.write(lines.to_bytes(2, 'little'))
    # bit image
    block = image.crop((0, line, image.width, line + lines))
    _ = stdout.write(block.tobytes())
    return

def print_footer(file: BufferedWriter):
    _ = file.write(b'\x1f' + b'\xf0' + b'\x05' + b'\x00')
    _ = file.write(b'\x1f' + b'\xf0' + b'\x03' + b'\x00')

pages = read_ras3(sys.stdin.buffer.read())

for i, datatuple in enumerate(pages):
    (header, imgdata) = datatuple

    if header.cupsNumColors != 1:
        raise ValueError('Invalid color space, only monocolor supported')

    im = Image.frombuffer(mode='L', data=imgdata,
                          size=(header.cupsWidth, header.cupsHeight))

    if not header.NegativePrint:
        # For normal printing, invert the image (printer expects inverted data)
        im = ImageOps.invert(im)

    im = im.convert('1')

    line = 0

    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        print_header(stdout,header.cupsMediaType)
        lines = im.height
        print_raster(stdout, im, line, lines)
        print_footer(stdout)
