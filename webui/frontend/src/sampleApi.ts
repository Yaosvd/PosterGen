import axios from 'axios';
import type { SampleConfig, SampleFiles, SampleJob } from './sampleTypes';
const base = 'http://localhost:8001';
const client = axios.create({ baseURL: base });
export const sampleApi = {
  async models(): Promise<{ models: string[]; default_text_model: string; default_vision_model: string }> {
    return (await client.get('/models')).data;
  },
  async generate(config: SampleConfig, files: SampleFiles): Promise<SampleJob> {
    const form = new FormData();
    for (const [key, value] of Object.entries(config)) {
      if (value !== '') form.append(key, String(value));
    }
    for (const [key, value] of Object.entries(files)) if (value) form.append(key, value);
    return (await client.post('/generate', form)).data;
  },
  async status(id: string): Promise<SampleJob> { return (await client.get(`/status/${id}`)).data; },
  async logs(id: string): Promise<string[]> { return (await client.get(`/logs/${id}`)).data.logs; },
  async files(id: string): Promise<Record<string, unknown>> { return (await client.get(`/files/${id}`)).data.files; },
  async control(id: string, action: string): Promise<void> { await client.post(`/control/${id}/${action}`); },
  artifact(run: string, poster: string, file: string): string {
    return `${base}/runs/${encodeURIComponent(run)}/posters/${encodeURIComponent(poster)}/${encodeURIComponent(file)}`;
  },
  download(id: string): string { return `${base}/download/${id}`; },
};
