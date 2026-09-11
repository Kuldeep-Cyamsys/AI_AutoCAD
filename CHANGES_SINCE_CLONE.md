# Changes Since Cloning

Recorded: 2026-09-11

Baseline: `02c2296` - Initial general AI parametric CAD studio.
Repository: https://github.com/abhishekCyamsys/AI_AutoCAD

This report describes the current workspace changes relative to the cloned commit, plus local setup work performed during development. Application changes are still uncommitted as of this report. No commit, push, or deployment was performed.

## 1. Local Setup

- Cloned the repository into `C:\Users\cyamsys\Desktop\dev\AI_AutoCAD`.
- Installed Python 3.10.11 for the repository's documented Python version; the existing Python 3.13 installation was retained.
- Installed Node.js 22.23.2 with npm 10.9.8 in the Windows user profile and added Node.js to the user PATH.
- Created `backend/.venv` and installed `backend/requirements.txt`.
- Installed frontend packages with `npm.cmd ci`, using the existing lockfile.
- Built the frontend into the ignored `frontend/dist` directory.
- Started FastAPI on port 8010 and checked the frontend on port 5174. The backend was restarted after backend changes.
- Checked the health endpoint and Python dependency consistency. npm reported zero vulnerabilities at installation time.

No package manifest or lockfile changes were required. No model upgrade was made; the configured model observed during setup was `gpt-4.1-mini`. API key values are intentionally excluded from this report.

## 2. Rotation Controls

Previously, the CAD engine and schema already supported rotation, but the editor exposed only position.

- Added X, Y, and Z rotation inputs below each 3D feature's position fields.
- Added one rotation input for each 2D sketch entity.
- Inputs use degrees and accept fractional and negative values.
- Missing rotation values display as zero.
- Changes use the existing approval/rebuild flow; changing an input does not immediately regenerate the mesh.

File: [frontend/src/App.tsx](frontend/src/App.tsx).

## 3. Image Input

- Added a paperclip file picker, attachment thumbnails, and removal buttons.
- Added clipboard image paste handling.
- Added a camera action to attach the current built CAD viewport.
- Enabled WebGL drawing-buffer preservation for viewport capture.
- Added image previews to sent chat messages.
- Accepted formats: PNG, JPEG, and WebP; up to three images per message and 5 MB per image, with an additional encoded-string limit on the backend.
- Added client-side image decoding and backend checks for encoding, size, and basic file signatures. Backend signature checks are not a full image decoder.
- Sent images as multimodal image content alongside the message and current design.
- Added a clarification response when images are submitted without an API key.
- Improved display of API validation errors and restored prompt text after a failed request.

Files: [ImageAttachments.tsx](frontend/src/ImageAttachments.tsx), [App.tsx](frontend/src/App.tsx), [style.css](frontend/src/style.css), [schemas.py](backend/app/schemas.py), [ai_service.py](backend/app/ai_service.py).

## 4. Conversation Memory

Previously, each model request included only the latest message and current design. Earlier visible chat messages were not sent to the model.

- Added ordered user/assistant history to `ChatRequest` and forwarded it as separate model messages.
- Included historical user image attachments in follow-up requests.
- Excluded transient thinking indicators, incomplete streamed messages, and the initial welcome message from outgoing history.
- Restricted historical roles to user and assistant; clients cannot supply a system role through history.
- Added IndexedDB persistence for the current design specification, completed chat messages, their images, and proposal state.
- Added loading guards, serialized storage writes, and storage-error feedback.
- Retained a migration fallback for the old localStorage design when no IndexedDB session exists.
- Added `DesignSpec.design_notes` for agreed formulas, constraints, and choices, with instructions for the model to preserve or update those notes.
- Instructed the model to honor later corrections and use the current specification as the latest geometry, including manual edits.

Storage uses database `forge-cad`, store `sessions`, and key `current`. This is one browser-local session, not a project library or account database. Starting a new design replaces that session. The built mesh/model response is not persisted; a restored design needs rebuilding for its preview.

History is limited to 200 prior messages, with 30,000 characters per historical message. There is no automatic summarization or token-budget management. Repeated historical images increase request size and API usage. Chats lost before this change cannot be recovered. Design notes are model-maintained text, not an enforced constraint solver.

Files: [conversationStore.ts](frontend/src/conversationStore.ts), [App.tsx](frontend/src/App.tsx), [schemas.py](backend/app/schemas.py), [ai_service.py](backend/app/ai_service.py).

## 5. Arithmetic Verification

- Added optional structured calculations to model responses: label, expression, result, and units.
- Added a restricted Python AST evaluator for numbers, parentheses, unary signs, addition, subtraction, multiplication, and division.
- Rejected function calls, unsupported operators, non-finite values, excessive expression complexity, and out-of-range values.
- Compared reported results against computed values with a numeric tolerance.
- Routed calculation validation failures through the existing one-retry response-correction flow.
- Asked the model to explain formulas, substituted values, and results concisely.

This checks only calculations actually included in the response. It does not verify formula selection, unit conversion, engineering correctness, or whether the feature-tree dimensions match a calculation. The calculation list is optional; this is not comprehensive dimensional validation.

Files: [calculations.py](backend/app/calculations.py), [schemas.py](backend/app/schemas.py), [ai_service.py](backend/app/ai_service.py).

## 6. Approval and Session Handling

- Removed the process-wide `LATEST_PROPOSAL` fallback, which could supply a proposal unrelated to a client's current design.
- Approval requests now rely on the current specification supplied by the client.
- Kept the explicit text-confirmation shortcut for requests with a current design and no new images.
- Changed model-generated `ready` responses to proposals or clarifications, so an unsolicited model response does not trigger a build.

This is application workflow handling, not server-side authorization. The existing model-generation endpoint remains directly callable.

Files: [main.py](backend/app/main.py), [ai_service.py](backend/app/ai_service.py).

## 7. Coordinate Display Fix

- Removed the viewer's `Center` wrapper, which translated the full assembly while leaving the world axes fixed.
- Retained camera fitting with `Bounds`, without recentering the mesh coordinates.
- Changed the camera to Z-up and rotated the grid into the CAD XY plane.
- Added explicit coordinate conventions to the model prompt: millimeters, center-based boxes, orientation then rotation then translation, and surface-to-center placement calculations.

Example: an unrotated 210 x 110 x 28 mm box at `(0, 0, 0)` spans X `-105..105`, Y `-55..55`, and Z `-14..14`. To put its bottom at Z=0, set its center Z to 14.

The CAD engine was not changed. Existing generated feature coordinates, including misplaced standoffs, were not automatically corrected by the viewer fix.

Files: [App.tsx](frontend/src/App.tsx), [ai_service.py](backend/app/ai_service.py).

## 8. Verification Recorded During Development

| Check | Recorded result |
| --- | --- |
| Frontend TypeScript and Vite production builds | Passed after the final coordinate change; existing large-bundle warning remains |
| Python dependency check | No broken requirements found during installation |
| Original CAD tests during setup | 6 passed |
| Image regression tests | 7 passed with exit code 0 |
| Combined image and memory/arithmetic tests | 15 passed with exit code 0 |
| Box-coordinate tests | 2 passed, but the process subsequently returned exit code 1 |
| Earlier combined CAD/image run | 13 assertions passed, but the process subsequently returned exit code 1 |
| Backend health and updated API schema | Checked successfully after image and memory changes |
| Browser visual and interaction checks | Not completed; browser automation was unavailable |
| Live model image understanding and multi-turn quality | Not verified; model-request tests used mocks |

The abnormal CAD test exits remain unresolved and must not be described as a fully clean test run. No new execution tests were run solely for writing this report.

Added tests: [test_images.py](backend/tests/test_images.py), [test_memory.py](backend/tests/test_memory.py), [test_coordinates.py](backend/tests/test_coordinates.py).

## 9. Current File Inventory

Modified application files:

- `backend/app/ai_service.py`
- `backend/app/main.py`
- `backend/app/schemas.py`
- `frontend/src/App.tsx`
- `frontend/src/style.css`

Added application and test files:

- `backend/app/calculations.py`
- `backend/tests/test_coordinates.py`
- `backend/tests/test_images.py`
- `backend/tests/test_memory.py`
- `frontend/src/ImageAttachments.tsx`
- `frontend/src/conversationStore.ts`

Documentation added in this reporting task: this file and a README link.

Git also reports `backend/.env.example` as deleted. This was already present when implementation began, was not part of the assistant's feature edits, and was left untouched. The local `.env`, installed dependencies, generated models, and build outputs are not included in the tracked application diff.

## 10. Discussed but Not Implemented

- MCP server or external-assistant integration.
- A stronger model or reasoning-configuration upgrade.
- Full dimensional constraints, automatic component placement correction, or a general engineering calculation engine.
- Conversation summarization, multi-project storage, cloud sync, or cross-device memory.
- Complete browser-based validation of uploads, persistence, capture, and coordinate display.
