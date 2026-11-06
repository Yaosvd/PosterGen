import { useEffect, useState, type FormEvent } from 'react';
import axios from 'axios';
import { FileUpload } from './components/FileUpload';
import { ProgressBar } from './components/ProgressBar';
import { sampleApi } from './sampleApi';
import type { SampleConfig, SampleFiles, SampleJob } from './sampleTypes';

export default function SampleApp() {
  const [config, setConfig] = useState<SampleConfig>({ text_model: '', vision_model: '', poster_width: 54,
    poster_height: 36, sample_generation: true, samples: '', run_id: '', random_seed: '',
    paper_cache_run_id: '', paper_cache_sample_id: '' });
  const [files, setFiles] = useState<SampleFiles>({ pdf_file: null, logo_file: null, aff_logo_file: null });
  const [models, setModels] = useState<string[]>([]);
  const [job, setJob] = useState<SampleJob | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [metadata, setMetadata] = useState<Record<string, unknown>>({});
  const [selectedPoster, setSelectedPoster] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const active = !!job && ['pending', 'processing', 'paused', 'stopping'].includes(job.status);
  const stopped = job?.status === 'paused' && !submitting;
  useEffect(() => {
    sampleApi.models().then(data => {
      setModels(data.models);
      setConfig(c => ({ ...c, text_model: data.default_text_model, vision_model: data.default_vision_model }));
    }).catch(() => setError('Could not load models'));
  }, []);
  useEffect(() => {
    if (!job || !submitting) return;
    let disposed = false;
    const id = job.job_id;
    const timer = window.setInterval(async () => {
      try {
        const [current, messages] = await Promise.all([sampleApi.status(id), sampleApi.logs(id)]);
        if (disposed) return;
        setJob(current); setLogs(messages);
        if (['completed', 'failed'].includes(current.status) || (current.status === 'paused' && current.message.includes('PAUSED'))) {
          setSubmitting(false);
          sampleApi.files(id).then(setMetadata).catch(() => {});
        }
      } catch { if (!disposed) setError('Could not refresh job status'); }
    }, 2000);
    return () => { disposed = true; window.clearInterval(timer); };
  }, [job?.job_id, submitting]);
  const update = <K extends keyof SampleConfig>(key: K, value: SampleConfig[K]) => setConfig(c => ({ ...c, [key]: value }));
  const reportError = (e: unknown) => {
    setError(axios.isAxiosError(e) ? String(e.response?.data?.detail || e.message) : String(e));
  };
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setSubmitting(true); setSelectedPoster(''); setMetadata({}); setLogs([]);
    try { setJob(await sampleApi.generate(config, files)); }
    catch (e) { reportError(e); setSubmitting(false); }
  }
  async function control(action: string) {
    if (!job) return;
    try { await sampleApi.control(job.job_id, action); setJob(await sampleApi.status(job.job_id)); }
    catch (e) { reportError(e); }
  }
  const posters = (job?.results || []).filter(r => r.poster_id);
  const selected = posters.find(r => r.poster_id === selectedPoster) || posters[posters.length - 1];
  const preview = selected?.poster_id && job?.run_id ? sampleApi.artifact(job.run_id, selected.poster_id, 'poster.png') : null;
  const canSubmit = !!files.pdf_file && !!files.logo_file && !!files.aff_logo_file && !!config.text_model && !!config.vision_model && !submitting;
  return <div className="container">
    <header className="header"><h1>Rubrics_poster</h1><p>Independent paper-to-poster samples for Rubrics development</p></header>
    <form onSubmit={submit} className="poster-form">
      <div className="form-section"><h2>Paper and logos</h2>
        <div className="form-grid">
          <FileUpload label="Paper PDF" accept="application/pdf" selectedFile={files.pdf_file} onFileSelect={f => setFiles(v => ({ ...v, pdf_file: f }))} />
          <FileUpload label="Conference logo" accept="image/*" selectedFile={files.logo_file} onFileSelect={f => setFiles(v => ({ ...v, logo_file: f }))} />
          <FileUpload label="Affiliation logo" accept="image/*" selectedFile={files.aff_logo_file} onFileSelect={f => setFiles(v => ({ ...v, aff_logo_file: f }))} />
        </div>
      </div>
      <div className="form-section"><h2>Generation</h2><div className="form-grid">
        {(['text_model', 'vision_model'] as const).map(key => <div className="form-group" key={key}>
          <label htmlFor={key}>{key === 'text_model' ? 'Text model' : 'Vision model'}</label>
          <select id={key} value={config[key]} disabled={submitting} onChange={e => update(key, e.target.value)}>
            {models.map(model => <option key={model}>{model}</option>)}
          </select>
        </div>)}
        <div className="form-group"><label htmlFor="width">Width</label><input id="width" type="number" min="1" value={config.poster_width} onChange={e => update('poster_width', Number(e.target.value))} /></div>
        <div className="form-group"><label htmlFor="height">Height</label><input id="height" type="number" min="1" value={config.poster_height} onChange={e => update('poster_height', Number(e.target.value))} /></div>
        {config.sample_generation && <>
          <div className="form-group"><label htmlFor="samples">Full poster tasks</label><input id="samples" type="number" min="1" placeholder="100 for a new run" value={config.samples} disabled={submitting || !!config.run_id} onChange={e => update('samples', e.target.value)} /></div>
          <div className="form-group"><label htmlFor="seed">Random seed</label><input id="seed" type="number" value={config.random_seed} disabled={submitting || !!config.run_id} onChange={e => update('random_seed', e.target.value)} /></div>
          <div className="form-group"><label htmlFor="run">Resume run ID (optional)</label><input id="run" value={config.run_id} disabled={submitting} placeholder="Blank creates a new independent run" onChange={e => setConfig(c => ({ ...c, run_id: e.target.value, samples: '', random_seed: '', paper_cache_run_id: '', paper_cache_sample_id: '' }))} /></div>
          <div className="form-group"><label htmlFor="cache-run">Reuse paper from run ID (optional)</label><input id="cache-run" value={config.paper_cache_run_id} disabled={submitting || !!config.run_id} placeholder="Blank re-extracts the PDF for every poster" onChange={e => update('paper_cache_run_id', e.target.value)} /></div>
          <div className="form-group"><label htmlFor="cache-sample">Source sample ID (for multi-task cache)</label><input id="cache-sample" value={config.paper_cache_sample_id} disabled={submitting || !!config.run_id} placeholder="sample_000001" onChange={e => update('paper_cache_sample_id', e.target.value)} /></div>
        </>}
      </div><p>Every poster starts from the uploaded PDF, logos and generation parameters. The PDF is re-extracted and organized for each task unless you explicitly select a compatible paper cache. Resuming restores checkpoints only for that same task. The final Critic compares the finished poster with the original paper. Every final poster and its layout template are saved together: high score (80 or above), low score (below 80), or failed/incomplete evaluation.</p></div>
      <button className="button" type="submit" disabled={!canSubmit}>{submitting ? 'Generating…' : 'Generate'}</button>
      {error && <div className="error-message">{error}</div>}
    </form>
    {job && <>
      <ProgressBar message={job.message} logs={logs} isActive={active && !stopped} />
      {job.sample_generation && <div className="loop-control-panel">
        <p>Run: <strong>{job.run_id || 'preparing'}</strong></p>
        <p>Tasks {job.finalized_samples}/{job.planned_samples} · Posters {job.rendered_samples} · Scored {job.scored_samples} · Failures {job.failed_samples}</p>
        {submitting && <div className="loop-controls">
          <button onClick={() => control(job.status === 'paused' ? 'resume' : 'pause')}>{job.status === 'paused' ? 'Continue' : 'Pause'}</button>
          <button onClick={() => control('stop')}>Save and stop</button><button onClick={() => control('force-stop')}>Force stop</button>
        </div>}
        {stopped && <button onClick={() => setConfig(c => ({ ...c, run_id: job.run_id || '', samples: '', random_seed: '', paper_cache_run_id: '', paper_cache_sample_id: '' }))}>Use this run ID to resume</button>}
      </div>}
      {['completed', 'paused', 'failed'].includes(job.status) && <a className="download-button" href={sampleApi.download(job.job_id)}>Download saved results</a>}
      {job.sample_generation && <div className="form-section"><h2>Samples</h2>
        <table><thead><tr><th>Sample</th><th>Family</th><th>Status</th><th>Score</th><th>Group</th><th>Files</th></tr></thead><tbody>
          {job.results.map(r => <tr key={r.sample_id}><td>{r.sample_id}</td><td>{r.layout_family}</td><td>{r.status}</td><td>{r.score ?? 'Unavailable'}</td><td>{{high_score: 'High (≥80)', low_score: 'Low (<80)', evaluation_failed: 'Failed / incomplete', unclassified: 'No poster'}[r.grouping]}</td><td>
            {r.poster_id && job.run_id && <><button onClick={() => setSelectedPoster(r.poster_id!)}>Preview</button>{['poster.pptx', 'template.json', 'template.png', 'template.pptx', 'evaluation.json'].map(file => <a key={file} href={sampleApi.artifact(job.run_id!, r.poster_id!, file)} target="_blank" rel="noreferrer"> {file} </a>)}</>}
          </td></tr>)}
        </tbody></table>
      </div>}
      <div className="preview-wrapper"><div className="preview-section"><h3>Poster preview</h3>{preview ? <img src={preview} alt="Saved final poster" className="poster-preview" /> : <p>No final poster saved yet.</p>}</div>
        <div className="preview-section"><h3>Run details</h3><pre>{JSON.stringify(metadata, null, 2)}</pre></div></div>
    </>}
  </div>;
}
