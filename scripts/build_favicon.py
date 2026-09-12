#!/usr/bin/env python3
"""Original font-independent SVG paths and matching high-resolution raster icons."""
from pathlib import Path
from PIL import Image, ImageDraw
root=Path(__file__).resolve().parents[1]/'web/static'
color='#FFB000'
paths=[[(10,19),(10,45),(17,45),(22,41),(22,36),(18,32),(10,32)],
       [(10,19),(17,19),(21,22),(21,28),(18,32)],
       [(27,19),(39,19)],[(33,19),(33,45)],
       [(54,22),(51,19),(46,19),(43,22),(43,42),(46,45),(51,45),(54,42)]]
svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">',
     '<title>JustVerify — BTC circle</title>',
     f'<circle cx="32" cy="32" r="29.5" fill="#080d10" stroke="{color}" stroke-width="3"/>']
for path in paths:
    d='M'+'L'.join(f'{x} {y}' for x,y in path)
    svg.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
svg.append('</svg>');(root/'favicon.svg').write_text('\n'.join(svg)+'\n')
scale=16
im=Image.new('RGBA',(64*scale,64*scale));draw=ImageDraw.Draw(im)
draw.ellipse((1*scale,1*scale,63*scale,63*scale),fill=color)
draw.ellipse((4*scale,4*scale,60*scale,60*scale),fill='#080d10')
for path in paths:
    draw.line([(x*scale,y*scale) for x,y in path],fill=color,width=3*scale,joint='curve')
    for x,y in path:draw.ellipse(((x-1.5)*scale,(y-1.5)*scale,(x+1.5)*scale,(y+1.5)*scale),fill=color)
im.resize((256,256),Image.Resampling.LANCZOS).save(root/'favicon.ico',sizes=[(16,16),(32,32),(48,48)])
im.resize((180,180),Image.Resampling.LANCZOS).save(root/'apple-touch-icon.png')
