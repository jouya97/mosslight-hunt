"""Portable SVG maps and time-series prints, without plotting dependencies."""
from __future__ import annotations
from html import escape
from .catalog import LAYERS
from .validation import choice

TERRAIN_COLORS = {"soil":"#786950", "sand":"#c9b57b", "peat":"#494039", "pond":"#507f91", "stone":"#92908b"}


def color_scale(value):
    """Interpolate a fixed 0–100 scale from dry gold to wet teal."""
    value = max(0,min(100,value))/100
    low,high = (218,183,109),(54,146,148)
    return "#"+"".join(f"{round(a+(b-a)*value):02x}" for a,b in zip(low,high))


def render_map(world, layer="moisture", interactive=False):
    choice(layer,LAYERS,"map layer")
    if layer == "art":
        from .render import render_svg
        return render_svg(world,interactive=interactive)
    from .habitat import effective_shade
    tile,margin,header = 42,24,76
    width,height = world.width*tile+margin*2, world.height*tile+header+60
    pieces = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(layer)} map">',
              f'<rect width="{width}" height="{height}" fill="#122c29" rx="12"/>',
              f'<text x="{margin}" y="30" fill="#f0e7ce" font-size="19" font-family="Georgia">{escape(world.workbench["title"])}</text>',
              f'<text x="{margin}" y="54" fill="#a9c7b6" font-size="12" font-family="sans-serif">{layer.upper()} · DAY {world.day}</text>']
    for i,cell in enumerate(world.cells):
        x,y = i%world.width,i//world.width
        settings = world.workbench["tiles"][i]
        value = settings[layer] if layer in ("terrain","mulch","stress") else effective_shade(world,i) if layer == "shade" else getattr(cell,layer)
        color = TERRAIN_COLORS[value] if layer == "terrain" else color_scale(value)
        label = str(value) if layer != "terrain" else value[:2].upper()
        attrs = 'tabindex="0" role="button"' if interactive else ''
        pieces += [f'<g class="tile" data-x="{x}" data-y="{y}" {attrs}>',
                   f'<rect x="{margin+x*tile}" y="{header+y*tile}" width="39" height="39" rx="5" fill="{color}"/>',
                   f'<text x="{margin+x*tile+19}" y="{header+y*tile+24}" text-anchor="middle" font-size="12" fill="#142925">{label}</text>',
                   f'<title>Tile {x+1}, {y+1}: {layer} {value}</title></g>']
    if layer != "terrain":
        for value in range(0,101,10):
            pieces.append(f'<rect x="{margin+value*1.5}" y="{height-35}" width="15" height="10" fill="{color_scale(value)}"/>')
        pieces.append(f'<text x="{margin}" y="{height-10}" fill="#cadbcb" font-size="10">0 ← {layer} → 100</text>')
    pieces.append('</svg>')
    return ''.join(pieces)


def render_history(world, metric="moisture"):
    choice(metric,("moisture","nutrients","vitality","occupied","births","losses"),"history metric")
    width,height,left,top = 760,300,60,50
    plot_w,plot_h = 660,195
    history = world.workbench["history"]
    maximum = len(world.cells) if metric in ("occupied","births","losses") else 100
    pieces = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{metric} history">',
              f'<rect width="{width}" height="{height}" rx="12" fill="#122c29"/>',
              f'<text x="{left}" y="28" fill="#efdfb6" font-family="Georgia" font-size="18">{metric.title()} through the days</text>']
    for i in range(5):
        y = top+plot_h*i/4
        pieces += [f'<path d="M {left} {y} H {left+plot_w}" stroke="#34554a"/>',
                   f'<text x="{left-10}" y="{y+4}" text-anchor="end" fill="#b2c7b8" font-size="11">{maximum*(4-i)/4:g}</text>']
    if history:
        first,last = history[0]["day"],history[-1]["day"]
        points = [(left+(h["day"]-first)/max(1,last-first)*plot_w,top+plot_h*(1-h[metric]/maximum)) for h in history]
        path = " ".join(f'{"M" if i == 0 else "L"} {x:.2f} {y:.2f}' for i,(x,y) in enumerate(points))
        pieces.append(f'<path d="{path}" stroke="#d9c389" stroke-width="2" fill="none"/>')
        for h,(x,y) in zip(history,points):
            pieces.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="#e9d7a2"><title>Day {h["day"]}: {h[metric]}</title></circle>')
        pieces.append(f'<text x="{left}" y="275" fill="#c8d4c4" font-size="12">Day {first}</text>')
        pieces.append(f'<text x="{left+plot_w}" y="275" text-anchor="end" fill="#c8d4c4" font-size="12">Day {last}</text>')
    else:
        pieces.append('<text x="380" y="160" text-anchor="middle" fill="#c8d4c4">Advance a day to begin the record.</text>')
    pieces.append('</svg>')
    return ''.join(pieces)
