#!/usr/bin/env bash
# Rebuilds every data layer and assembles index.html.  Needs: EARTHDATA_TOKEN, OPENAQ_API_KEY,
# AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (CDSE S3).  Runtime ~60-90 min (OpenAQ + OCO-2 dominate).
set -euo pipefail
cd "$(dirname "$0")"
export GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR AWS_S3_ENDPOINT=${AWS_S3_ENDPOINT:-eodata.dataspace.copernicus.eu} AWS_VIRTUAL_HOSTING=FALSE AWS_HTTPS=YES
STEPS=${STEPS:-noaa icos openaq oco2 modis s3ndvi geoscf gibs enso fires assemble}
for s in $STEPS; do echo "=== $s ==="; python3 build_all.py "$s"; done
