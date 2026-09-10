from pathlib import Path

import pytest

from app.ai_service import demo_parse
from app.cad_engine import export_model
from app.schemas import ChatRequest, DesignSpec


def test_general_boolean_part_exports(tmp_path: Path):
    spec=DesignSpec(name="Bearing Block",mode="part_3d",features=[
        {"id":"body","name":"Block","shape":"box","length":80,"width":50,"height":30,"fillet_radius":3},
        {"id":"bore","name":"Bearing bore","operation":"cut","shape":"cylinder","diameter":20,"height":80,"axis":"y"},
    ])
    shape,bounds,bodies=export_model(spec,tmp_path)
    assert shape.val().Volume() > 0
    assert bounds["length"] == pytest.approx(80,abs=.01)
    assert bodies == 1
    assert (tmp_path/"model.step").stat().st_size > 1000
    assert (tmp_path/"model.stl").stat().st_size > 100


def test_multi_body_gearbox(tmp_path: Path):
    response=demo_parse(ChatRequest(message="Design a 200 x 140 x 110 mm industrial gearbox with gears and shafts"))
    assert response.status == "proposal"
    assert response.spec.mode == "assembly"
    shape,_,bodies=export_model(response.spec,tmp_path)
    assert shape.val().Volume() > 0
    assert bodies >= 5
    assert any(feature.shape == "spur_gear" for feature in response.spec.features)


def test_2d_sketch_exports_dxf(tmp_path: Path):
    response=demo_parse(ChatRequest(message="Create a 2D 120 x 80 x 5 mm plate sketch with four holes"))
    assert response.spec.mode == "sketch_2d"
    _,bounds,_=export_model(response.spec,tmp_path)
    assert bounds["height"] == pytest.approx(1,abs=.01)
    assert (tmp_path/"model.dxf").stat().st_size > 1000


def test_first_body_feature_must_add():
    with pytest.raises(ValueError):
        DesignSpec(name="Invalid",features=[{"id":"hole","name":"Hole","operation":"cut","shape":"cylinder","diameter":4,"height":10}])


def test_prompt_edit_preserves_feature_tree():
    proposal=demo_parse(ChatRequest(message="Create a shaft 20 diameter and 100 long"))
    count=len(proposal.spec.features)
    edit=demo_parse(ChatRequest(message="change diameter to 25",current_spec=proposal.spec))
    assert edit.status == "proposal"
    assert edit.spec.revision == 2
    assert len(edit.spec.features) == count
    approved=demo_parse(ChatRequest(message="design",current_spec=edit.spec))
    assert approved.status == "ready"


def test_supported_primitive_family(tmp_path: Path):
    spec=DesignSpec(name="Primitive Family",mode="assembly",features=[
        {"id":"cone","name":"Cone","body_id":"cone","shape":"cone","diameter":30,"diameter2":12,"height":40,"position":{"x":-80}},
        {"id":"sphere","name":"Sphere","body_id":"sphere","shape":"sphere","diameter":30,"position":{"x":-35}},
        {"id":"torus","name":"Torus","body_id":"torus","shape":"torus","diameter":32,"diameter2":8,"position":{"x":10}},
        {"id":"slot","name":"Slot prism","body_id":"slot","shape":"extruded_profile","height":8,"profile":{"kind":"slot","length":40,"width":14},"position":{"x":55}},
        {"id":"label","name":"Text","body_id":"label","shape":"text","text":"CAD","font_size":12,"height":2,"position":{"x":100}},
    ])
    shape,_,bodies=export_model(spec,tmp_path)
    assert shape.val().isValid()
    assert bodies == 5
