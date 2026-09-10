from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Vector3(BaseModel):
    x: float = 0
    y: float = 0
    z: float = 0


class Point2(BaseModel):
    x: float
    y: float


class ProfileSpec(BaseModel):
    kind: Literal["rectangle", "circle", "polygon", "slot"]
    width: float | None = Field(None, gt=0)
    height: float | None = Field(None, gt=0)
    diameter: float | None = Field(None, gt=0)
    length: float | None = Field(None, gt=0)
    points: list[Point2] = Field(default_factory=list)
    corner_radius: float = Field(0, ge=0)

    @model_validator(mode="after")
    def validate_profile(self):
        if self.kind == "rectangle" and (not self.width or not self.height):
            raise ValueError("rectangle profile requires width and height")
        if self.kind == "circle" and not self.diameter:
            raise ValueError("circle profile requires diameter")
        if self.kind == "polygon" and len(self.points) < 3:
            raise ValueError("polygon profile requires at least three points")
        if self.kind == "slot" and (not self.length or not self.width or self.length < self.width):
            raise ValueError("slot profile requires length >= width")
        return self


class SketchEntity(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    name: str
    operation: Literal["add", "cut"] = "add"
    profile: ProfileSpec
    x: float = 0
    y: float = 0
    rotation: float = 0


class FeatureSpec(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    name: str
    body_id: str = Field("main", pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    operation: Literal["add", "cut", "intersect"] = "add"
    shape: Literal[
        "box", "cylinder", "cone", "sphere", "torus",
        "extruded_profile", "spur_gear", "text"
    ]
    position: Vector3 = Field(default_factory=Vector3)
    rotation: Vector3 = Field(default_factory=Vector3)
    axis: Literal["x", "y", "z"] = "z"
    length: float | None = Field(None, gt=0)
    width: float | None = Field(None, gt=0)
    height: float | None = Field(None, gt=0)
    diameter: float | None = Field(None, gt=0)
    diameter2: float | None = Field(None, ge=0)
    inner_diameter: float | None = Field(None, gt=0)
    profile: ProfileSpec | None = None
    teeth: int | None = Field(None, ge=6, le=120)
    module: float | None = Field(None, gt=0, le=20)
    text: str | None = Field(None, min_length=1, max_length=40)
    font_size: float | None = Field(None, gt=1, le=100)
    fillet_radius: float = Field(0, ge=0)

    @model_validator(mode="after")
    def validate_shape_dimensions(self):
        if self.shape == "box" and (not self.length or not self.width or not self.height):
            raise ValueError(f"feature {self.id}: box requires length, width, and height")
        if self.shape == "cylinder" and (not self.diameter or not self.height):
            raise ValueError(f"feature {self.id}: cylinder requires diameter and height")
        if self.shape == "cone" and (not self.diameter or self.diameter2 is None or not self.height):
            raise ValueError(f"feature {self.id}: cone requires diameter, diameter2, and height")
        if self.shape == "sphere" and not self.diameter:
            raise ValueError(f"feature {self.id}: sphere requires diameter")
        if self.shape == "torus" and (not self.diameter or not self.diameter2):
            raise ValueError(f"feature {self.id}: torus requires major diameter and tube diameter")
        if self.shape == "extruded_profile" and (not self.profile or not self.height):
            raise ValueError(f"feature {self.id}: extruded_profile requires profile and height")
        if self.shape == "spur_gear" and (not self.teeth or not self.module or not self.height):
            raise ValueError(f"feature {self.id}: spur_gear requires teeth, module, and height")
        if self.shape == "text" and (not self.text or not self.font_size or not self.height):
            raise ValueError(f"feature {self.id}: text requires text, font_size, and height")
        if self.inner_diameter and self.diameter and self.inner_diameter >= self.diameter:
            raise ValueError(f"feature {self.id}: inner diameter must be smaller than diameter")
        return self


class DesignSpec(BaseModel):
    schema_version: Literal["2.0"] = "2.0"
    name: str = Field("Untitled Design", min_length=1, max_length=80)
    mode: Literal["sketch_2d", "part_3d", "assembly"] = "part_3d"
    units: Literal["mm"] = "mm"
    description: str = ""
    features: list[FeatureSpec] = Field(default_factory=list, max_length=160)
    sketch: list[SketchEntity] = Field(default_factory=list, max_length=160)
    design_summary: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    material: Literal["aluminum", "steel", "plastic", "brass", "wood", "generic"] = "generic"
    color: str = Field("#8fa8bd", pattern=r"^#[0-9A-Fa-f]{6}$")
    revision: int = Field(1, ge=1)

    @model_validator(mode="after")
    def validate_design(self):
        if self.mode == "sketch_2d" and not self.sketch:
            raise ValueError("a 2D design requires at least one sketch entity")
        if self.mode != "sketch_2d" and not self.features:
            raise ValueError("a 3D design requires at least one feature")
        feature_ids=[feature.id for feature in self.features]
        sketch_ids=[entity.id for entity in self.sketch]
        if len(feature_ids) != len(set(feature_ids)):
            raise ValueError("feature ids must be unique")
        if len(sketch_ids) != len(set(sketch_ids)):
            raise ValueError("sketch entity ids must be unique")
        first_by_body={}
        for feature in self.features:
            first_by_body.setdefault(feature.body_id, feature.operation)
        invalid=[body for body,operation in first_by_body.items() if operation != "add"]
        if invalid:
            raise ValueError(f"the first feature of each body must use add: {', '.join(invalid)}")
        if self.sketch and self.sketch[0].operation != "add":
            raise ValueError("the first sketch entity must use add")
        return self


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    current_spec: DesignSpec | None = None


class ChatResponse(BaseModel):
    status: Literal["proposal", "ready", "clarification"]
    message: str
    spec: DesignSpec | None = None
    defaults: list[str] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    model_id: str
    spec: DesignSpec
    preview_url: str
    step_url: str
    stl_url: str
    dxf_url: str | None = None
    volume_mm3: float
    bounding_box: dict[str, float]
    body_count: int
    feature_count: int
