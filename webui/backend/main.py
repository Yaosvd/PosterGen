import os
import sys
import tempfile
import time
import zipfile
import json
from pathlib import Path
from typing import Dict, Any, Optional
import uuid
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

os.chdir(project_root)
from src.workflow.optimization_loop import LoopControl, PosterOptimizationLoop

from src.state.poster_state import create_state
from src.workflow.pipeline import create_workflow_graph, save_timing_log

app = FastAPI(title="PosterGen WebUI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: Dict[str, Dict[str, Any]] = {}

job_logs: Dict[str, list] = {}

loop_controls: Dict[str, LoopControl] = {}

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    error: Optional[str] = None
    continuous_loop: bool = False
    iteration: int = 0
    last_score: Optional[float] = None
    accepted_count: int = 0
    campaign_id: Optional[str] = None
    resumed: bool = False
    last_completed_iteration: int = 0
    attempt_number: Optional[int] = None
    batch_id: Optional[str] = None
    batch_completed_iterations: int = 0
    batch_target_iterations: int = 100
    layout_family: Optional[str] = None
    lineage_id: Optional[str] = None
    portfolio_mode: Optional[str] = None
    batch_mode: Optional[str] = None
    batch_status: Optional[str] = None

class PosterRequest(BaseModel):
    text_model: str
    vision_model: str
    poster_width: float
    poster_height: float

def get_available_models():
    models = []
    if os.getenv("LOCAL_TEXT_BASE_URL"):
        models.append(os.getenv("LOCAL_TEXT_MODEL", "qwen3.8-27b"))
    if os.getenv("LOCAL_VISION_BASE_URL"):
        models.append(os.getenv("LOCAL_VISION_MODEL", "qwen3-vl-30b-a3b"))

    return models + [
        "claude-sonnet-4-20250514",
        "claude-opus-4.5",
        "gpt-4o-2024-08-06",
        "gpt-4.1-2025-04-14",
        "gpt-4.1-mini-2025-04-14",
        "glm-4.6",
        "glm-4.6v",
        "glm-4.5",
        "glm-4.5-air",
        "glm-4.5v",
        "glm-4",
        "glm-4v"
    ]

def create_job_directory() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"postgen_{timestamp}"
    job_dir = Path(tempfile.mkdtemp(prefix=f"{dir_name}_"))
    return job_dir

def add_job_log(job_id: str, message: str):
    if job_id not in job_logs:
        job_logs[job_id] = []
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    job_logs[job_id].append(log_entry)
    
    if len(job_logs[job_id]) > 50:
        job_logs[job_id] = job_logs[job_id][-50:]

def run_poster_generation(job_id: str, config: dict, files: dict):
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["progress"] = 10
        jobs[job_id]["message"] = "Initializing pipeline..."
        add_job_log(job_id, "Starting poster generation pipeline")
        
        job_dir = create_job_directory()
        add_job_log(job_id, f"Created working directory: {job_dir.name}")
        
        pdf_path = job_dir / "paper.pdf"
        logo_path = job_dir / "logo.png"
        aff_logo_path = job_dir / "aff_logo.png"
        
        with open(pdf_path, "wb") as f:
            f.write(files["pdf"])
        with open(logo_path, "wb") as f:
            f.write(files["logo"])
        with open(aff_logo_path, "wb") as f:
            f.write(files["aff_logo"])
        
        add_job_log(job_id, "Uploaded files saved successfully")
            
        jobs[job_id]["progress"] = 20
        jobs[job_id]["message"] = "Setting up workflow..."
        add_job_log(job_id, "Configuring pipeline workflow")
        
        state = create_state(
            pdf_path=str(pdf_path),
            text_model=config["text_model"],
            vision_model=config["vision_model"],
            width=int(config["poster_width"]),
            height=int(config["poster_height"]),
            url="",
            logo_path=str(logo_path),
            aff_logo_path=str(aff_logo_path),
            poster_name=Path(files.get("pdf_filename") or "poster.pdf").stem,
        )

        jobs[job_id]["output_dir"] = state["output_dir"]
        jobs[job_id]["poster_name"] = state["poster_name"]

        def update_loop_status(payload: Dict[str, Any]):
            loop_status = str(payload.get("status", "RUNNING")).lower()
            if loop_status == "paused":
                jobs[job_id]["status"] = "paused"
            elif loop_status == "stopped":
                jobs[job_id]["status"] = "stopping"
            elif jobs[job_id].get("status") != "stopping":
                jobs[job_id]["status"] = "processing"
            jobs[job_id]["iteration"] = int(payload.get("iteration", 0))
            jobs[job_id]["last_score"] = payload.get("last_score")
            jobs[job_id]["accepted_count"] = int(payload.get("accepted_count", 0))
            jobs[job_id]["campaign_id"] = payload.get("campaign_id")
            jobs[job_id]["resumed"] = bool(payload.get("resumed", False))
            jobs[job_id]["last_completed_iteration"] = int(payload.get("last_completed_iteration", 0))
            jobs[job_id]["attempt_number"] = payload.get("attempt_number")
            batch = payload.get("batch") or {}
            jobs[job_id]["batch_id"] = batch.get("batch_id")
            jobs[job_id]["batch_completed_iterations"] = int(
                batch.get("completed_iterations", 0)
            )
            jobs[job_id]["batch_target_iterations"] = int(
                batch.get(
                    "target_iterations",
                    config.get("batch_iterations", 100),
                )
            )
            jobs[job_id]["layout_family"] = payload.get("layout_family")
            jobs[job_id]["lineage_id"] = payload.get("lineage_id")
            jobs[job_id]["portfolio_mode"] = payload.get("portfolio_mode")
            jobs[job_id]["batch_mode"] = batch.get("schedule_policy", {}).get("mode")
            jobs[job_id]["batch_status"] = batch.get("status")
            next_message = payload.get("message", "Optimizing poster")
            if next_message != jobs[job_id].get("message"):
                jobs[job_id]["message"] = next_message
                add_job_log(job_id, next_message)
        
        jobs[job_id]["progress"] = 30
        jobs[job_id]["message"] = "Running poster generation..."
        add_job_log(job_id, "Initializing multi-agent workflow")
        
        state["timing_metrics"].pipeline_start = time.time()
        if config.get("continuous_loop", False):
            control = LoopControl()
            loop_controls[job_id] = control
            jobs[job_id]["continuous_loop"] = True
            jobs[job_id]["progress"] = 40
            jobs[job_id]["message"] = "Critic optimization Batch running..."
            add_job_log(
                job_id,
                f"Batch started with {config.get('batch_iterations', 100)} committed iterations",
            )
            final_state = PosterOptimizationLoop(
                control=control,
                status_callback=update_loop_status,
                resume_mode=config.get("resume_mode", "latest"),
                campaign_id=config.get("campaign_id") or None,
                batch_iterations=int(config.get("batch_iterations", 100)),
                batch_mode=config.get("batch_mode") or None,
                target_lineage_id=config.get("target_lineage_id") or None,
            ).run(state)
        else:
            jobs[job_id]["continuous_loop"] = False
            graph = create_workflow_graph()
            workflow = graph.compile()
            add_job_log(job_id, "Workflow graph compiled successfully")
            jobs[job_id]["progress"] = 40
            jobs[job_id]["message"] = "Analyzing paper content..."
            add_job_log(job_id, "Starting document analysis and content extraction")
            final_state = workflow.invoke(state)
            add_job_log(job_id, "Workflow execution completed")
        
        final_state["timing_metrics"].pipeline_end = time.time()
        save_timing_log(final_state)
        jobs[job_id]["progress"] = 80
        jobs[job_id]["message"] = "Generating final outputs..."
        add_job_log(job_id, "Creating final poster files")
        
        loop_result = final_state.get("loop_state") or {}
        if config.get("continuous_loop", False) and loop_result.get("status") == "FAILED_REQUIRES_USER":
            raise Exception(f"Continuous loop failed: {loop_result.get('errors') or loop_result.get('stop_reason')}")
        if loop_result.get("status") == "UNAVAILABLE":
            raise Exception(f"Batch unavailable: {loop_result.get('stop_reason')}")
        if not config.get("continuous_loop", False) and final_state.get("errors"):
            raise Exception(f"Pipeline errors: {final_state['errors']}")
        if loop_result.get("status") == "EXHAUSTED" and not loop_result.get("best_candidate"):
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["progress"] = 100
            jobs[job_id]["message"] = "Validation queue exhausted; no poster was generated."
            add_job_log(job_id, jobs[job_id]["message"])
            return

        output_dir = Path(final_state["output_dir"])
        zip_path = job_dir / f"{final_state['poster_name']}_output.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if output_dir.exists():
                for file_path in output_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(output_dir)
                        zipf.write(file_path, arcname)
        
        add_job_log(job_id, f"ZIP package created: {zip_path.name}")
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "Poster generation completed!"
        jobs[job_id]["output_file"] = str(zip_path)
        jobs[job_id]["poster_name"] = final_state["poster_name"]
        jobs[job_id]["output_dir"] = str(output_dir)
        add_job_log(job_id, "✅ Poster generation completed successfully!")
        
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["message"] = f"Error: {str(e)}"
        add_job_log(job_id, f"❌ Error: {str(e)}")
    finally:
        loop_controls.pop(job_id, None)

@app.get("/")
async def root():
    return {"message": "PosterGen WebUI API"}

@app.get("/models")
async def get_models():
    """Get available models for dropdowns"""
    models = get_available_models()
    return {
        "models": models,
        "default_text_model": (
            os.getenv("LOCAL_TEXT_MODEL", "qwen3.8-27b")
            if os.getenv("LOCAL_TEXT_BASE_URL")
            else "gpt-4o-2024-08-06"
        ),
        "default_vision_model": (
            os.getenv("LOCAL_VISION_MODEL", "qwen3-vl-30b-a3b")
            if os.getenv("LOCAL_VISION_BASE_URL")
            else "gpt-4o-2024-08-06"
        ),
    }

@app.post("/generate", response_model=JobStatus)
async def generate_poster(
    background_tasks: BackgroundTasks,
    text_model: str = Form(...),
    vision_model: str = Form(...),
    poster_width: float = Form(...),
    poster_height: float = Form(...),
    continuous_loop: bool = Form(True),
    resume_mode: str = Form("latest"),
    campaign_id: Optional[str] = Form(None),
    batch_iterations: int = Form(100),
    batch_mode: str = Form(""),
    target_lineage_id: str = Form(""),
    pdf_file: UploadFile = File(...),
    logo_file: UploadFile = File(...),
    aff_logo_file: UploadFile = File(...)
):
    
    available_models = get_available_models()
    if text_model not in available_models:
        raise HTTPException(status_code=400, detail=f"Invalid text model: {text_model}")
    if vision_model not in available_models:
        raise HTTPException(status_code=400, detail=f"Invalid vision model: {vision_model}")
    if resume_mode not in {"latest", "required", "new"}:
        raise HTTPException(status_code=400, detail="Invalid resume mode")
    if batch_mode and batch_mode not in {"mixed", "explore", "improve", "mutate", "validate"}:
        raise HTTPException(status_code=400, detail="Invalid Batch mode")
    if target_lineage_id and batch_mode not in {"improve", "mutate"}:
        raise HTTPException(status_code=400, detail="Target Lineage requires improve or mutate mode")
    if batch_iterations < 1:
        raise HTTPException(
            status_code=400,
            detail="Batch iterations must be positive",
        )

    
    ratio = poster_width / poster_height
    if ratio > 2 or ratio < 1.4:
        raise HTTPException(status_code=400, detail=f"Poster ratio {ratio:.2f} out of range (1.4-2.0)")
    
    if not pdf_file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Paper must be a PDF file")
    
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "progress": 0,
        "message": "Job created, starting soon...",
        "continuous_loop": continuous_loop,
        "iteration": 0,
        "last_score": None,
        "accepted_count": 0,
        "campaign_id": None,
        "resumed": False,
        "last_completed_iteration": 0,
        "attempt_number": None,
        "batch_id": None,
        "batch_completed_iterations": 0,
        "batch_target_iterations": batch_iterations,
        "layout_family": None,
        "lineage_id": None,
        "portfolio_mode": None,
        "batch_mode": batch_mode or None,
        "batch_status": None,
    }
    
    job_logs[job_id] = []
    add_job_log(job_id, "Job created and queued for processing")
    
    pdf_content = await pdf_file.read()
    logo_content = await logo_file.read()
    aff_logo_content = await aff_logo_file.read()
    
    config = {
        "text_model": text_model,
        "vision_model": vision_model,
        "poster_width": poster_width,
        "poster_height": poster_height,
        "continuous_loop": continuous_loop,
        "resume_mode": resume_mode,
        "campaign_id": campaign_id,
        "batch_iterations": batch_iterations,
        "batch_mode": batch_mode,
        "target_lineage_id": target_lineage_id,
    }
    
    files = {
        "pdf": pdf_content,
        "logo": logo_content,
        "aff_logo": aff_logo_content,
        "pdf_filename": pdf_file.filename,
    }
    
    background_tasks.add_task(run_poster_generation, job_id, config, files)
    
    return JobStatus(
        job_id=job_id,
        status="pending",
        progress=0,
        message="Job started...",
        continuous_loop=continuous_loop,
    )

@app.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        error=job.get("error"),
        continuous_loop=bool(job.get("continuous_loop", False)),
        iteration=int(job.get("iteration", 0)),
        last_score=job.get("last_score"),
        accepted_count=int(job.get("accepted_count", 0)),
        campaign_id=job.get("campaign_id"),
        resumed=bool(job.get("resumed", False)),
        last_completed_iteration=int(job.get("last_completed_iteration", 0)),
        attempt_number=job.get("attempt_number"),
        batch_id=job.get("batch_id"),
        batch_completed_iterations=int(
            job.get("batch_completed_iterations", 0)
        ),
        batch_target_iterations=int(
            job.get("batch_target_iterations", 100)
        ),
        layout_family=job.get("layout_family"),
        lineage_id=job.get("lineage_id"),
        portfolio_mode=job.get("portfolio_mode"),
        batch_mode=job.get("batch_mode"),
        batch_status=job.get("batch_status"),
    )

@app.post("/control/{job_id}/{action}")
async def control_loop(job_id: str, action: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    control = loop_controls.get(job_id)
    if control is None:
        raise HTTPException(status_code=400, detail="Job has no active continuous loop")
    if action == "pause":
        control.pause()
        jobs[job_id]["status"] = "paused"
        message = "Pause requested"
    elif action == "resume":
        control.resume()
        jobs[job_id]["status"] = "processing"
        message = "Optimization resumed"
    elif action in {"stop", "force-stop"}:
        control.request_stop(force=action == "force-stop")
        jobs[job_id]["status"] = "stopping"
        message = (
            "Stop requested; finishing current iteration"
            if action == "stop"
            else "Force-stop requested; waiting for the current model or render call to return"
        )
    else:
        raise HTTPException(status_code=400, detail="Action must be pause, resume, stop, or force-stop")
    add_job_log(job_id, message)
    return {
        "job_id": job_id,
        "status": jobs[job_id]["status"],
        "action": action,
    }

@app.get("/logs/{job_id}")
async def get_job_logs(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    logs = job_logs.get(job_id, [])
    return {"logs": logs}

@app.get("/download/{job_id}")
async def download_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    output_file = job.get("output_file")
    if not output_file or not Path(output_file).exists():
        raise HTTPException(status_code=404, detail="Output file not found")
    
    poster_name = job.get("poster_name", "poster")
    filename = f"{poster_name}_poster_output.zip"
    
    return FileResponse(
        path=output_file,
        media_type="application/zip",
        filename=filename
    )

@app.get("/poster/{job_id}")
async def get_poster_image(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] not in {"processing", "paused", "stopping", "completed"}:
        raise HTTPException(status_code=400, detail="Poster preview is not available yet")
    
    poster_name = job.get("poster_name", "poster")
    output_dir = job.get("output_dir")
    if not output_dir:
        raise HTTPException(status_code=404, detail="Output directory not found")
    png_path = Path(output_dir) / f"{poster_name}.png"
    
    if not png_path.exists():
        raise HTTPException(status_code=404, detail="Poster image not found")
    
    return FileResponse(
        path=str(png_path),
        media_type="image/png"
    )

@app.get("/files/{job_id}")
async def get_json_files(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    # Use the specific job's output directory
    output_dir = job.get("output_dir")
    if not output_dir:
        return {"files": {}}
    
    output_path = Path(output_dir)
    content_path = output_path / "content"
    
    json_files = {}
    
    # Only search in the specific job's content directory
    if content_path.exists():
        for json_file in content_path.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_files[json_file.name] = json.load(f)
            except Exception:
                continue
    
    return {"files": json_files}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
