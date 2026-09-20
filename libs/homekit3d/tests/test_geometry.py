from __future__ import annotations

import math

import pytest

from homekit3d import Plan
from homekit3d.geometry import Frame, Mesh, Shell, build_shell, triangulate


def total_volume(shell: Shell) -> float:
    return sum(m.volume() for m in shell.meshes.values())


def shoelace(poly) -> float:
    n = len(poly)
    return abs(sum(p[0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * p[1] for i, p in enumerate(poly))) / 2


def one_wall(length=4.0, thickness=0.2, height=2.7) -> Plan:
    plan = Plan(length, 3.0, height=height)
    plan.wall((0, 0), (length, 0), thickness=thickness, exterior=False, id="w")
    return plan


def bare(plan: Plan, **kw) -> Shell:
    return build_shell(plan, floors=False, slab=False, **kw)


def test_a_plain_wall_has_the_volume_of_its_box():
    assert total_volume(bare(one_wall(), extend_ends=False)) == pytest.approx(4.0 * 0.2 * 2.7)


def test_extending_the_ends_adds_half_a_thickness_on_each_side():
    assert total_volume(bare(one_wall(), extend_ends=True)) == pytest.approx((4.0 + 0.2) * 0.2 * 2.7)


def test_a_door_removes_exactly_its_opening_from_the_wall():
    plan = one_wall()
    plan.door("w", 1.0, width=0.9)
    shell = bare(plan, extend_ends=False)
    walls = sum(m.volume() for k, m in shell.meshes.items() if k.startswith("wall"))
    assert walls == pytest.approx(4.0 * 0.2 * 2.7 - 0.9 * 2.05 * 0.2, abs=1e-6)


def test_a_window_leaves_a_sill_below_and_a_lintel_above():
    plan = one_wall()
    plan.window("w", 1.0, width=1.2, sill=0.9, height=1.2)
    walls = sum(m.volume() for k, m in bare(plan, extend_ends=False).meshes.items() if k.startswith("wall"))
    assert walls == pytest.approx(4.0 * 0.2 * 2.7 - 1.2 * 1.2 * 0.2, abs=1e-6)


def test_two_openings_on_one_wall_are_both_cut():
    plan = one_wall(length=6.0)
    plan.door("w", 0.5, width=0.9)
    plan.window("w", 3.0, width=1.2)
    walls = sum(m.volume() for k, m in bare(plan, extend_ends=False).meshes.items() if k.startswith("wall"))
    assert walls == pytest.approx(6.0 * 0.2 * 2.7 - 0.9 * 2.05 * 0.2 - 1.2 * 1.2 * 0.2, abs=1e-6)


def test_a_house_has_positive_volume(house):
    assert total_volume(bare(house)) > 0


def test_a_single_material_box_is_a_closed_outward_solid():
    shell = Shell()
    shell.box(Frame(0.0, 0.0, 0.0, 1.0), 0, 2, -0.1, 0.1, 0, 1, "m")      # mur dirigé vers +Y
    assert shell.meshes["m"].volume() == pytest.approx(0.4)


def _normals(mesh: Mesh):
    out = []
    for f in mesh.faces:
        p = [mesh.verts[i] for i in f[:3]]
        u = [p[1][k] - p[0][k] for k in range(3)]
        v = [p[2][k] - p[0][k] for k in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        norm = math.sqrt(sum(c * c for c in n)) or 1
        out.append((sum(q[0] for q in p) / 3, sum(q[1] for q in p) / 3, n[0] / norm, n[1] / norm, n[2] / norm))
    return out


def test_the_exterior_paint_faces_outward(house):
    ext = _normals(bare(house).meshes["wall_ext"])
    centre = (house.width / 2, -house.depth / 2)
    sides = [(cx, cy, nx, ny) for cx, cy, nx, ny, nz in ext if abs(nz) < 0.5]
    outward = [1 for cx, cy, nx, ny in sides if (cx - centre[0]) * nx + (cy - centre[1]) * ny > 0]
    assert sides and len(outward) / len(sides) > 0.6


def test_the_interior_paint_faces_the_inside():
    """Sur une maison sans cloison, chaque face peinte « intérieur » regarde vers le centre."""
    plan = Plan(8.0, 6.0)
    plan.outline()
    inner = _normals(bare(plan).meshes["wall_int"])
    centre = (plan.width / 2, -plan.depth / 2)
    sides = [(cx, cy, nx, ny) for cx, cy, nx, ny, nz in inner if abs(nz) < 0.5]
    facing = [1 for cx, cy, nx, ny in sides if (centre[0] - cx) * nx + (centre[1] - cy) * ny > 0]
    assert sides and len(facing) == len(sides)


def test_floors_face_up_and_use_a_material_per_room_type(house):
    shell = build_shell(house)
    assert {"floor:living", "floor:bedroom", "floor:hallway"} <= set(shell.meshes)
    for name in ("floor:living", "floor:bedroom"):
        assert all(nz > 0.99 for *_, nz in _normals(shell.meshes[name]))


def test_the_floor_area_matches_the_room_area(house):
    m = build_shell(house).meshes["floor:living"]
    area = sum(abs((m.verts[f[1]][0] - m.verts[f[0]][0]) * (m.verts[f[2]][1] - m.verts[f[0]][1])
                   - (m.verts[f[2]][0] - m.verts[f[0]][0]) * (m.verts[f[1]][1] - m.verts[f[0]][1])) / 2 for f in m.faces)
    assert area == pytest.approx(house.rooms[0].area)


def _signed(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])


@pytest.mark.parametrize("poly", [
    [(0, 0), (4, 0), (4, 3), (0, 3)],
    [(0, 3), (4, 3), (4, 0), (0, 0)],                                   # sens inverse
    [(0, 0), (6, 0), (6, 2), (2, 2), (2, 5), (0, 5)],                   # en L
    [(0, 0), (3, 0), (3, 1), (5, 1), (5, 4), (0, 4)],                   # autre L
])
def test_triangulation_covers_exactly_the_polygon(poly):
    tris = triangulate(poly)
    assert all(_signed(poly[a], poly[b], poly[c]) > 0 for a, b, c in tris)          # antihoraires
    assert len(tris) == len(poly) - 2
    area = sum(abs((poly[b][0] - poly[a][0]) * (poly[c][1] - poly[a][1]) - (poly[c][0] - poly[a][0]) * (poly[b][1] - poly[a][1])) / 2
               for a, b, c in tris)
    assert area == pytest.approx(shoelace(poly))


def test_triangulation_of_degenerate_input_is_empty():
    assert triangulate([(0, 0), (1, 1)]) == []


def test_openings_get_frames_glass_and_leaves(house):
    assert {"trim", "door", "glass", "handle"} <= set(build_shell(house).meshes)


def test_a_garage_door_gets_a_closed_panel():
    plan = one_wall(length=6.0)
    plan.door("w", 1.0, width=2.4)
    assert "garage" in build_shell(plan).meshes


def test_the_shell_stays_light(house):
    assert build_shell(house).triangles < 3000


def test_a_wall_frame_is_right_handed():
    f = Frame(1.0, 2.0, 0.6, 0.8)
    a, b = f.at(1, 0, 0), f.at(0, 1, 0)
    ox, oy = f.at(0, 0, 0)[:2]
    ux, uy = a[0] - ox, a[1] - oy
    nx, ny = b[0] - ox, b[1] - oy
    assert ux * ny - uy * nx > 0                        # n est à gauche de u : repère direct


def _outline_reversed(plan: Plan) -> None:
    """Les quatre murs extérieurs tracés dans le sens inverse : la face « intérieure » est alors du côté +n."""
    w, d = plan.width, plan.depth
    plan.wall((0, 0), (0, d), exterior=True)
    plan.wall((0, d), (w, d), exterior=True)
    plan.wall((w, d), (w, 0), exterior=True)
    plan.wall((w, 0), (0, 0), exterior=True)


def test_paint_sides_do_not_depend_on_the_direction_the_wall_was_drawn():
    plan = Plan(8.0, 6.0)
    _outline_reversed(plan)
    shell = bare(plan)
    centre = (plan.width / 2, -plan.depth / 2)
    inner = [(cx, cy, nx, ny) for cx, cy, nx, ny, nz in _normals(shell.meshes["wall_int"]) if abs(nz) < 0.5]
    assert inner and all((centre[0] - cx) * nx + (centre[1] - cy) * ny > 0 for cx, cy, nx, ny in inner)
    outer = [(cx, cy, nx, ny) for cx, cy, nx, ny, nz in _normals(shell.meshes["wall_ext"])
             if abs(nz) < 0.5 and abs(nx * (cx - centre[0]) + ny * (cy - centre[1])) > 1.0]
    assert outer and all((cx - centre[0]) * nx + (cy - centre[1]) * ny > 0 for cx, cy, nx, ny in outer)


def test_a_cutaway_lowers_the_walls_to_the_cut_height():
    plan = one_wall()
    plan.cutaway = 1.2
    assert total_volume(bare(plan, extend_ends=False)) == pytest.approx(4.0 * 0.2 * 1.2)


def test_a_cutaway_keeps_the_part_of_an_opening_below_the_cut():
    plan = one_wall()
    plan.cutaway = 1.2
    plan.window("w", 1.0, width=1.2, sill=0.9, height=1.2)
    walls = sum(m.volume() for k, m in bare(plan, extend_ends=False).meshes.items() if k.startswith("wall"))
    assert walls == pytest.approx(4.0 * 0.2 * 1.2 - 1.2 * 0.3 * 0.2, abs=1e-6)          # il reste 30 cm de vide sous la coupe


def test_an_opening_entirely_above_the_cut_disappears_with_its_fittings():
    plan = one_wall()
    plan.cutaway = 0.8
    plan.window("w", 1.0, width=1.2, sill=0.9, height=1.2)
    shell = bare(plan, extend_ends=False)
    assert "glass" not in shell.meshes and "trim" not in shell.meshes
    assert total_volume(shell) == pytest.approx(4.0 * 0.2 * 0.8)


def test_the_cutaway_is_validated_and_round_trips():
    plan = one_wall()
    plan.cutaway = 5.0
    with pytest.raises(Exception):
        plan.validate()
    plan.cutaway = 1.2
    assert Plan.from_dict(plan.to_dict()).cutaway == 1.2 and Plan.from_dict(one_wall().to_dict()).cutaway is None
    assert plan.wall_height == 1.2 and one_wall().wall_height == 2.7
