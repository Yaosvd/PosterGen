# Layout-family skeletons

These fifteen PNG/PPTX pairs visualize the *initial* normalized zones in
`src/layout/families.py`. They are not scored or approved poster templates.
The PPTX files contain editable PowerPoint shapes, not flattened screenshots.
The classic three-column preview is a schematic of the preserved renderer's
three-column geometry; final module heights and visual positions depend on
paper content and bounded current-sample fitting and repairs.

After editing the family registry, regenerate all pairs from the repository
root:

```bash
.venv/bin/python -m src.layout.family_previews
```

All final sample posters are stored separately in
`storage/rubrics_samples/posters/<poster_id>/template.{json,png,pptx}` together
with the poster. Those previews use the actual final coordinates but generic
module/visual labels, without scientific text or original figure pixels.
They are inspection-only and never generation inputs. All fifteen families
share one coverage-first selection pool without priority tiers.
