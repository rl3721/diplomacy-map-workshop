# Map workshop design

`concept.png` is the full-screen visual concept, generated with the built-in Image Gen tool.
The interface is implemented as native HTML controls and generated SVG map output, not as a screenshot.

Design system: white panels on `#f2f4f3`, `#253c39` text, `#22695d` primary controls,
Segoe UI with system fallbacks, 13px control labels, 23px section headings, 6px control corners,
a 365px settings sidebar, and a flexible map workspace. Repeated control families are segmented
buttons, labeled sliders, numeric inputs, checkboxes, disclosures, and optional seed inputs.

Concept brief: a complete local Diplomacy map editor named Map workshop. Header with Load settings,
Save settings, Generate map. Separate Terrain and Provinces regions in the left sidebar, with preset
buttons, sliders, wrap/exact-count checkboxes, advanced controls, and optional independent seeds.
Main workspace with Elevation, Cleaned terrain, and Provinces tabs, Fit/zoom controls, Download SVG,
and a large map canvas. A real-statistics strip sits below the map, followed by reserved Supply centers
and Powers panels. A footer shows generation status and saved seeds. Clean, restrained, neutral light
appearance; no marketing sections or decorative artwork.

Functional extensions to the concept: an empty state before first generation, actual progress and
error messages, a derived-target summary, a score/details dialog, keyboard tab navigation, and a
responsive stacked layout. These support the required generation workflow. Actual SVGs retain their
native aspect ratio and colors; their geography, province labels, and reported statistics come from
the generator. Slider positions reflect their numerical ranges rather than the illustrative mockup.
