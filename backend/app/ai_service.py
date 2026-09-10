import json
import os
import re

from openai import OpenAI
from pydantic import ValidationError

from .schemas import ChatRequest, ChatResponse, DesignSpec


def is_confirmation(text: str):
    value=text.strip().lower()
    return bool(re.fullmatch(r"(?:yes[, ]+|please\s+)?(?:design|generate|proceed|build|create)(?:\s+(?:it|this|the design))?[.!]?",value)) or value in {"go ahead","approved","looks good"}


def _dimensions(text,default):
    match=re.search(r"(\d+(?:\.\d+)?)\s*(?:mm)?\s*[x×]\s*(\d+(?:\.\d+)?)\s*(?:mm)?\s*[x×]\s*(\d+(?:\.\d+)?)\s*mm",text,re.I)
    return [float(value) for value in match.groups()] if match else list(default)


def _gearbox(text):
    length,width,height=_dimensions(text,(180,120,100)); wall=max(5,round(min(length,width,height)*.05,1))
    features=[
      {"id":"housing_outer","name":"Housing outer shell","body_id":"housing","operation":"add","shape":"box","length":length,"width":width,"height":height,"fillet_radius":min(6,wall)},
      {"id":"housing_cavity","name":"Internal drivetrain clearance","body_id":"housing","operation":"cut","shape":"box","length":length-2*wall,"width":width-2*wall,"height":height-wall,"position":{"z":wall/2}},
      {"id":"input_bore","name":"Input bearing bore","body_id":"housing","operation":"cut","shape":"cylinder","diameter":35,"height":wall*4,"axis":"x","position":{"x":-length/2}},
      {"id":"output_bore","name":"Output bearing bore","body_id":"housing","operation":"cut","shape":"cylinder","diameter":45,"height":wall*4,"axis":"x","position":{"x":length/2}},
      {"id":"service_cover","name":"Removable service cover","body_id":"cover","operation":"add","shape":"box","length":length,"width":width,"height":wall,"position":{"z":height/2+wall*1.5},"fillet_radius":min(4,wall/2)},
      {"id":"input_shaft","name":"Input shaft","body_id":"input_shaft","operation":"add","shape":"cylinder","diameter":20,"height":length*.72,"axis":"x","position":{"z":-height*.12}},
      {"id":"output_shaft","name":"Output shaft","body_id":"output_shaft","operation":"add","shape":"cylinder","diameter":28,"height":length*.72,"axis":"x","position":{"z":height*.16}},
      {"id":"pinion","name":"Input spur gear","body_id":"pinion","operation":"add","shape":"spur_gear","teeth":18,"module":2.5,"height":18,"inner_diameter":20,"axis":"x","position":{"x":-length*.1,"z":-height*.12}},
      {"id":"driven_gear","name":"Driven spur gear","body_id":"driven_gear","operation":"add","shape":"spur_gear","teeth":32,"module":2.5,"height":20,"inner_diameter":28,"axis":"x","position":{"x":length*.1,"z":height*.16}},
    ]
    summary=["multi-body gearbox concept with a hollow serviceable housing","two aligned shafts and two meshing conceptual spur gears","input/output bearing bores","separate raised service cover","dimensions and tooth geometry remain parametric and editable"]
    assumptions=["Concept gears use deterministic straight teeth rather than a production involute tooth profile.","Bearing seats, seals, lubrication channels, tolerances, and load ratings require detailed engineering validation."]
    return DesignSpec(name="Industrial Gearbox Concept",mode="assembly",description="Two-shaft gearbox concept generated from safe parametric features",features=features,design_summary=summary,assumptions=assumptions,material="steel",color="#71818b")


def _enclosure(text):
    length,width,height=_dimensions(text,(120,80,40)); wall=2.5
    features=[
      {"id":"outer","name":"Outer body","body_id":"body","shape":"box","length":length,"width":width,"height":height,"fillet_radius":4},
      {"id":"cavity","name":"Internal cavity","body_id":"body","operation":"cut","shape":"box","length":length-2*wall,"width":width-2*wall,"height":height-wall,"position":{"z":wall/2}},
      {"id":"lid","name":"Removable lid","body_id":"lid","shape":"box","length":length,"width":width,"height":wall,"position":{"z":height/2+wall*1.5},"fillet_radius":2},
    ]
    if any(word in text.lower() for word in ("wire","cable")):
        features.append({"id":"cable_port","name":"Cable port","body_id":"body","operation":"cut","shape":"cylinder","diameter":10,"height":wall*4,"axis":"y","position":{"y":-width/2}})
    return DesignSpec(name="Custom Enclosure",mode="assembly",description="Hollow enclosure with a separate lid",features=features,design_summary=["rounded hollow enclosure","separate removable lid","parametric wall and envelope dimensions"],assumptions=["Default wall thickness is 2.5 mm."],material="plastic",color="#5592aa")


def _plate_or_sketch(text,sketch=False):
    length,width,thickness=_dimensions(text,(100,60,5)); holes=4 if "four" in text.lower() or "4" in text else 2
    if sketch:
        entities=[{"id":"outline","name":"Plate outline","operation":"add","profile":{"kind":"rectangle","width":length,"height":width,"corner_radius":3}}]
        points=[(-length*.35,-width*.3),(length*.35,-width*.3),(length*.35,width*.3),(-length*.35,width*.3)][:holes]
        entities += [{"id":f"hole_{i+1}","name":f"Hole {i+1}","operation":"cut","profile":{"kind":"circle","diameter":6},"x":x,"y":y} for i,(x,y) in enumerate(points)]
        return DesignSpec(name="2D Plate Profile",mode="sketch_2d",description="Dimensioned plate outline and cutouts",sketch=entities,design_summary=[f"{length:g} × {width:g} mm plate profile",f"{holes} circular cutouts","DXF-ready 2D geometry"],assumptions=["Hole diameter defaults to 6 mm."],material="steel",color="#8797a0")
    features=[{"id":"plate","name":"Plate body","shape":"box","length":length,"width":width,"height":thickness,"fillet_radius":3}]
    points=[(-length*.35,-width*.3),(length*.35,-width*.3),(length*.35,width*.3),(-length*.35,width*.3)][:holes]
    features += [{"id":f"hole_{i+1}","name":f"Mounting hole {i+1}","operation":"cut","shape":"cylinder","diameter":6,"height":thickness*3,"position":{"x":x,"y":y}} for i,(x,y) in enumerate(points)]
    return DesignSpec(name="Mounting Plate",mode="part_3d",features=features,design_summary=["filleted plate","symmetric mounting-hole pattern"],assumptions=["Hole diameter defaults to 6 mm."],material="steel",color="#8797a0")


def _simple_part(text):
    lower=text.lower(); numbers=[float(value) for value in re.findall(r"\d+(?:\.\d+)?",text)]
    if "gear" in lower:
        teeth=int(numbers[0]) if numbers else 24; module=numbers[1] if len(numbers)>1 else 2
        feature={"id":"gear","name":"Spur gear","shape":"spur_gear","teeth":teeth,"module":module,"height":10,"inner_diameter":8}
        return DesignSpec(name="Spur Gear",mode="part_3d",features=[feature],design_summary=[f"{teeth}-tooth conceptual spur gear",f"module {module:g}","central shaft bore"],assumptions=["Straight deterministic teeth are used; production involute geometry requires a dedicated gear library."],material="steel")
    if any(word in lower for word in ("shaft","rod","pin")):
        diameter=numbers[0] if numbers else 20; length=numbers[1] if len(numbers)>1 else 100
        return DesignSpec(name="Stepped Shaft",mode="part_3d",features=[{"id":"shaft","name":"Main shaft","shape":"cylinder","diameter":diameter,"height":length,"axis":"x"}],design_summary=[f"Ø{diameter:g} × {length:g} mm shaft"],material="steel")
    return None


def demo_parse(request: ChatRequest):
    text=request.message.strip(); lower=text.lower()
    if request.current_spec and is_confirmation(text):
        return ChatResponse(status="ready",message="Design approved. Building the validated feature tree now.",spec=request.current_spec)
    if request.current_spec:
        current=request.current_spec.model_copy(deep=True); changed=[]
        for field,label in (("length","length"),("width","width"),("height","height"),("diameter","diameter")):
            match=re.search(rf"{label}(?:\s+to|\s*=|\s+is)?\s*(\d+(?:\.\d+)?)",lower)
            if match:
                for feature in current.features:
                    if getattr(feature,field,None) is not None:
                        setattr(feature,field,float(match.group(1))); changed.append(f"{feature.name} {label}")
                        break
        if changed:
            current.revision+=1
            return ChatResponse(status="proposal",message="I updated "+", ".join(changed)+" and preserved the remaining feature tree. Reply ‘design’ to rebuild revision "+str(current.revision)+".",spec=current)
    design=None
    if any(word in lower for word in ("gearbox","gear box","gear train","reducer")): design=_gearbox(text)
    elif any(word in lower for word in ("2d","sketch","drawing","dxf","profile")): design=_plate_or_sketch(text,True)
    elif any(word in lower for word in ("plate","flange")): design=_plate_or_sketch(text)
    elif any(word in lower for word in ("enclosure","housing","case","box")): design=_enclosure(text)
    else: design=_simple_part(text)
    if design:
        return ChatResponse(status="proposal",message="Proposed construction: "+"; ".join(design.design_summary)+". Review the named features and assumptions, request changes, or reply ‘design’ to build it.",spec=design,defaults=design.assumptions)
    return ChatResponse(status="clarification",message="Describe the object’s purpose or overall form. Dimensions are optional—I can propose sensible defaults. In offline mode I can interpret plates, sketches, shafts, gears, gearboxes, and enclosures; connect OpenAI for broader feature composition.")


def _validate_content(content: str):
    return ChatResponse.model_validate(json.loads(content))


def chat(request: ChatRequest):
    if request.current_spec and is_confirmation(request.message):
        return ChatResponse(status="ready",message=f"Revision {request.current_spec.revision} approved. Building the validated CAD feature tree now.",spec=request.current_spec)
    if not os.getenv("OPENAI_API_KEY"):
        return demo_parse(request)

    schema=ChatResponse.model_json_schema()
    system="""You are a general parametric CAD design planner. Analyze the user's object instead of forcing it into an enclosure. Produce a safe, structured feature tree for real CadQuery geometry.

WORKFLOW:
1. On a new design request, return status='proposal', explain the construction, choose reasonable defaults for missing noncritical dimensions, and provide a complete valid spec.
2. Ask clarification only when the intended physical object or scale truly cannot be inferred. Do not ask the user to enumerate schema fields.
3. Do not generate immediately. status='ready' is reserved for explicit approval such as 'design' or 'generate'.
4. For edits, modify only the requested named features, preserve all other features/body IDs, increment revision, and return a new proposal.

CAPABILITIES:
- 3D primitives: box, cylinder/tube, cone, sphere, torus, extruded rectangle/circle/polygon/slot, conceptual spur gear, and extruded text.
- Boolean add/cut/intersect in ordered named features.
- Multiple body_id values for assemblies and separate parts. Position and rotate each feature; axis controls axial shapes.
- 2D sketches with additive outlines and cut profiles; these export as DXF plus a thin 3D preview.
- Compose complex objects from multiple features. When exact organic surfaces or production-standard mechanisms are impossible, propose a recognizable parametric concept and disclose the approximation in assumptions. Never silently turn unrelated objects into enclosures.
- Never emit Python, code, or unsupported shape names. Keep dimensions in millimeters. The first feature for every body must be operation='add'. IDs must be unique identifiers beginning with a letter.

Return only JSON matching this schema: """+json.dumps(schema)
    messages=[{"role":"system","content":system},{"role":"user","content":json.dumps(request.model_dump(mode="json"))}]
    client=OpenAI(); model=os.getenv("OPENAI_MODEL","gpt-4.1-mini")
    response=client.chat.completions.create(model=model,response_format={"type":"json_object"},messages=messages)
    content=response.choices[0].message.content
    try:
        result=_validate_content(content)
    except (ValidationError,ValueError,TypeError) as error:
        messages += [{"role":"assistant","content":content},{"role":"user","content":"The feature tree failed validation. Correct it and return the complete JSON again. Error: "+str(error)}]
        retry=client.chat.completions.create(model=model,response_format={"type":"json_object"},messages=messages)
        result=_validate_content(retry.choices[0].message.content)
    return result
