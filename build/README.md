# El Niño GHG Dashboard — data build scripts

These are the scripts used to build the embedded data snapshot for `index.html`.
They are provided as a starting point for refreshing the dashboard yourself; they
were written interactively, so expect to adapt paths and a few inline steps.

## Credentials (never commit these; use environment variables / GitHub secrets)
| Source | Credential | Used by |
|---|---|---|
| NASA Earthdata (GES DISC OCO-2 Fwd_FP / Lite) | `EARTHDATA_TOKEN` (Bearer) | OCO-2 step |
| Copernicus Data Space (Sentinel-3 NDVI 300 m) | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` for `eodata.dataspace.copernicus.eu` | `s3ndvi` step |
| OpenAQ v3 | `OPENAQ_API_KEY` | `openaq_fetch.py` |
| ICOS, NOAA GML, NASA GIBS, FIRMS CSV, GEOS-CF OPeNDAP, CPC | none | — |

## Pipeline (in order)
1. **NOAA GGRN** – download `co2_*` and `ch4_*_surface-flask_1_ccgg_month.txt` from
   `https://gml.noaa.gov/aftp/data/trace_gases/{co2,ch4}/flask/surface/txt/` into `noaa/` and `noaa_ch4/`;
   station table from `https://gml.noaa.gov/dv/site/?program=ccgg` saved as `noaa/sites.html`.
2. **ICOS** – SPARQL (`q1.rq`, `q2.rq`, `q3.rq`) for stations and CO2/CH4 L2 + NRT objects; hourly data via the
   portal's `/cpb` binary endpoint (anonymous works when `Referer`/`Origin` are set to the portal) – see `icos_ch4.py`
   (CO2 is identical with `co2` column). Output `icos.json`, `icos_ch4.json`.
3. **OpenAQ** – `openaq_fetch.py` (1 request/s; ~30 min for 1,800 sites) then `build_aq.py`.
4. **Stations bundle** – `build_stations.py` → `stations.json` (per-site `vars{co2,ch4,pm25}` with anomaly metrics).
5. **OCO-2** – list daily `OCO2_L2_Fwd_FP.11.3` (and `.11.2`, `OCO2_L2_Lite_FP.11.3r`) files on GES DISC,
   download with the Earthdata token, keep `xco2_quality_flag==0`, bin 16-day windows to 1° → `oco2_fwd.json`.
6. **MODIS NDVI** – `ndvi_hi.py` (GIBS WMS `MODIS_Terra_L3_NDVI_Monthly`, colour-map inversion, 5-yr same-month anomaly;
   latest month at 7200×3600, others 2880×1440) → `ndvi_hi/anom_*.png`, plus 2° value grids (`ndvi2.json`).
7. **Sentinel-3 NDVI** – CDSE S3 COGs `CLMS/bio-geophysical/vegetation_indices/ndvi_global_300m_10daily_v3/…`,
   read the 1/32 overview with rasterio (`/vsis3/`), DN×0.004−0.08, same-dekad 5-yr anomaly → `s3ndvi/anom_*.png`.
8. **GEOS-CF PM2.5** – `geoscf_fetch2.py` (OPeNDAP, 6-hourly samples at 2°; v2 analysis current, v1 for the baseline).
9. **AIRS CO + monthly fires** – `bg_fetch.py` (GIBS WMS; AIRS 500 hPa CO monthly, VIIRS thermal anomalies counted per cell).
10. **ENSO / global CO2** – CPC `wksst9120.for`, `oni.ascii.txt`; NOAA `co2_mm_gl.csv`, `co2_gr_gl.csv` → `enso.json`.
11. **VIIRS 24 h fires** – FIRMS global CSVs (SUOMI + NOAA-20), packed to int16 → `fires.json`.
12. **Assemble** – `build_all.py assemble` builds the grid JSONs, then replaces the data and image blocks inside `index.html` in place (the older `reference/assemble.py` + `template.html` route is kept for history); big JSON blocks are gzipped+base64 and decoded in
    the browser (`DecompressionStream`). The published page differs from `template.html` by later interactive edits;
    treat `index.html` in the repo as the authoritative page and `page_patch_example.py` as an example of how it was patched.

## Automating with GitHub Actions
A workflow could run steps 1–12 weekly on `ubuntu-latest` (≈60–90 min, dominated by OpenAQ and OCO-2 downloads),
with the four secrets above, and commit the regenerated `index.html`. A skeleton is in `.github/workflows/refresh.yml`.

## Caching and dry runs
`refresh.yml` caches `build/data`, `build/geoscf`, `build/airs`, `build/firesm` and `build/ndvi_hi` between runs
(key = year-month), so weekly runs only fetch what is new. `dryrun.yml` runs `STEPS="enso fires grids assemble"` in ~2 minutes
to validate the assembly after script changes, without committing anything.

## Layout
`build_all.py` + `run_all.sh` are the pipeline. `ndvi_hi.py`, `bg_fetch.py`, `geoscf_fetch2.py`, `s3ndvi.py` are called by it. Everything under `reference/` is kept only as a record of how the first snapshot was made and is not used by the workflow.

## Page layout on GitHub Pages
`dashboard-single.html` is the self-contained page (what the claude.ai artifact uses). `index.html` is a 0.3 MB shell
that loads the same data from `data/` (made by `split_page.py`). `test_page.py` smoke-tests the page in headless
Chromium before the workflow commits; the `refresh.yml.example` pip line installs Playwright for it.

## Registry layers
`python3 build_all.py registries` refreshes the FLUXNET2015 / FLUXNET-CH4, TCCON and COCCON site lists (not part of the weekly `STEPS`; run it quarterly or when a network changes, then `assemble`).
