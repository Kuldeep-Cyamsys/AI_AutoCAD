import { Suspense, useEffect, useRef, useState } from "react";
import { Canvas, useLoader, useThree } from "@react-three/fiber";
import { Bounds, Center, GizmoHelper, GizmoViewport, Grid, OrbitControls } from "@react-three/drei";
import { Box, ChevronDown, Download, Layers3, Plus, RotateCcw, Send, Sparkles, WandSparkles } from "lucide-react";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

const API_BASE = "http://127.0.0.1:8010";
const apiUrl = (path: string) => `${API_BASE}${path}`;

type Vector3 = { x: number; y: number; z: number };
type Profile = { kind: string; width?: number; height?: number; diameter?: number; length?: number; points?: { x: number; y: number }[]; corner_radius?: number };
type Feature = {
  id: string; name: string; body_id: string; operation: "add" | "cut" | "intersect"; shape: string;
  position: Vector3; rotation: Vector3; axis: "x" | "y" | "z";
  length?: number; width?: number; height?: number; diameter?: number; diameter2?: number; inner_diameter?: number;
  profile?: Profile; teeth?: number; module?: number; text?: string; font_size?: number; fillet_radius: number;
};
type SketchEntity = { id: string; name: string; operation: "add" | "cut"; profile: Profile; x: number; y: number; rotation: number };
type Spec = {
  schema_version: "2.0"; name: string; mode: "sketch_2d" | "part_3d" | "assembly"; units: "mm";
  description: string; features: Feature[]; sketch: SketchEntity[]; design_summary: string[]; assumptions: string[];
  material: string; color: string; revision: number;
};
type Model = {
  model_id: string; preview_url: string; step_url: string; stl_url: string; dxf_url?: string;
  volume_mm3: number; bounding_box: Record<string, number>; body_count: number; feature_count: number; spec: Spec;
};
type ChatMessage = { id: string; role: "ai" | "user" | "thinking"; text: string; streaming?: boolean };

const emptySpec: Spec = {
  schema_version: "2.0", name: "New CAD Design", mode: "part_3d", units: "mm", description: "",
  features: [{ id: "seed", name: "Initial body", body_id: "main", operation: "add", shape: "box", position: { x: 0, y: 0, z: 0 }, rotation: { x: 0, y: 0, z: 0 }, axis: "z", length: 60, width: 40, height: 20, fillet_radius: 0 }],
  sketch: [], design_summary: [], assumptions: [], material: "generic", color: "#65a6c8", revision: 1,
};

function Mesh({ url, color }: { url: string; color: string }) {
  const geometry = useLoader(STLLoader, url);
  useEffect(() => geometry.computeVertexNormals(), [geometry]);
  return <mesh geometry={geometry} castShadow receiveShadow><meshStandardMaterial color={color} metalness={0.48} roughness={0.3} /></mesh>;
}

function CameraReset({ signal }: { signal: number }) {
  const { camera } = useThree();
  useEffect(() => { camera.position.set(180, 150, 180); camera.lookAt(0, 0, 0); }, [signal, camera]);
  return null;
}

function Viewer({ model, reset }: { model: Model | null; reset: number }) {
  return <Canvas shadows camera={{ position: [180, 150, 180], fov: 42, near: 0.1, far: 5000 }}>
    <color attach="background" args={["#071017"]} /><ambientLight intensity={1.25} />
    <directionalLight castShadow position={[120, 180, 100]} intensity={3} />
    <directionalLight position={[-100, 50, -80]} intensity={1} color="#4ca6c8" />
    <Grid infiniteGrid fadeDistance={700} sectionColor="#346377" cellColor="#18323f" cellSize={10} sectionSize={50} />
    <axesHelper args={[70]} />
    <Suspense fallback={null}>{model && <Bounds fit clip observe margin={1.35}><Center><Mesh url={`${model.preview_url}?v=${model.model_id}`} color={model.spec.color} /></Center></Bounds>}</Suspense>
    <OrbitControls makeDefault enableDamping /><CameraReset signal={reset} />
    <GizmoHelper alignment="bottom-right" margin={[70, 70]}><GizmoViewport axisColors={["#ef5350", "#66bb6a", "#42a5f5"]} labelColor="white" /></GizmoHelper>
  </Canvas>;
}

const shapeFields: Record<string, string[]> = {
  box: ["length", "width", "height", "fillet_radius"], cylinder: ["diameter", "inner_diameter", "height"],
  cone: ["diameter", "diameter2", "height"], sphere: ["diameter"], torus: ["diameter", "diameter2"],
  extruded_profile: ["height"], spur_gear: ["teeth", "module", "height", "inner_diameter"], text: ["font_size", "height"],
};
const labels: Record<string, string> = { length: "Length", width: "Width", height: "Height", diameter: "Diameter", diameter2: "Second Ø", inner_diameter: "Bore Ø", teeth: "Teeth", module: "Module", font_size: "Font", fillet_radius: "Fillet" };

function FeatureEditor({ feature, index, update }: { feature: Feature; index: number; update: (index: number, feature: Feature) => void }) {
  const [open, setOpen] = useState(index < 3);
  const setNumber = (key: string, value: string) => update(index, { ...feature, [key]: value === "" ? undefined : Number(value) });
  const setPosition = (axis: keyof Vector3, value: string) => update(index, { ...feature, position: { ...feature.position, [axis]: Number(value) } });
  return <div className="tree-item">
    <button className="tree-title" onClick={() => setOpen(!open)}><span className={`op ${feature.operation}`}>{feature.operation === "add" ? "+" : feature.operation === "cut" ? "−" : "∩"}</span><div><b>{feature.name}</b><small>{feature.shape.replaceAll("_", " ")} · {feature.body_id}</small></div><ChevronDown size={14} className={open ? "turn" : ""} /></button>
    {open && <div className="tree-fields">
      {(shapeFields[feature.shape] || []).map((key) => <label key={key}><span>{labels[key] || key}</span><input type="number" value={(feature as any)[key] ?? ""} onChange={(event) => setNumber(key, event.target.value)} /></label>)}
      {feature.shape === "text" && <label className="wide"><span>Text</span><input value={feature.text || ""} onChange={(event) => update(index, { ...feature, text: event.target.value })} /></label>}
      <div className="position-row"><small>POSITION</small>{(["x", "y", "z"] as const).map((axis) => <label key={axis}><span>{axis.toUpperCase()}</span><input type="number" value={feature.position[axis]} onChange={(event) => setPosition(axis, event.target.value)} /></label>)}</div>
    </div>}
  </div>;
}

function SketchEditor({ entity, index, update }: { entity: SketchEntity; index: number; update: (index: number, entity: SketchEntity) => void }) {
  const fields = entity.profile.kind === "circle" ? ["diameter"] : entity.profile.kind === "slot" ? ["length", "width"] : ["width", "height"];
  return <div className="tree-item"><div className="tree-title static"><span className={`op ${entity.operation}`}>{entity.operation === "add" ? "+" : "−"}</span><div><b>{entity.name}</b><small>{entity.profile.kind} profile</small></div></div><div className="tree-fields sketch-fields">
    {fields.map((key) => <label key={key}><span>{labels[key]}</span><input type="number" value={(entity.profile as any)[key] ?? ""} onChange={(event) => update(index, { ...entity, profile: { ...entity.profile, [key]: Number(event.target.value) } })} /></label>)}
    {(["x", "y"] as const).map((axis) => <label key={axis}><span>{axis.toUpperCase()}</span><input type="number" value={entity[axis]} onChange={(event) => update(index, { ...entity, [axis]: Number(event.target.value) })} /></label>)}
  </div></div>;
}

export default function App() {
  const [spec, setSpec] = useState<Spec>(emptySpec), [model, setModel] = useState<Model | null>(null), [hasProposal, setHasProposal] = useState(false), [prompt, setPrompt] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState(""), [reset, setReset] = useState(0), [ai, setAi] = useState<boolean | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([{ id: "welcome", role: "ai", text: "Describe any part, mechanism, assembly, or 2D profile. I’ll analyze it, propose a parametric construction, and wait for your approval before building." }]);
  const chatRef = useRef<HTMLElement>(null);

  useEffect(() => {
    fetch(apiUrl("/api/health")).then((response) => response.json()).then((data) => setAi(data.ai_enabled)).catch(() => setError("Backend is offline. Start FastAPI on port 8010."));
    const stored = localStorage.getItem("forge-cad-v2-proposal");
    if (stored) try { const parsed = JSON.parse(stored); if (parsed.schema_version === "2.0") { setSpec(parsed); setHasProposal(true); } } catch { localStorage.removeItem("forge-cad-v2-proposal"); }
  }, []);
  useEffect(() => { if (hasProposal) localStorage.setItem("forge-cad-v2-proposal", JSON.stringify(spec)); }, [hasProposal, spec]);
  useEffect(() => { if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight; }, [messages]);

  function streamAssistant(text: string) {
    return new Promise<void>((resolve) => {
      const id = crypto.randomUUID(); let position = 0;
      setMessages((items) => [...items, { id, role: "ai", text: "", streaming: true }]);
      const timer = window.setInterval(() => {
        position = Math.min(position + 5, text.length);
        setMessages((items) => items.map((item) => item.id === id ? { ...item, text: text.slice(0, position), streaming: position < text.length } : item));
        if (position >= text.length) { window.clearInterval(timer); resolve(); }
      }, 10);
    });
  }

  async function send(text = prompt) {
    const cleanText = text.replace(/^\s*\d+\.\s*/, "").replace(/```(?:text)?/gi, "").trim();
    if (!cleanText || busy) return;
    const thinkingId = crypto.randomUUID(); setBusy(true); setError(""); setPrompt("");
    setMessages((items) => [...items, { id: crypto.randomUUID(), role: "user", text: cleanText }, { id: thinkingId, role: "thinking", text: model ? "Revising the feature tree" : "Analyzing geometry and constraints" }]);
    try {
      const response = await fetch(apiUrl("/api/chat"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: cleanText, current_spec: hasProposal || model ? spec : null }) });
      const data = await response.json(); if (!response.ok) throw Error(data.detail);
      setMessages((items) => items.filter((item) => item.id !== thinkingId));
      await streamAssistant([data.message, ...(data.defaults || []).map((item: string) => `Assumption: ${item}`)].join("\n\n"));
      if (data.spec) { setSpec(data.spec); setHasProposal(true); }
      if (data.status === "ready" && data.spec) await generate(data.spec);
    } catch (exception: any) { setMessages((items) => items.filter((item) => item.id !== thinkingId)); setError(exception.message); }
    finally { setBusy(false); }
  }

  async function generate(target = spec) {
    const thinkingId = crypto.randomUUID(); setBusy(true); setError("");
    setMessages((items) => [...items, { id: thinkingId, role: "thinking", text: target.mode === "sketch_2d" ? "Building 2D profile and DXF" : "Executing parametric CAD operations" }]);
    try {
      const response = await fetch(apiUrl("/api/models"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(target) });
      const data = await response.json(); if (!response.ok) throw Error(typeof data.detail === "string" ? data.detail : data.detail?.[0]?.msg || "Generation failed");
      for (const key of ["preview_url", "step_url", "stl_url", "dxf_url"]) if (data[key]) data[key] = apiUrl(data[key]);
      setMessages((items) => items.filter((item) => item.id !== thinkingId)); setModel(data); setSpec(target);
      await streamAssistant(`${target.name} revision ${target.revision} is built. ${data.body_count} ${data.body_count === 1 ? "body" : "bodies"} and ${data.feature_count} features were validated and exported.`);
    } catch (exception: any) { setMessages((items) => items.filter((item) => item.id !== thinkingId)); setError(exception.message); }
    finally { setBusy(false); }
  }

  function newDesign() { localStorage.removeItem("forge-cad-v2-proposal"); setSpec(emptySpec); setModel(null); setHasProposal(false); setMessages([{ id: crypto.randomUUID(), role: "ai", text: "What would you like to design? Describe its purpose or shape; exact dimensions are optional." }]); }
  const updateFeature = (index: number, feature: Feature) => setSpec({ ...spec, features: spec.features.map((item, itemIndex) => itemIndex === index ? feature : item) });
  const updateSketch = (index: number, entity: SketchEntity) => setSpec({ ...spec, sketch: spec.sketch.map((item, itemIndex) => itemIndex === index ? entity : item) });
  const modeLabel = spec.mode === "sketch_2d" ? "2D SKETCH" : spec.mode === "assembly" ? "ASSEMBLY" : "3D PART";

  return <main>
    <aside className="left"><header><div className="mark"><Box /></div><div><h1>FORGE <i>AI</i></h1><p>GENERATIVE PARAMETRIC CAD</p></div><button className="new-design" onClick={newDesign} title="New design"><Plus size={17} /></button></header>
      <div className={`mode ${ai ? "live" : "demo"}`}><span /> {ai ? "AI DESIGNER CONNECTED" : "OFFLINE DESIGN MODE"}</div>
      <section className="chat" ref={chatRef}>{messages.map((message) => <div key={message.id} className={`msg ${message.role}`}>{(message.role === "ai" || message.role === "thinking") && <Sparkles size={14} />}<div className="message-body">{message.role === "thinking" ? <div className="thinking-label"><span>{message.text}</span><i /><i /><i /></div> : <p className={message.streaming ? "streaming" : ""}>{message.text}</p>}</div></div>)}</section>
      <div className="composer"><textarea value={prompt} disabled={busy} onChange={(event) => setPrompt(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} placeholder={model ? "Describe an edit to this design…" : "Describe anything you want to design…"} /><button onClick={() => send()} disabled={busy || !prompt.trim()}><Send size={18} /></button></div>{error && <div className="error">{error}</div>}
    </aside>
    <section className="stage"><div className="stagebar"><div><strong>{model?.spec.name || spec.name}</strong><span>{hasProposal ? `${modeLabel} · REV ${spec.revision}` : "AWAITING PROMPT"}</span></div><button onClick={() => setReset((value) => value + 1)}><RotateCcw size={15} /> Reset view</button></div><Viewer model={model} reset={reset} />
      {!model && <div className="empty"><div><WandSparkles /><h2>{hasProposal ? "Proposal ready for approval" : "Describe it. Review it. Build it."}</h2><p>{hasProposal ? "Review the feature tree, then say “design”." : "Parts, mechanisms, assemblies, or 2D profiles."}</p></div></div>}
      {model && <div className="measure">{Object.entries(model.bounding_box).map(([key, value]) => <span key={key}>{key[0].toUpperCase()} <b>{value} mm</b></span>)}</div>}
    </section>
    <aside className="right"><div className="panelhead"><small>PARAMETRIC DESIGN TREE</small><span>V2 · {modeLabel}</span></div>
      <label><span>Design name</span><input value={spec.name} onChange={(event) => setSpec({ ...spec, name: event.target.value })} /></label>
      <div className="type-badge"><Layers3 size={16} /><div><b>{modeLabel}</b><small>{spec.features.length || spec.sketch.length} named operations</small></div></div>
      {hasProposal && <><div className="feature-card"><small>DESIGN ANALYSIS</small>{spec.design_summary.map((item, index) => <p key={index}>✓ {item}</p>)}{spec.assumptions.map((item, index) => <p className="assumption" key={`a${index}`}>△ {item}</p>)}</div><div className="rule" /><small>{spec.mode === "sketch_2d" ? "SKETCH ENTITIES" : "FEATURES & BODIES"}</small><div className="feature-tree">{spec.mode === "sketch_2d" ? spec.sketch.map((entity, index) => <SketchEditor key={entity.id} entity={entity} index={index} update={updateSketch} />) : spec.features.map((feature, index) => <FeatureEditor key={feature.id} feature={feature} index={index} update={updateFeature} />)}</div></>}
      <div className="rule" /><small>APPEARANCE</small><label><span>Material</span><select value={spec.material} onChange={(event) => setSpec({ ...spec, material: event.target.value })}>{["generic", "aluminum", "steel", "plastic", "brass", "wood"].map((material) => <option key={material}>{material}</option>)}</select></label><label><span>Display color</span><input type="color" value={spec.color} onChange={(event) => setSpec({ ...spec, color: event.target.value })} /></label>
      <button className="generate" disabled={busy || !hasProposal} onClick={() => generate()}><WandSparkles size={17} />{busy ? "Building geometry…" : model ? "Rebuild revision" : hasProposal ? "Approve & build" : "Describe a design first"}</button>
      {model && <><div className="stats"><div><span>Bodies</span><b>{model.body_count}</b></div><div><span>Features</span><b>{model.feature_count}</b></div><div><span>Volume</span><b>{model.volume_mm3.toLocaleString()} mm³</b></div></div><div className="exports"><a href={model.step_url}><Download size={16} />STEP</a><a href={model.stl_url}><Download size={16} />STL</a>{model.dxf_url && <a href={model.dxf_url}><Download size={16} />DXF</a>}</div></>}
    </aside>
  </main>;
}
