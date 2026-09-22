# Layout-family skeletons

These twelve PNG/PPTX pairs visualize the *initial* normalized zones in
`src/layout/families.py`. They are not scored or approved poster templates.
The PPTX files contain editable PowerPoint shapes, not flattened screenshots.
The classic three-column preview is a schematic of the preserved renderer's
three-column geometry; final module heights and visual positions depend on
paper content and Critic-guided iteration.

After editing the family registry, regenerate all pairs from the repository
root:

```bash
.venv/bin/python -m src.templates.preview
```

Critic-accepted candidate templates are stored separately in
`storage/critic_loop/accepted_posters/<candidate_id>/template.{json,png,pptx}`.
Those previews show generic module and visual placement but no scientific text
or original figure pixels.
