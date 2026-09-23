export interface JobStatus {
  job_id: string;
  status: 'pending' | 'processing' | 'paused' | 'stopping' | 'completed' | 'failed';
  progress: number;
  message: string;
  error?: string;
  continuous_loop: boolean;
  iteration: number;
  last_score?: number | null;
  accepted_count: number;
  campaign_id?: string | null;
  resumed: boolean;
  last_completed_iteration: number;
  attempt_number?: number | null;
  batch_id?: string | null;
  batch_completed_iterations: number;
  batch_target_iterations: number;
  layout_family?: string | null;
  lineage_id?: string | null;
  portfolio_mode?: string | null;
  batch_mode?: string | null;
  batch_status?: string | null;
}

export interface PosterConfig {
  text_model: string;
  vision_model: string;
  poster_width: number;
  poster_height: number;
  continuous_loop: boolean;
  resume_mode: 'latest' | 'required' | 'new';
  campaign_id: string;
  batch_iterations: number;
  batch_mode: '' | 'mixed' | 'explore' | 'improve' | 'mutate' | 'validate';
  target_lineage_id: string;
  batch_id: string;
  new_batch: boolean;
}

export interface UploadedFiles {
  pdf_file: File | null;
  logo_file: File | null;
  aff_logo_file: File | null;
}

export interface ModelOptions {
  models: string[];
  default_text_model: string;
  default_vision_model: string;
}
