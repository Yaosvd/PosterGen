export interface SampleResult {
  run_id: string;
  sample_id: string;
  status: string;
  poster_id: string | null;
  layout_family: string;
  score: number | null;
  grouping: 'unclassified';
}
export interface SampleJob {
  job_id: string;
  status: 'pending' | 'processing' | 'paused' | 'stopping' | 'completed' | 'failed';
  progress: number;
  message: string;
  error?: string;
  sample_generation: boolean;
  run_id: string | null;
  planned_samples: number;
  finalized_samples: number;
  rendered_samples: number;
  scored_samples: number;
  failed_samples: number;
  iteration: number;
  layout_family: string | null;
  results: SampleResult[];
}
export interface SampleConfig {
  text_model: string;
  vision_model: string;
  poster_width: number;
  poster_height: number;
  sample_generation: boolean;
  samples: string;
  run_id: string;
  random_seed: string;
}
export interface SampleFiles {
  pdf_file: File | null;
  logo_file: File | null;
  aff_logo_file: File | null;
}
