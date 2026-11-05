---
description: Build an interactive 3D simulator of a real machine or mechanism you can take apart
---

Build an interactive 3D simulator of the requested machine, mechanism or physical system ($ARGUMENTS).

Follow the Teardown instructions in `skills/teardown/SKILL.md`:
1. Model the machine as one offline HTML page (Three.js + CSS overlay) people can take apart.
2. Ground everything in real physical dimensions and kinematic equations (`kin.js` / math first). One input drives all poses, gauges, and charts.
3. Include cutaway modes (glass/section/solid), interactive buttons for every subsystem, telemetry dials with real numbers, and an auto-tour mode with cursor that hands over control on visitor click/drag.
4. Reuse the modular architecture: `<name>-shared/`, `<name>-live/`, `<name>-film/`.
5. Kit runtime: `import {runSim} from 'skills/teardown/sims/kit/runtime.js'`. Build with `node skills/teardown/sims/build.mjs <machine-name>-live`.
