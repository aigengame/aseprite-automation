"""Small declared preparation inputs shared by the verification tiers."""


def specification(mode="rgba"):
    return {
        "alpha_threshold": 128,
        "crop": {
            "kind": "rectangle",
            "rectangle": {"x": 0, "y": 0, "width": 3, "height": 2},
        },
        "resize": {"kind": "size", "width": 3, "height": 2},
        "rounding": "nearest-away-from-zero",
        "palette": {
            "entries": [
                {"red": 0, "green": 0, "blue": 0, "alpha": 0},
                {"red": 180, "green": 70, "blue": 30, "alpha": 255},
                {"red": 30, "green": 90, "blue": 180, "alpha": 255},
            ],
            "transparent_index": 0,
        },
        "mapping": {
            "rgb_map_algorithm": "octree",
            "color_best_fit_criteria": "rgb",
            "dithering": "none",
        },
        "canvas": {"width": 5, "height": 4},
        "anchors": [{"name": "foot", "x": 1, "y": 2}],
        "alignment": {"primary_anchor": "foot", "position": {"x": 2, "y": 3}},
        "output_mode": mode,
    }
