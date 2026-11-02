# Build pipeline — El Niño GHG Dashboard

The dashboard is one self-contained page, `dashboard-single.html`. A weekly GitHub Actions workflow
(`.github/workflows/refresh.yml`, copy of `refresh.yml.example`) re-downloads the data, rebuilds the data
blocks inside that page, tests it, and writes the GitHub Pages copy (`index.html` + `data/`).

## Credentials (GitHub repository secrets; never commit them)
| Secret | Used for |
|---|---|
| `EARTHDATA_TOKEN` | NASA GES DISC (OCO-2), OceanColor (VIIRS/PACE) — expires; regenerate at urs.earthdata.nasa.gov |
| `OPENAQ_API_KEY` | OpenAQ v3 (PM₂.₅ monitors) |
| `CDSE_S3_KEY`, `CDSE_S3_SECRET` | Copernicus Data Space S3 (Sentinel-3 NDVI) |

## Weekly steps (`run_all.sh`, in order)
`noaa` NOAA GML flask, observatory in-situ and Mauna Loa preliminary CO₂/CH₄ ·
`icos` ICOS Carbon Portal CO₂/CH₄ (+ platform and flask tags) · `openaq` PM₂.₅ monitors (incremental, weekly per site) ·
`stations` merges all station networks (carries SOCAT and PMEL forward) · `oco2` OCO-2 16-day 0.25° windows ·
`modis` MODIS NDVI anomaly images · `s3ndvi` Sentinel-3 NDVI dekads · `geoscf` GEOS-CF PM₂.₅ ·
`gibs` AIRS CO and monthly fire counts · `sst` GHRSST MUR SST anomaly · `enso` Niño indices, global CO₂/CH₄, CPC outlook ·
`cards` the four headline indicator cards · `fires` VIIRS 24-hour fires · `assemble` · `test` · `split`

Data steps are non-fatal: a provider outage is retried with backoff, then skipped (warning on the run, listed in
`failed_steps.txt`) and that layer keeps its previous data. The assembler never replaces a layer with data that end
earlier than what the page already shows. Only `assemble`, `test` and `split` stop a run; `test` runs on both the
single file and the GitHub Pages layout.

## Manual / occasional steps
| Command | When |
|---|---|
| `python3 build_all.py registries` then `assemble` | quarterly: FLUXNET2015/CH4, TCCON, COCCON, WAFNET, MexFlux site lists |
| `python3 build_all.py socat` then `stations`, `assemble` | each June (SOCAT annual release; update the version in the URL) |
| `chl_layer.py` | VIIRS chlorophyll anomaly (monthly; not yet in the weekly run) |
| `glwd_layer.py` | GLWD v2 wetlands (static) |

Hand-maintained blocks in the page: `d-other` (other flux towers), `d-lsce` (LSCE EM27/SUN), `d-paf`
(PanAmazonFlux), `d-saeon` (SAEON-EFTEON). PACE chlorophyll/NDVI, PMEL moorings and BGC-Argo were built
interactively and are not yet refreshed automatically.

## claude.ai copy
`python3 make_lite.py ../dashboard-single.html <out.html>` makes the reduced copy (image basemaps re-encoded smaller) that fits the 16 MB limit of a claude.ai artifact.

## Dry run
`dryrun.yml` (manual trigger) runs `STEPS="enso fires grids assemble"` against the cached data in about two minutes,
without committing — use it after changing scripts.

## How this was made
This dashboard, its data pipeline and the weekly refresh were created using Claude Fable 5 (Anthropic), working with
Ben Poulter (Spark Climate Solutions).
