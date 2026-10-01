"""Dependency-free SVG illustration of a living terrarium."""
from __future__ import annotations

from html import escape
import math
from .engine import season
from .model import World

PALETTES = {
    "Dawn": ("#102e2d", "#193d37", "#ffe6ac"),
    "Highsummer": ("#193329", "#385039", "#ffdca0"),
    "Ember": ("#302e2c", "#484035", "#f5be93"),
    "Hush": ("#172b32", "#29404a", "#c8e6eb"),
}


def _plant(species: str, cx: float, cy: float, size: float, vitality: int, key: int) -> str:
    opacity = .48 + vitality / 200
    if species == "moss":
        parts = []
        for j in range(7):
            angle = j * 2.4 + key * .17
            distance = size * (.12 + (j % 3) * .13)
            px = cx + math.cos(angle) * distance
            py = cy + math.sin(angle) * distance
            parts.append(f'<ellipse cx="{px:.1f}" cy="{py:.1f}" rx="{size*.19:.1f}" ry="{size*.13:.1f}" transform="rotate({j*31} {px:.1f} {py:.1f})"/>')
        return f'<g fill="#91bb78" opacity="{opacity:.2f}">{"".join(parts)}</g>'
    if species == "fern":
        branches = [f'<path d="M {cx:.1f} {cy+size*.36:.1f} Q {cx+size*.05:.1f} {cy-size*.1:.1f} {cx:.1f} {cy-size*.48:.1f}" fill="none" stroke="#c4d8a0" stroke-width="1.4"/>']
        for j in range(4):
            y = cy + size * (.18 - j * .16)
            span = size * (.34 - j * .04)
            for direction in (-1, 1):
                branches.append(f'<path d="M {cx:.1f} {y:.1f} Q {cx+direction*span*.55:.1f} {y-size*.12:.1f} {cx+direction*span:.1f} {y-size*.22:.1f} Q {cx+direction*span*.56:.1f} {y+size*.1:.1f} {cx:.1f} {y:.1f}" fill="#7ebd80"/>')
        return f'<g opacity="{opacity:.2f}">{"".join(branches)}</g>'
    if species == "clover":
        petals = []
        for j in range(4):
            angle = j * math.pi / 2 + .3
            px = cx + math.cos(angle) * size * .16
            py = cy + math.sin(angle) * size * .16
            petals.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{size*.16:.1f}"/>')
        return f'<g fill="#afd78a" opacity="{opacity:.2f}">{"".join(petals)}<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size*.07:.1f}" fill="#f1d891"/></g>'
    # A mushroom with a soft halo and gills.
    return (f'<g opacity="{opacity:.2f}"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size*.5:.1f}" fill="#b8ddae" opacity=".13"/>'
            f'<path d="M {cx-size*.09:.1f} {cy+size*.29:.1f} L {cx-size*.07:.1f} {cy:.1f} L {cx+size*.07:.1f} {cy:.1f} L {cx+size*.09:.1f} {cy+size*.29:.1f} Z" fill="#e6ddd0"/>'
            f'<path d="M {cx-size*.33:.1f} {cy+size*.06:.1f} Q {cx:.1f} {cy-size*.5:.1f} {cx+size*.33:.1f} {cy+size*.02:.1f} Q {cx:.1f} {cy+size*.15:.1f} {cx-size*.33:.1f} {cy+size*.06:.1f}" fill="#b9a6d9"/>'
            f'<circle cx="{cx-size*.09:.1f}" cy="{cy-size*.11:.1f}" r="{size*.035:.1f}" fill="#f9e8c4"/></g>')


def render_svg(world: World, *, interactive: bool = False) -> str:
    tile = 48
    margin = 38
    header = 94
    width = world.width * tile + margin * 2
    height = world.height * tile + header + 38
    dark, mid, moon = PALETTES[season(world.day)]
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {width} {height}" role="img" aria-label="Mosslight terrarium on day {world.day}">',
        '<defs>',
        f'<linearGradient id="night" x2="0" y2="1"><stop stop-color="{dark}"/><stop offset="1" stop-color="{mid}"/></linearGradient>',
        '<radialGradient id="pool"><stop stop-color="#9bd9c0" stop-opacity=".22"/><stop offset="1" stop-color="#9bd9c0" stop-opacity="0"/></radialGradient>',
        '<filter id="glow"><feGaussianBlur stdDeviation="3"/></filter>',
        '</defs>',
        f'<rect width="{width}" height="{height}" rx="24" fill="url(#night)"/>',
        f'<circle cx="{width-92}" cy="50" r="22" fill="{moon}" opacity=".8"/>',
        f'<text x="{margin}" y="48" fill="#f7ead1" font-family="Georgia,serif" font-size="26" letter-spacing="2">MOSSLIGHT</text>',
        f'<text x="{margin}" y="72" fill="#b5c8ba" font-family="sans-serif" font-size="11" letter-spacing="2">DAY {world.day:03d} · {escape(season(world.day).upper())} · {escape(world.weather.upper())}</text>',
        f'<rect x="{margin-10}" y="{header-10}" width="{world.width*tile+20}" height="{world.height*tile+20}" rx="18" fill="#071b1c" opacity=".58"/>',
    ]
    for y in range(world.height):
        for x in range(world.width):
            i = world.index(x, y)
            cell = world.cells[i]
            cx = margin + x * tile + tile / 2
            cy = header + y * tile + tile / 2
            damp = cell.moisture / 100
            settings = world.workbench["tiles"][i]
            soil = "#344b3e" if damp > .62 else "#42503c" if damp > .35 else "#575340"
            from .charts import TERRAIN_COLORS
            if settings["terrain"] != "soil":
                soil = TERRAIN_COLORS[settings["terrain"]]
            r = 21.5
            attrs = 'tabindex="0" role="button"' if interactive else ''
            pieces.append(f'<g class="tile" data-x="{x}" data-y="{y}" {attrs}>')
            pieces.append(f'<rect x="{cx-r:.1f}" y="{cy-r:.1f}" width="{r*2:.1f}" height="{r*2:.1f}" rx="10" fill="{soil}" opacity="{.65 + damp*.19:.2f}"/>')
            if damp > .62:
                pieces.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="22" fill="url(#pool)"/>')
            # Fine mineral specks distinguish empty earth from a flat grid.
            for j in range(3):
                dx = ((i * 17 + j * 23) % 31) - 15
                dy = ((i * 29 + j * 13) % 29) - 14
                pieces.append(f'<circle cx="{cx+dx:.1f}" cy="{cy+dy:.1f}" r="{.6+j*.2:.1f}" fill="#b5ac88" opacity=".34"/>')
            if settings["structure"] != "none":
                symbols = {"shade_cloth": "▱", "rain_barrel": "▥", "bee_house": "⌂", "log": "≋"}
                pieces.append(f'<text x="{cx+12}" y="{cy-10}" fill="#e6d3a5" font-size="12">{symbols[settings["structure"]]}</text>')
            if cell.species:
                pieces.append(_plant(cell.species, cx, cy, 37, cell.vitality, i))
            if interactive:
                pieces.append(f'<rect x="{cx-r:.1f}" y="{cy-r:.1f}" width="{r*2:.1f}" height="{r*2:.1f}" rx="10" fill="transparent"><title>Tile {x+1}, {y+1}: {escape(cell.species or "bare soil")}, moisture {cell.moisture}, nutrients {cell.nutrients}</title></rect>')
            pieces.append('</g>')
    pieces.extend([
        f'<text x="{margin}" y="{height-14}" fill="#a1b6a9" font-family="sans-serif" font-size="10" letter-spacing="1.5">A SMALL WORLD, HELD IN GLASS</text>',
        f'<text x="{width-margin}" y="{height-14}" text-anchor="end" fill="#a1b6a9" font-family="sans-serif" font-size="10">SEED {world.seed}</text>',
        '</svg>',
    ])
    return ''.join(pieces)
