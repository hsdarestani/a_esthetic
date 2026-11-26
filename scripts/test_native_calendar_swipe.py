"""Compare a real Android weekly swipe before and after. Synthetic calendar only."""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops

before_path = Path(sys.argv[1])
before = Image.open(before_path).convert('RGB')
w, h = before.size
ruler_color = (246, 247, 251)
ruler_rows = [y for y in range(h // 5, (h * 9) // 10) if before.getpixel((5, y)) == ruler_color]
assert len(ruler_rows) > h // 4, 'Missing native ruler in weekly fixture'
top, bottom = min(ruler_rows), max(ruler_rows)
middle = (top + bottom) // 2
width = next(x for x in range(5, w // 3) if before.getpixel((x, middle)) != ruler_color)
assert width > 15, 'Cannot locate the fixed ruler width'
subprocess.run(['adb', 'shell', 'input', 'swipe', str(int(w*.87)), str(middle), str(int(w*.25)), str(middle), '650'], check=True)
subprocess.run(['adb', 'shell', 'sleep', '1'], check=True)
after_path = before_path.with_name(before_path.stem + '-swiped.png')
with after_path.open('wb') as stream:
    subprocess.run(['adb', 'exec-out', 'screencap', '-p'], stdout=stream, check=True)
after = Image.open(after_path).convert('RGB')
def pixels_changed(box):
    return sum(1 for pixel in ImageChops.difference(before.crop(box), after.crop(box)).getdata() if max(pixel)>8)
ruler_box = (0, top + 5, width - 2, bottom - 5)
grid_box = (width + 5, max(0, top - int(width*.6)), int(w*.95), bottom - 5)
assert pixels_changed(ruler_box) <= 15, 'Ruler moved during real weekly swipe'
assert pixels_changed(grid_box) > 250, 'Weekly day columns did not move during real swipe'
print('PASS actual Android horizontal swipe: dates move, fixed ruler unchanged')
