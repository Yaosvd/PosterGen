import React, { useState, useEffect } from 'react';
import { FileUpload } from './components/FileUpload';
import { ProgressBar } from './components/ProgressBar';
import { apiService } from './api';
import {
  BatchSummary,
  PosterConfig,
  UploadedFiles,
  JobStatus,
} from './types';
import postergenLogo from './postergen-logo.png';

function App() {
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [config, setConfig] = useState<PosterConfig>({
    text_model: '',
    vision_model: '',
    poster_width: 54,
    poster_height: 36,
    continuous_loop: true,
    resume_mode: 'latest',
    campaign_id: '',
    batch_iterations: 100,
    batch_mode: '',
    target_lineage_id: '',
    batch_id: '',
    new_batch: false,
  });
  const [files, setFiles] = useState<UploadedFiles>({
    pdf_file: null,
    logo_file: null,
    aff_logo_file: null,
  });
  const [currentJob, setCurrentJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [jsonFiles, setJsonFiles] = useState<Record<string, any>>({});
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
  const [batches, setBatches] = useState<BatchSummary[]>([]);
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null);
  const [isLoadingBatches, setIsLoadingBatches] = useState(false);

  useEffect(() => {
    const loadModels = async () => {
      try {
        const modelOptions = await apiService.getModels();
        setAvailableModels(modelOptions.models);
        if (modelOptions.models.length > 0) {
          setConfig(prev => ({
            ...prev,
            text_model: modelOptions.default_text_model,
            vision_model: modelOptions.default_vision_model,
          }));
        }
      } catch (err) {
        setError('Failed to load available models');
      }
    };
    
    loadModels();
  }, []);

  useEffect(() => {
    if (!currentJob || currentJob.status === 'completed' || currentJob.status === 'failed') {
      return;
    }

    const pollInterval = setInterval(async () => {
      try {
        const [status, logs] = await Promise.all([
          apiService.getJobStatus(currentJob.job_id),
          apiService.getJobLogs(currentJob.job_id)
        ]);
        
        setCurrentJob(status);
        setLogs(logs);
        
        if (status.status === 'failed') {
          setError(status.error || 'Job failed');
          setIsSubmitting(false);
        } else if (status.status === 'completed') {
          setIsSubmitting(false);
          fetchJsonFiles(currentJob.job_id);
        }
      } catch (err) {
        setError('Failed to check job status');
        setIsSubmitting(false);
      }
    }, 2000);

    return () => clearInterval(pollInterval);
  }, [currentJob]);

  const fetchJsonFiles = async (jobId: string) => {
    try {
      const response = await fetch(`http://localhost:8001/files/${jobId}`);
      if (response.ok) {
        const data = await response.json();
        setJsonFiles(data.files || {});
      }
    } catch (error) {
      console.error('Failed to fetch JSON files:', error);
    }
  };

  const getPosterImageUrl = () => {
    if (!currentJob) return null;
    const previewStatuses: JobStatus['status'][] = ['processing', 'paused', 'stopping', 'completed'];
    if (!previewStatuses.includes(currentJob.status)) return null;
    if (currentJob.continuous_loop && currentJob.accepted_count < 1) return null;
    if (!currentJob.continuous_loop && currentJob.status !== 'completed') return null;
    return `http://localhost:8001/poster/${currentJob.job_id}?iteration=${currentJob.iteration}`;
  };

  const toggleFileExpansion = (filename: string) => {
    const newExpanded = new Set(expandedFiles);
    if (newExpanded.has(filename)) {
      newExpanded.delete(filename);
    } else {
      newExpanded.add(filename);
    }
    setExpandedFiles(newExpanded);
  };

  const copyToClipboard = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  const handleConfigChange = (field: keyof PosterConfig, value: string | number | boolean) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };

  const handleFileChange = (field: keyof UploadedFiles, file: File) => {
    setFiles(prev => ({ ...prev, [field]: file }));
    setError(null);
  };

  const loadCampaignBatches = async () => {
    const campaignId = config.campaign_id.trim();
    if (!campaignId) {
      setError('Enter an exact Campaign ID before loading Batches');
      return;
    }
    setIsLoadingBatches(true);
    setError(null);
    try {
      const response = await apiService.getCampaignBatches(campaignId);
      setBatches(response.batches);
      setActiveBatchId(response.active_batch_id ?? null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load Campaign Batches');
    } finally {
      setIsLoadingBatches(false);
    }
  };

  const selectBatch = (batch: BatchSummary) => {
    if (!['PAUSED', 'FAILED_REQUIRES_USER'].includes(batch.status)) return;
    setConfig(prev => ({
      ...prev,
      batch_id: batch.batch_id,
      new_batch: false,
      resume_mode: 'required',
      batch_mode: '',
      target_lineage_id: '',
    }));
  };

  const changeBatchArchive = async (
    batch: BatchSummary,
    archive: boolean,
  ) => {
    const campaignId = config.campaign_id.trim();
    if (!campaignId) return;
    try {
      if (archive) {
        await apiService.archiveBatch(campaignId, batch.batch_id);
      } else {
        await apiService.unarchiveBatch(campaignId, batch.batch_id);
      }
      await loadCampaignBatches();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update Batch archive');
    }
  };

  const validateForm = (): string | null => {
    if (!files.pdf_file) return 'Please upload a PDF paper';
    if (!files.logo_file) return 'Please upload a conference logo';
    if (!files.aff_logo_file) return 'Please upload an affiliation logo';
    
    const ratio = config.poster_width / config.poster_height;
    if (ratio < 1.4 || ratio > 2.0) {
      return `Poster ratio ${ratio.toFixed(2)} is out of range (1.4 - 2.0)`;
    }
    
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setCurrentJob(null);

    try {
      const jobStatus = await apiService.generatePoster(config, files);
      setCurrentJob(jobStatus);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start poster generation');
      setIsSubmitting(false);
    }
  };

  const handleLoopAction = async (action: 'pause' | 'resume' | 'stop' | 'force-stop') => {
    if (!currentJob) return;
    try {
      await apiService.controlLoop(currentJob.job_id, action);
      setCurrentJob(await apiService.getJobStatus(currentJob.job_id));
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to ${action} optimization loop`);
    }
  };

  const canSubmit = files.pdf_file && files.logo_file && files.aff_logo_file && !isSubmitting;

  return (
    <div className="container">
      <div className="header">
        <h1 style={{display: 'flex', alignItems: 'center', justifyContent: 'center'}}><img src={postergenLogo} alt="PosterGen Logo" style={{height: '1.5em', marginRight: '0.5em'}} />PosterGen WebUI</h1>
        <p>🎨 Generate design-aware academic posters from PDF papers</p>
      </div>

      <form onSubmit={handleSubmit} className="main-form">
        <div className="form-section">
          <h3 className="section-title">📄 Upload Files</h3>
          
          <div className="form-group">
            <label>PDF Paper</label>
            <FileUpload
              label="PDF Paper"
              accept="application/pdf"
              selectedFile={files.pdf_file}
              onFileSelect={(file) => handleFileChange('pdf_file', file)}
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Conference Logo</label>
              <FileUpload
                label="Logo"
                accept="image/*"
                selectedFile={files.logo_file}
                onFileSelect={(file) => handleFileChange('logo_file', file)}
              />
            </div>
            
            <div className="form-group">
              <label>Affiliation Logo</label>
              <FileUpload
                label="Affiliation Logo"
                accept="image/*"
                selectedFile={files.aff_logo_file}
                onFileSelect={(file) => handleFileChange('aff_logo_file', file)}
              />
            </div>
          </div>
        </div>

        <div className="form-section">
          <h3 className="section-title">🤖 Model Configuration</h3>
          
          <div className="form-row">
            <div className="form-group">
              <label>Text Model</label>
              <select
                value={config.text_model}
                onChange={(e) => handleConfigChange('text_model', e.target.value)}
              >
                {availableModels.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
            
            <div className="form-group">
              <label>Vision Model</label>
              <select
                value={config.vision_model}
                onChange={(e) => handleConfigChange('vision_model', e.target.value)}
              >
                {availableModels.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="form-section">
          <h3 className="section-title">📐 Poster Dimensions</h3>
          
          <div className="form-row">
            <div className="form-group">
              <label>Width (inches)</label>
              <input
                type="number"
                min="20"
                max="100"
                step="0.1"
                value={config.poster_width}
                onChange={(e) => handleConfigChange('poster_width', parseFloat(e.target.value) || 54)}
              />
            </div>
            
            <div className="form-group">
              <label>Height (inches)</label>
              <input
                type="number"
                min="10"
                max="60"
                step="0.1"
                value={config.poster_height}
                onChange={(e) => handleConfigChange('poster_height', parseFloat(e.target.value) || 36)}
              />
            </div>
          </div>
          
        </div>

        <div className="form-section loop-option-section">
          <label className="loop-option">
            <input
              type="checkbox"
              checked={config.continuous_loop}
              onChange={(e) => handleConfigChange('continuous_loop', e.target.checked)}
              disabled={isSubmitting}
            />
            <span>
              <strong>Resumable Critic optimization Batch</strong>
              <small>Runs a finite committed-iteration Batch. Quality never ends it early, and unfinished work resumes next launch.</small>
            </span>
          </label>
          {config.continuous_loop && (
            <>
            <div className="form-row">
              <div className="form-group">
                <label>Committed iterations in this Batch</label>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={config.batch_iterations}
                  onChange={(e) => handleConfigChange('batch_iterations', parseInt(e.target.value, 10) || 100)}
                  disabled={isSubmitting}
                />
                <small>Default 100. Interrupted attempts do not consume the budget.</small>
              </div>
              <div className="form-group">
                <label>Batch scheduling mode</label>
                <select
                  value={config.batch_mode}
                  onChange={(e) => handleConfigChange('batch_mode', e.target.value)}
                  disabled={isSubmitting}
                >
                  <option value="">Resume active mode / mixed for a new Batch</option>
                  <option value="mixed">Mixed portfolio</option>
                  <option value="explore">Pure new-route exploration</option>
                  <option value="improve">Pure Lineage improvement</option>
                  <option value="mutate">Pure structural mutation</option>
                  <option value="validate">Pure template validation</option>
                </select>
                <small>Mode is frozen for an unfinished Batch; pure validation stops when its queue is exhausted.</small>
              </div>
              <div className="form-group">
                <label>Target Lineage ID (optional)</label>
                <input
                  type="text"
                  value={config.target_lineage_id}
                  onChange={(e) => handleConfigChange('target_lineage_id', e.target.value)}
                  disabled={isSubmitting || !['improve', 'mutate'].includes(config.batch_mode)}
                />
              </div>
              <div className="form-group">
                <label>Exact Batch ID (optional)</label>
                <input
                  type="text"
                  value={config.batch_id}
                  onChange={(e) => handleConfigChange('batch_id', e.target.value)}
                  placeholder="e.g. batch_0004"
                  disabled={isSubmitting || config.new_batch}
                />
                <small>Required when a Campaign has multiple paused Batches.</small>
              </div>
              <div className="form-group">
                <label className="loop-option">
                  <input
                    type="checkbox"
                    checked={config.new_batch}
                    onChange={(e) => handleConfigChange('new_batch', e.target.checked)}
                    disabled={isSubmitting || Boolean(config.batch_id)}
                  />
                  <span>
                    <strong>Create a new Batch</strong>
                    <small>Allocate the next permanent Batch ID while preserving paused Batches.</small>
                  </span>
                </label>
              </div>
              <div className="form-group">
                <label>Campaign start mode</label>
                <select
                  value={config.resume_mode}
                  onChange={(e) => handleConfigChange('resume_mode', e.target.value)}
                  disabled={isSubmitting}
                >
                  <option value="latest">Resume latest compatible campaign</option>
                  <option value="required">Require an existing campaign</option>
                  <option value="new">Start a new independent campaign</option>
                </select>
                <small>Compatibility uses the PDF, logos, poster size, and scientific-state schema.</small>
              </div>
              <div className="form-group">
                <label>Exact campaign ID (optional)</label>
                <input
                  type="text"
                  value={config.campaign_id}
                  onChange={(e) => handleConfigChange('campaign_id', e.target.value)}
                  placeholder="Leave blank to use the selected mode"
                  disabled={isSubmitting}
                />
                <small>An exact ID resumes that campaign after compatibility validation.</small>
                <button
                  type="button"
                  onClick={loadCampaignBatches}
                  disabled={isSubmitting || isLoadingBatches || !config.campaign_id.trim()}
                >
                  {isLoadingBatches ? 'Loading Batches...' : 'Load Campaign Batches'}
                </button>
              </div>
              {batches.length > 0 && (
                <div className="form-group">
                  <label>Persisted Batches</label>
                  <div style={{ overflowX: 'auto' }}>
                    <table>
                      <thead>
                        <tr>
                          <th>Batch</th>
                          <th>Mode</th>
                          <th>Progress</th>
                          <th>Status</th>
                          <th>Target Lineage</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {batches.map(batch => (
                          <tr key={batch.batch_id}>
                            <td>
                              {batch.batch_id}
                              {activeBatchId === batch.batch_id ? ' (active)' : ''}
                            </td>
                            <td>{batch.mode}</td>
                            <td>{batch.completed_iterations}/{batch.target_iterations}</td>
                            <td>{batch.status}</td>
                            <td>{batch.target_lineage_id || '—'}</td>
                            <td>
                              {['PAUSED', 'FAILED_REQUIRES_USER'].includes(batch.status) && (
                                <button type="button" onClick={() => selectBatch(batch)}>
                                  Select
                                </button>
                              )}
                              {['PAUSED', 'FAILED_REQUIRES_USER'].includes(batch.status) && (
                                <button type="button" onClick={() => changeBatchArchive(batch, true)}>
                                  Archive
                                </button>
                              )}
                              {batch.status === 'ARCHIVED' && (
                                <button type="button" onClick={() => changeBatchArchive(batch, false)}>
                                  Unarchive
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => window.open(
                                  apiService.getBatchDetailsUrl(
                                    config.campaign_id.trim(),
                                    batch.batch_id,
                                  ),
                                  '_blank',
                                  'noopener,noreferrer',
                                )}
                              >
                                Details
                              </button>
                              {batch.report_available && (
                                <button
                                  type="button"
                                  onClick={() => window.open(
                                    apiService.getBatchReportUrl(
                                      config.campaign_id.trim(),
                                      batch.batch_id,
                                    ),
                                    '_blank',
                                    'noopener,noreferrer',
                                  )}
                                >
                                  Report
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <small>Selecting a resumable Batch fills the exact Batch ID; the paper inputs are still compatibility-checked when generation starts.</small>
                </div>
              )}
            </div>
            </>
          )}
        </div>

        <button
          type="submit"
          className="button"
          disabled={!canSubmit}
        >
          {isSubmitting ? 'Generating Poster...' : 'Generate Poster'}
        </button>
        {currentJob?.continuous_loop && ['processing', 'paused', 'stopping'].includes(currentJob.status) && (
          <div className="loop-control-panel">
            <div className="loop-metrics">
              <span>Iteration <strong>{currentJob.iteration}</strong></span>
              <span>Last completed <strong>{currentJob.last_completed_iteration}</strong></span>
              <span>Campaign <strong title={currentJob.campaign_id ?? ''}>{currentJob.campaign_id?.slice(-12) ?? '—'}</strong></span>
              <span>Launch <strong>{currentJob.resumed ? 'resumed' : 'new'}</strong></span>
              <span>Last score <strong>{currentJob.last_score ?? '—'}</strong></span>
              <span>Accepted <strong>{currentJob.accepted_count}</strong></span>
              <span>Batch <strong>{currentJob.batch_id ?? '—'}</strong></span>
              <span>Batch progress <strong>{currentJob.batch_completed_iterations}/{currentJob.batch_target_iterations}</strong></span>
              <span>Batch mode <strong>{currentJob.batch_mode ?? '—'}</strong></span>
              <span>Task mode <strong>{currentJob.portfolio_mode ?? '—'}</strong></span>
              <span>Family <strong>{currentJob.layout_family ?? '—'}</strong></span>
              <span>Lineage <strong>{currentJob.lineage_id?.slice(-18) ?? '—'}</strong></span>
            </div>
            <p>The Batch continues regardless of score until its committed budget is complete or you request stop.</p>
            <div className="loop-controls">
              {currentJob.status === 'paused' ? (
                <button type="button" onClick={() => handleLoopAction('resume')}>Resume</button>
              ) : (
                <button type="button" disabled={currentJob.status === 'stopping'} onClick={() => handleLoopAction('pause')}>Pause</button>
              )}
              <button type="button" disabled={currentJob.status === 'stopping'} onClick={() => handleLoopAction('stop')}>Pause Batch and stop</button>
              <button type="button" className="danger" onClick={() => handleLoopAction('force-stop')}>Force stop</button>
            </div>
          </div>
        )}

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {currentJob && currentJob.status !== 'failed' && (
          <ProgressBar
            message={currentJob.message}
            logs={logs}
            isActive={currentJob.status === 'processing' || currentJob.status === 'pending' || currentJob.status === 'stopping'}
          />
        )}

        {currentJob && currentJob.status === 'completed' && (
          <div className="download-section">
            <div className="success-message">
              Poster generation completed successfully!
            </div>
            <a
              href={apiService.getDownloadUrl(currentJob.job_id)}
              className="download-button"
              download
            >
              Download Poster Files
            </a>
          </div>
        )}
      </form>

      <div className="preview-wrapper">
        <div className="preview-section">
          <h3 className="section-title">📄 Meta Files</h3>
          <div className="json-viewer">
            {Object.keys(jsonFiles).length > 0 ? (
              Object.entries(jsonFiles).map(([filename, content]) => (
                <div key={filename} className="json-file">
                  <div
                    className="json-file-header"
                    onClick={() => toggleFileExpansion(filename)}
                  >
                    <span>{filename}</span>
                    <div>
                      <button
                        className="copy-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          copyToClipboard(JSON.stringify(content, null, 2));
                        }}
                      >
                        Copy
                      </button>
                      <span style={{ marginLeft: '8px' }}>
                        {expandedFiles.has(filename) ? '−' : '+'}
                      </span>
                    </div>
                  </div>
                  {expandedFiles.has(filename) && (
                    <div className="json-content">
                      <pre>{JSON.stringify(content, null, 2)}</pre>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="empty-state">
                {currentJob?.status === 'completed' 
                  ? 'No files available'
                  : 'JSON files will appear after generation'
                }
              </div>
            )}
          </div>
        </div>
        
        <div className="section-divider"></div>
        
        <div className="preview-section">
          <h3 className="section-title">🖼️ Poster Preview</h3>
          <div className="preview-content">
            {getPosterImageUrl() ? (
              <div className="preview-container">
                <img
                  src={getPosterImageUrl()!}
                  alt="Generated Poster"
                  className="poster-preview"
                />
              </div>
            ) : (
              <div className="empty-state">
                {currentJob?.status === 'processing' || currentJob?.status === 'pending' || currentJob?.status === 'paused' || currentJob?.status === 'stopping'
                  ? 'The best accepted poster will appear here after the first archive decision.'
                  : 'Upload files and generate a poster to see preview'
                }
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
