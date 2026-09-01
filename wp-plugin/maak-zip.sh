#!/bin/sh
# Bouwt snackspert-review-api.zip, klaar om te uploaden via
# wp-admin > Plugins > Nieuwe plugin > Plugin uploaden.
set -e
cd "$(dirname "$0")"
rm -rf build snackspert-review-api.zip
mkdir -p build/snackspert-review-api
cp snackspert-review-api.php build/snackspert-review-api/
cd build
zip -q -r ../snackspert-review-api.zip snackspert-review-api
cd ..
rm -rf build
echo "Gemaakt: $(pwd)/snackspert-review-api.zip"
