#!/usr/bin/env python3
"""Generate menu bar icons from SF Symbols as template PNGs."""
import os
from AppKit import NSImage, NSBitmapImageRep, NSPNGFileType, NSMakeSize
from AppKit import NSImageSymbolConfiguration

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(SCRIPT_DIR, "icons")
os.makedirs(ICONS_DIR, exist_ok=True)

# SF Symbol names for each state
ICONS = {
    "mic": "mic",
    "recording": "record.circle",
    "transcribing": "ellipsis.circle",
}

SIZE = 18  # menu bar icon size

for name, symbol in ICONS.items():
    img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, None)
    if not img:
        print(f"Symbol '{symbol}' not found, skipping")
        continue

    # Configure for menu bar size
    config = NSImageSymbolConfiguration.configurationWithPointSize_weight_(SIZE, -1)
    img = img.imageWithSymbolConfiguration_(config)

    # Set size
    img.setSize_(NSMakeSize(SIZE, SIZE))

    # Lock focus and render to bitmap
    img.lockFocus()
    rep = NSBitmapImageRep.alloc().initWithFocusedViewRect_(((0, 0), (SIZE, SIZE)))
    img.unlockFocus()

    # Save as PNG
    data = rep.representationUsingType_properties_(NSPNGFileType, {})
    path = os.path.join(ICONS_DIR, f"{name}.png")
    data.writeToFile_atomically_(path, True)
    print(f"Created {path}")

# Also create @2x versions for Retina
SIZE_2X = 36
for name, symbol in ICONS.items():
    img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, None)
    if not img:
        continue
    config = NSImageSymbolConfiguration.configurationWithPointSize_weight_(SIZE_2X, -1)
    img = img.imageWithSymbolConfiguration_(config)
    img.setSize_(NSMakeSize(SIZE_2X, SIZE_2X))
    img.lockFocus()
    rep = NSBitmapImageRep.alloc().initWithFocusedViewRect_(((0, 0), (SIZE_2X, SIZE_2X)))
    img.unlockFocus()
    data = rep.representationUsingType_properties_(NSPNGFileType, {})
    path = os.path.join(ICONS_DIR, f"{name}@2x.png")
    data.writeToFile_atomically_(path, True)
    print(f"Created {path}")

print("Done!")
