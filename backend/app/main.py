import os, re, shutil, uuid
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from .schemas import ChatRequest, ChatResponse, DesignSpec, GenerateResponse
from .ai_service import chat
from .cad_engine import export_model

load_dotenv(Path(__file__).parents[1]/".env")
ROOT=Path(__file__).parents[1]/"generated"; MODELS={}
LATEST_PROPOSAL: DesignSpec | None = None
app=FastAPI(title="Forge AI CAD API",version="0.1.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5174","http://127.0.0.1:5174"],allow_methods=["*"],allow_headers=["*"])

@app.get("/api/health")
def health(): return {"status":"ok","ai_enabled":bool(os.getenv("OPENAI_API_KEY")),"cad_engine":"CadQuery","schema_version":"2.0","design_modes":["sketch_2d","part_3d","assembly"]}

@app.post("/api/chat",response_model=ChatResponse)
def ai_chat(req: ChatRequest):
    global LATEST_PROPOSAL
    try:
        command=req.message.strip().lower()
        confirmation=bool(re.fullmatch(r"(?:yes[, ]+|please\s+)?(?:design|generate|proceed|build)(?:\s+(?:it|this))?[.!]?",command)) or command in {"go ahead","approved"}
        if confirmation and req.current_spec is None and LATEST_PROPOSAL is not None:
            req=req.model_copy(update={"current_spec":LATEST_PROPOSAL})
        response=chat(req)
        if response.spec is not None:
            LATEST_PROPOSAL=response.spec
        return response
    except Exception as e: raise HTTPException(502,f"AI request failed: {e}")

@app.post("/api/models",response_model=GenerateResponse)
def generate(spec: DesignSpec):
    model_id=uuid.uuid4().hex[:12]; folder=ROOT/model_id
    try:
        shape,bb,body_count=export_model(spec,folder); MODELS[model_id]=spec
        dxf_url=f"/api/models/{model_id}/dxf" if (folder/"model.dxf").exists() else None
        return GenerateResponse(model_id=model_id,spec=spec,preview_url=f"/api/models/{model_id}/preview",step_url=f"/api/models/{model_id}/step",stl_url=f"/api/models/{model_id}/stl",dxf_url=dxf_url,volume_mm3=round(shape.val().Volume(),2),bounding_box=bb,body_count=body_count,feature_count=len(spec.features)+len(spec.sketch))
    except Exception as e:
        shutil.rmtree(folder,ignore_errors=True); raise HTTPException(422,f"CAD generation failed: {e}")

def model_file(model_id,name,media):
    path=ROOT/model_id/name
    if not path.exists(): raise HTTPException(404,"Model not found")
    return FileResponse(path,media_type=media,filename=f"forge-{model_id}.{name.split('.')[-1]}")
@app.get("/api/models/{model_id}/preview")
def preview(model_id:str): return model_file(model_id,"model.stl","model/stl")
@app.get("/api/models/{model_id}/step")
def step(model_id:str): return model_file(model_id,"model.step","application/step")
@app.get("/api/models/{model_id}/stl")
def stl(model_id:str): return model_file(model_id,"model.stl","model/stl")
@app.get("/api/models/{model_id}/dxf")
def dxf(model_id:str): return model_file(model_id,"model.dxf","application/dxf")
