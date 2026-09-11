# Forge AI — General Parametric CAD Studio

Forge AI is a local React + FastAPI prototype that converts natural-language design intent into a validated, editable CAD feature tree. CadQuery executes the tree deterministically; the AI never emits or executes Python code. The interactive browser preview, STEP export, and STL export all come from the same CAD geometry. Native 2D designs also export as DXF.

## Prerequisites

For implementation changes, setup history, and verification limits since the initial clone, see [Changes Since Cloning](CHANGES_SINCE_CLONE.md).

- Windows 10/11 with PowerShell
- Python 3.10
- Node.js 20 or newer

## Install and run

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Set-Location frontend
npm.cmd install
Set-Location ..
```

Start two PowerShell windows:

```powershell
.\start-backend.ps1
```

```powershell
.\start-frontend.ps1
```

Open http://localhost:5174. API documentation is at http://127.0.0.1:8010/docs.

If PowerShell blocks scripts:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-backend.ps1
```

## OpenAI configuration

Copy `backend/.env.example` to `backend/.env` and set:

```dotenv
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
```

The API key remains on the Python backend. Without a key, a smaller deterministic demo interpreter supports common plates, shafts, gears, gearboxes, enclosures, and 2D profiles.

## Design workflow

1. Describe a part, mechanism, assembly, or 2D drawing. Exact dimensions are optional.
2. The assistant analyzes the object and proposes named bodies, features, dimensions, and assumptions.
3. Review the feature tree or request changes in chat.
4. Reply `design` or press **Approve & build**.
5. Rotate, zoom, and pan the generated model.
6. Edit feature dimensions directly or use prompts such as `increase the main shaft diameter to 30 mm`.
7. Rebuild and export STEP/STL, plus DXF for 2D sketches.

Example prompts:

```text
Design a V-belt pulley with 80 mm outer diameter, 20 mm bore, two flanges, and a central groove.
```

```text
Create a 2D DXF mounting flange: 120 by 80 mm rounded rectangle, four 8 mm corner holes, and a 40 mm center opening.
```

```text
Design a two-shaft gearbox with a serviceable housing, input and output shafts, bearing bores, and two spur gears.
```

## Supported feature tree

- Modes: 2D sketch, 3D part, and multi-body assembly
- Solids: box, cylinder/tube, cone, sphere, torus, extruded profile, text, and conceptual spur gear
- Profiles: rectangle, circle, polygon, and slot
- Operations: add, cut, and intersect
- Feature transforms: XYZ position, XYZ rotation, and axial orientation
- Named bodies and ordered named features
- Optional edge fillets
- Prompt-based revisions that preserve unaffected features
- STEP, STL, and DXF export

## Verification

```powershell
$env:PYTHONPATH="backend"
backend\.venv\Scripts\python.exe -m pytest backend\tests
Set-Location frontend
npm.cmd run build
```

Generated files are stored under `backend/generated/` and ignored by Git.

## Limitations

- “General CAD” means compositions of the validated operations above; it is not yet equivalent to a complete commercial CAD kernel UI.
- Concept spur gears use deterministic straight teeth, not production involute profiles.
- Assembly bodies are positioned geometrically but do not yet support mates, motion simulation, collision analysis, or exploded-view controls.
- Organic Class-A surfaces, imported image logos, threads, sheet-metal unfolding, FEA, CFD, and manufacturing tolerances are not implemented.
- Designs persist in browser local storage and backend memory only; there is no project database or undo timeline.
