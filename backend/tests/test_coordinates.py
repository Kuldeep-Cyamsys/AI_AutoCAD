import pytest
from app.cad_engine import _make_feature
from app.schemas import FeatureSpec


@pytest.mark.parametrize("position", [{"x": 0, "y": 0, "z": 0}, {"x": 40, "y": -20, "z": 14}])
def test_box_position_is_center(position):
    shape = _make_feature(FeatureSpec(id="base", name="Base", shape="box", length=210, width=110, height=28, position=position))
    bounds = shape.val().BoundingBox()
    for axis, size in [("x", 210), ("y", 110), ("z", 28)]:
        assert getattr(bounds, axis + "min") == pytest.approx(position[axis] - size / 2)
        assert getattr(bounds, axis + "max") == pytest.approx(position[axis] + size / 2)
