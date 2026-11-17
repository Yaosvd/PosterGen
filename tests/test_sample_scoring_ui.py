"""The UI displays each result's frozen scoring scale without guessing its age."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest


def test_score_labels_keep_mixed_versions_and_missing_policy_distinct():
    root = Path(__file__).resolve().parents[1]
    frontend = root / 'webui' / 'frontend'
    if not shutil.which('node') or not (frontend / 'node_modules' / 'typescript').is_dir():
        pytest.skip('Node and installed frontend dependencies are required')
    script = r"""
      const fs = require('node:fs');
      const ts = require('typescript');
      const source = fs.readFileSync('src/sampleScoreDisplay.ts', 'utf8');
      const js = ts.transpileModule(source, {
        compilerOptions: {module: ts.ModuleKind.CommonJS},
      }).outputText;
      const compiled = {exports: {}};
      new Function('module', 'exports', js)(compiled, compiled.exports);
      const {scoreLabel, groupLabel} = compiled.exports;
      const rows = [
        {score: 80, score_maximum: 100, high_score_threshold: 80, grouping: 'high_score'},
        {score: 81, score_maximum: 96, high_score_threshold: 82, grouping: 'low_score'},
        {score: 82, score_maximum: 96, high_score_threshold: 82, grouping: 'high_score'},
        {score: 0, score_maximum: 96, high_score_threshold: 82, grouping: 'low_score'},
        {score: null, score_maximum: 96, high_score_threshold: 82, grouping: 'evaluation_failed'},
        {score: 95, grouping: 'high_score'},
        {score: null, grouping: 'unclassified'},
      ];
      process.stdout.write(JSON.stringify(rows.map(row => [scoreLabel(row), groupLabel(row)])));
    """
    result = subprocess.run(['node', '-e', script], cwd=frontend, text=True,
                            capture_output=True, check=True)
    assert json.loads(result.stdout) == [
        ['80 / 100', 'High (≥80)'],
        ['81 / 96', 'Low (<82)'],
        ['82 / 96', 'High (≥82)'],
        ['0 / 96', 'Low (<82)'],
        ['Unavailable', 'Failed / incomplete'],
        ['95 (scale unavailable)', 'High (threshold unavailable)'],
        ['Unavailable', 'No poster'],
    ]
