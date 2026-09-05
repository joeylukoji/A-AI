from PIL import Image

from raster import evaluate_pair, mae_norm, wall_iou


def test_identical_images_perfect_scores():
    img = Image.new("L", (8, 8), 255)
    ev = evaluate_pair(img, img)
    assert ev["mae"] == 0.0
    assert ev["wall_iou"] == 0.0  # no dark walls


def test_wall_iou_overlap():
    a = Image.new("L", (4, 1), 255)
    b = Image.new("L", (4, 1), 255)
    a.putpixel((0, 0), 0)
    a.putpixel((1, 0), 0)
    b.putpixel((1, 0), 0)
    b.putpixel((2, 0), 0)
    assert 0.3 < wall_iou(a, b) < 0.5
    assert mae_norm(a, a) == 0.0
