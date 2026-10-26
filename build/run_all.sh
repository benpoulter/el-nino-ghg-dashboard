#!/usr/bin/env bash
# Rebuilds every data layer and assembles the page.  Needs: EARTHDATA_TOKEN, OPENAQ_API_KEY,
# AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (CDSE S3).
# A failing data-source step is reported (GitHub warning annotation + failed_steps.txt) and skipped:
# the page keeps that layer's previous data.  assemble / test / split must succeed.
set -uo pipefail
cd "$(dirname "$0")"
export BUILD_START=${BUILD_START:-$(date +%s)} BUILD_BUDGET_MIN=${BUILD_BUDGET_MIN:-150}
export GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR AWS_S3_ENDPOINT=${AWS_S3_ENDPOINT:-eodata.dataspace.copernicus.eu} AWS_VIRTUAL_HOSTING=FALSE AWS_HTTPS=YES
STEPS=${STEPS:-noaa icos openaq stations oco2 modis s3ndvi geoscf gibs sst enso fires assemble test split}
CRITICAL=" assemble test split "
: > failed_steps.txt
for s in $STEPS; do
  echo "=== $s ==="
  if ! python3 build_all.py "$s"; then
    if [[ "$CRITICAL" == *" $s "* ]]; then echo "::error::step '$s' failed - page not updated"; exit 1; fi
    echo "::warning::data step '$s' failed - that layer keeps its previous data this week"
    echo "$s" >> failed_steps.txt
  fi
done
if [ -s failed_steps.txt ]; then echo "Completed with failed data steps: $(tr '\n' ' ' < failed_steps.txt)"; else echo "All steps completed."; fi
