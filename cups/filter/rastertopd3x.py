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

def printer_init(file: BufferedWriter):
    _ = file.write(bytes.fromhex('1f112400')) # This comes from sniffing traffic, I'm unsure what it does, but seems needed
    _ = file.write(ESC + b'@') # initialize printer

def start_page(file: BufferedWriter, image: Image.Image):
    _ = file.write(GS + b'v0')   # GS v 0 : print raster bit image
    # 0: normal, 1 double width, 2 double heigh, 3 quadruple
    mode = 0
    _ = file.write(mode.to_bytes(1, 'little'))
    # number of bytes / line
    _ = file.write(bytes_per_line(image).to_bytes(2, 'little'))
    _ = file.write(image.height.to_bytes(2, 'little'))

def bytes_per_line(image: Image.Image):
    return int((image.width + 7) / 8)

pages = read_ras3(sys.stdin.buffer.read())

for i, datatuple in enumerate(pages):
    (header, imgdata) = datatuple

    if header.cupsColorSpace != 0 or header.cupsNumColors != 1:
        raise ValueError('Invalid color space, only monocolor supported')

    feedLines = header.AdvanceDistance

    im = Image.frombuffer(mode='L', data=imgdata,
                          size=(header.cupsWidth, header.cupsHeight))

    if not header.NegativePrint:
        # For normal printing, invert the image (printer expects inverted data)
        im = ImageOps.invert(im)

    im = im.convert('1')
    im = im.transpose(Image.Transpose.ROTATE_90)

    line = 0
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        printer_init(stdout)
        start_page(stdout, im)
        _ = stdout.write(im.tobytes())
        bpl = bytes_per_line(im)
        _ = stdout.write(bytes.fromhex("00"*bpl*feedLines)) # Feed lines manually
