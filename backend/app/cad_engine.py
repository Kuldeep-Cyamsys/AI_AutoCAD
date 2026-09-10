import math
from pathlib import Path

import cadquery as cq
import ezdxf

from .schemas import DesignSpec, FeatureSpec, ProfileSpec, SketchEntity


def _profile(workplane: cq.Workplane, profile: ProfileSpec):
    if profile.kind == "rectangle":
        result=workplane.rect(profile.width,profile.height)
        if profile.corner_radius:
            try: result=result.vertices().fillet2D(profile.corner_radius)
            except Exception: pass
        return result
    if profile.kind == "circle":
        return workplane.circle(profile.diameter/2)
    if profile.kind == "polygon":
        points=[(point.x,point.y) for point in profile.points]
        return workplane.polyline(points).close()
    return workplane.slot2D(profile.length,profile.width)


def _orient_and_place(shape: cq.Workplane, feature: FeatureSpec):
    if feature.axis == "x":
        shape=shape.rotate((0,0,0),(0,1,0),90)
    elif feature.axis == "y":
        shape=shape.rotate((0,0,0),(1,0,0),-90)
    for axis,angle in (((1,0,0),feature.rotation.x),((0,1,0),feature.rotation.y),((0,0,1),feature.rotation.z)):
        if angle: shape=shape.rotate((0,0,0),axis,angle)
    return shape.translate((feature.position.x,feature.position.y,feature.position.z))


def _spur_gear(feature: FeatureSpec):
    pitch_radius=feature.module*feature.teeth/2
    root_radius=max(feature.module,feature.module*(feature.teeth-2.5)/2)
    outer_radius=feature.module*(feature.teeth+2)/2
    thickness=feature.height
    gear=cq.Workplane("XY").circle(root_radius).extrude(thickness/2,both=True)
    tooth_depth=outer_radius-root_radius+feature.module*.35
    tooth_width=max(feature.module*1.35,2*math.pi*pitch_radius/feature.teeth*.48)
    tooth_center=(outer_radius+root_radius)/2-feature.module*.1
    for index in range(feature.teeth):
        angle=360*index/feature.teeth
        tooth=(cq.Workplane("XY").box(tooth_depth,tooth_width,thickness)
               .translate((tooth_center,0,0)).rotate((0,0,0),(0,0,1),angle))
        gear=gear.union(tooth)
    if feature.inner_diameter:
        bore=cq.Workplane("XY").circle(feature.inner_diameter/2).extrude(thickness,both=True)
        gear=gear.cut(bore)
    return gear


def _make_feature(feature: FeatureSpec):
    if feature.shape == "box":
        shape=cq.Workplane("XY").box(feature.length,feature.width,feature.height)
    elif feature.shape == "cylinder":
        shape=cq.Workplane("XY").circle(feature.diameter/2).extrude(feature.height/2,both=True)
        if feature.inner_diameter:
            shape=shape.cut(cq.Workplane("XY").circle(feature.inner_diameter/2).extrude(feature.height,both=True))
    elif feature.shape == "cone":
        solid=cq.Solid.makeCone(feature.diameter/2,feature.diameter2/2,feature.height,cq.Vector(0,0,-feature.height/2))
        shape=cq.Workplane(obj=solid)
    elif feature.shape == "sphere":
        shape=cq.Workplane("XY").sphere(feature.diameter/2)
    elif feature.shape == "torus":
        shape=cq.Workplane(obj=cq.Solid.makeTorus(feature.diameter/2,feature.diameter2/2))
    elif feature.shape == "extruded_profile":
        shape=_profile(cq.Workplane("XY"),feature.profile).extrude(feature.height/2,both=True)
    elif feature.shape == "spur_gear":
        shape=_spur_gear(feature)
    else:
        shape=(cq.Workplane("XY").text(feature.text,feature.font_size,feature.height,combine=True)
               .translate((0,0,-feature.height/2)))
    if feature.fillet_radius:
        radius=feature.fillet_radius
        dimensions=[value for value in (feature.length,feature.width,feature.height,feature.diameter) if value]
        if dimensions: radius=min(radius,min(dimensions)*.45)
        try: shape=shape.edges().fillet(radius)
        except Exception:
            try: shape=shape.edges("|Z").fillet(radius)
            except Exception: pass
    return _orient_and_place(shape,feature)


def _sketch_solid(entity: SketchEntity, thickness=1.0):
    workplane=_profile(cq.Workplane("XY"),entity.profile).extrude(thickness/2,both=True)
    if entity.rotation:
        workplane=workplane.rotate((0,0,0),(0,0,1),entity.rotation)
    return workplane.translate((entity.x,entity.y,0))


def build(spec: DesignSpec):
    if spec.mode == "sketch_2d":
        result=None
        for entity in spec.sketch:
            geometry=_sketch_solid(entity)
            if result is None: result=geometry
            elif entity.operation == "add": result=result.union(geometry)
            else: result=result.cut(geometry)
        return result,{"sketch":result}

    bodies: dict[str,cq.Workplane]={}
    for feature in spec.features:
        geometry=_make_feature(feature)
        current=bodies.get(feature.body_id)
        if current is None:
            bodies[feature.body_id]=geometry
        elif feature.operation == "add":
            bodies[feature.body_id]=current.union(geometry)
        elif feature.operation == "cut":
            bodies[feature.body_id]=current.cut(geometry)
        else:
            bodies[feature.body_id]=current.intersect(geometry)
    solids=[body.val() for body in bodies.values()]
    result=cq.Workplane(obj=solids[0] if len(solids)==1 else cq.Compound.makeCompound(solids))
    return result,bodies


def _rotate_point(x,y,angle):
    radians=math.radians(angle); cosine=math.cos(radians); sine=math.sin(radians)
    return x*cosine-y*sine,x*sine+y*cosine


def export_dxf(spec: DesignSpec,path: Path):
    document=ezdxf.new("R2010"); document.units=ezdxf.units.MM
    document.layers.add("OUTLINE",color=3); document.layers.add("CUTOUT",color=1)
    modelspace=document.modelspace()
    for entity in spec.sketch:
        profile=entity.profile; layer="OUTLINE" if entity.operation == "add" else "CUTOUT"
        attrs={"layer":layer}
        if profile.kind == "circle":
            modelspace.add_circle((entity.x,entity.y),profile.diameter/2,dxfattribs=attrs)
            continue
        if profile.kind == "rectangle":
            points=[(-profile.width/2,-profile.height/2),(profile.width/2,-profile.height/2),(profile.width/2,profile.height/2),(-profile.width/2,profile.height/2)]
        elif profile.kind == "polygon":
            points=[(point.x,point.y) for point in profile.points]
        else:
            radius=profile.width/2; straight=(profile.length-profile.width)/2
            points=[]
            for index in range(9):
                angle=-90+180*index/8; points.append((straight+radius*math.cos(math.radians(angle)),radius*math.sin(math.radians(angle))))
            for index in range(9):
                angle=90+180*index/8; points.append((-straight+radius*math.cos(math.radians(angle)),radius*math.sin(math.radians(angle))))
        transformed=[]
        for x,y in points:
            rx,ry=_rotate_point(x,y,entity.rotation); transformed.append((rx+entity.x,ry+entity.y))
        modelspace.add_lwpolyline(transformed,close=True,dxfattribs=attrs)
    document.saveas(path)


def export_model(spec: DesignSpec,folder: Path):
    shape,bodies=build(spec); folder.mkdir(parents=True,exist_ok=True)
    if shape is None or shape.val().Volume() <= 0:
        raise ValueError("design produced no solid geometry")
    if not shape.val().isValid():
        raise ValueError("design produced invalid CAD geometry")
    cq.exporters.export(shape,str(folder/"model.step"))
    cq.exporters.export(shape,str(folder/"model.stl"),tolerance=0.08,angularTolerance=0.1)
    if spec.mode == "sketch_2d": export_dxf(spec,folder/"model.dxf")
    bounds=shape.val().BoundingBox()
    return shape,{"length":round(bounds.xlen,3),"width":round(bounds.ylen,3),"height":round(bounds.zlen,3)},len(bodies)
