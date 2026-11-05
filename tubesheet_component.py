"""Tubesheet 2D procedural SVG generator for Shell-and-Tube Heat Exchangers.

Renders TEMA tube layout patterns (30° triangular, 45° rotated square,
60° rotated triangular, 90° square pitch) with multi-pass partition lanes.
"""

from __future__ import annotations

import math


def generate_tubesheet_svg(
    D_shell_mm: float,
    D_o_mm: float,
    D_i_mm: float,
    pitch_mm: float,
    layout_angle: str = "30",
    N_tubes: int = 100,
    tube_passes: int = 2,
    shell_passes: int = 1,
) -> str:
    """Generate a clean, high-contrast 2D SVG cross-section of the tubesheet tube bundle.

    Args:
        D_shell_mm: Shell inside diameter in mm.
        D_o_mm: Tube outside diameter in mm.
        D_i_mm: Tube inside diameter in mm.
        pitch_mm: Tube pitch in mm.
        layout_angle: "30", "45", "60", or "90".
        N_tubes: Target number of tubes.
        tube_passes: Number of tube passes (1, 2, 4, etc.).
        shell_passes: Number of shell passes.

    Returns:
        A standalone SVG string.
    """
    if D_shell_mm <= 0 or D_o_mm <= 0 or pitch_mm <= D_o_mm:
        return (
            '<svg viewBox="0 0 400 100" xmlns="http://www.w3.org/2000/svg">'
            '<rect width="400" height="100" fill="#fee2e2" rx="8"/>'
            '<text x="200" y="55" text-anchor="middle" fill="#991b1b" font-family="sans-serif" font-size="14">'
            'Geometri verisi eksik veya geçersiz (Pitch &gt; Do ve D_shell &gt; 0 olmalıdır).'
            '</text></svg>'
        )

    r_shell = D_shell_mm / 2.0
    r_tube_o = D_o_mm / 2.0
    r_tube_i = max(0.5, (D_i_mm / 2.0) if D_i_mm < D_o_mm else (r_tube_o * 0.8))

    # TEMA Outer Tube Limit (OTL) clearance: typically 10 to 15 mm from shell ID
    clearance = max(8.0, D_o_mm * 0.4)
    r_otl = max(r_tube_o, r_shell - clearance)

    # Pass partition lane width (mm)
    pass_lane_w = D_o_mm + 6.0 if tube_passes >= 2 else 0.0

    # Generate candidate grid coordinates
    candidates: list[tuple[float, float, int]] = []
    span = int(math.ceil((r_shell * 2.0) / pitch_mm)) + 3

    # Layout coordinate mathematics
    try:
        angle_val = int(float(str(layout_angle).replace("°", "").strip()))
    except (ValueError, TypeError):
        angle_val = 30
    angle = str(angle_val)
    for j in range(-span, span + 1):
        for i in range(-span, span + 1):
            if angle == "30":
                # 30° Triangular: rows spaced by p * sqrt(3)/2, staggered by p/2
                y = j * pitch_mm * (math.sqrt(3.0) / 2.0)
                x = i * pitch_mm + (0.5 * pitch_mm if (j % 2 != 0) else 0.0)
            elif angle == "60":
                # 60° Rotated Triangular: columns spaced by p * sqrt(3)/2, staggered by p/2
                x = i * pitch_mm * (math.sqrt(3.0) / 2.0)
                y = j * pitch_mm + (0.5 * pitch_mm if (i % 2 != 0) else 0.0)
            elif angle == "45":
                # 45° Rotated Square
                x = (i - j) * pitch_mm / math.sqrt(2.0)
                y = (i + j) * pitch_mm / math.sqrt(2.0)
            else:
                # 90° Square Pitch
                x = i * pitch_mm
                y = j * pitch_mm

            # Check boundary inside shell OTL
            r_dist = math.hypot(x, y)
            if r_dist + r_tube_o > r_otl:
                continue

            # Pass partition plate lane check
            pass_idx = 1
            if tube_passes >= 2:
                if abs(y) < (pass_lane_w / 2.0):
                    continue
                if tube_passes == 2:
                    pass_idx = 1 if y > 0 else 2
                elif tube_passes >= 4:
                    if abs(x) < (pass_lane_w / 2.0):
                        continue
                    if x > 0 and y > 0:
                        pass_idx = 1
                    elif x < 0 and y > 0:
                        pass_idx = 2
                    elif x < 0 and y < 0:
                        pass_idx = 3
                    else:
                        pass_idx = 4
            elif tube_passes == 1:
                pass_idx = 1

            candidates.append((r_dist, x, y, pass_idx))  # type: ignore[arg-type]

    # Sort candidates radially from bundle center outward
    candidates.sort(key=lambda item: item[0])

    # Select up to N_tubes
    target_count = max(1, int(N_tubes))
    selected = candidates[:target_count]
    n_drawn = len(selected)

    # Color palette per pass
    pass_colors = {
        1: ("#38bdf8", "#0284c7"),  # Sky blue (outer, stroke)
        2: ("#34d399", "#059669"),  # Emerald
        3: ("#fbbf24", "#d97706"),  # Amber
        4: ("#c084fc", "#7c3aed"),  # Violet
    }

    view_pad = max(25.0, r_shell * 0.15)
    view_box_r = r_shell + view_pad
    view_dim = 2.0 * view_box_r

    svg_parts: list[str] = [
        f'<svg viewBox="{-view_box_r:.1f} {-view_box_r:.1f} {view_dim:.1f} {view_dim:.1f}" '
        'xmlns="http://www.w3.org/2000/svg" style="width:100%; max-height:420px; display:block; margin:auto;">',
        '<defs>',
        '  <radialGradient id="shellBg" cx="50%" cy="50%" r="50%">',
        '    <stop offset="0%" stop-color="#ffffff"/>',
        '    <stop offset="100%" stop-color="#f1f5f9"/>',
        '  </radialGradient>',
        '  <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">',
        '    <feDropShadow dx="0" dy="2" stdDeviation="4" flood-opacity="0.15"/>',
        '  </filter>',
        '</defs>',
        # Shell Outer Flange & Wall
        f'<circle cx="0" cy="0" r="{r_shell + 10:.1f}" fill="#334155" filter="url(#shadow)"/>',
        f'<circle cx="0" cy="0" r="{r_shell:.1f}" fill="url(#shellBg)" stroke="#0f3a5d" stroke-width="3"/>',
        # Outer Tube Limit (OTL) Guide Circle (Dashed)
        f'<circle cx="0" cy="0" r="{r_otl:.1f}" fill="none" stroke="#94a3b8" stroke-dasharray="4,4" stroke-width="1.2"/>',
        # Center Crosshairs
        f'<line x1="{-r_shell:.1f}" y1="0" x2="{r_shell:.1f}" y2="0" stroke="#cbd5e1" stroke-width="1.5" stroke-dasharray="5,5"/>',
        f'<line x1="0" y1="{-r_shell:.1f}" x2="0" y2="{r_shell:.1f}" stroke="#cbd5e1" stroke-width="1.5" stroke-dasharray="5,5"/>',
    ]

    # Draw Pass Partition Plate(s)
    if tube_passes >= 2:
        plate_t = max(6.0, pass_lane_w * 0.5)
        svg_parts.append(
            f'<rect x="{-r_shell:.1f}" y="{-plate_t/2.0:.1f}" width="{2.0*r_shell:.1f}" height="{plate_t:.1f}" '
            'fill="#94a3b8" stroke="#475569" stroke-width="1" rx="2" opacity="0.85"/>'
        )
        if tube_passes >= 4:
            svg_parts.append(
                f'<rect x="{-plate_t/2.0:.1f}" y="{-r_shell:.1f}" width="{plate_t:.1f}" height="{2.0*r_shell:.1f}" '
                'fill="#94a3b8" stroke="#475569" stroke-width="1" rx="2" opacity="0.85"/>'
            )

    # Draw Tubes
    for _, x, y, pass_idx in selected:
        fill_c, stroke_c = pass_colors.get(pass_idx, ("#38bdf8", "#0284c7"))
        svg_parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r_tube_o:.2f}" fill="{fill_c}" stroke="{stroke_c}" stroke-width="1.2"/>'
        )
        svg_parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r_tube_i:.2f}" fill="#f8fafc" stroke="{stroke_c}" stroke-width="0.6"/>'
        )

    # Legend / Info text at bottom
    info_y = view_box_r - 8.0
    p_ratio = pitch_mm / max(1e-3, D_o_mm)
    ratio_warn = " ⚠️ P/Do<1.25" if p_ratio < 1.249 else ""
    svg_parts.append(
        f'<text x="0" y="{info_y:.1f}" text-anchor="middle" font-family="-apple-system, sans-serif" font-size="11.5" font-weight="600" fill="#1e293b">'
        f'TEMA {angle_val}° Açılı Ayna — {n_drawn}/{target_count} Boru | P={pitch_mm:.1f} mm (P/Do={p_ratio:.2f}{ratio_warn}) | {int(tube_passes)} Geçiş'
        '</text>'
    )
    svg_parts.append('</svg>')

    return "\n".join(svg_parts)
