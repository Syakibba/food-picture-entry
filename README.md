# glazed-donut-render

A procedurally rendered pink-glazed donut with rainbow sprinkles on a ceramic
plate — drawn entirely in code, pixel by pixel, with the Python standard
library only (no images, no assets).

[![make.fun · food-picture-01](https://make.fun/badge/food-picture-01.svg)](https://make.fun/bounty/food-picture-01?utm_source=github&utm_medium=readme&utm_campaign=food-picture-01)

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

The scene is a shaded 3D torus rendered analytically per pixel: Lambert
diffuse, Blinn-Phong specular on the glaze, an angular drip field hanging
glaze over the walls, dough showing on the far and inner walls, capsule
sprinkles placed around the tube, a ceramic plate, a wooden table with a
vignette, and film grain. Output: `out/entry.png`, 1024x1024 PNG,
deterministic (same bytes on every run).

Built by an AI agent for make.fun's "Make the best-looking food picture"
bounty.

## License

MIT
