#!/usr/bin/env bash
# Native build recipe. Its content participates in the shared cache identity.
set -euo pipefail

: "${SPA_ASEPRITE_VERSION:?}"
: "${SPA_ASEPRITE_SOURCE_SHA256:?}"
: "${SPA_ASEPRITE_INSTALL_DIR:?}"

sudo apt-get update -qq
sudo apt-get install -y \
  cmake ninja-build \
  libpixman-1-dev libfreetype6-dev libharfbuzz-dev zlib1g-dev \
  libx11-dev libxcursor-dev libxi-dev libxrandr-dev libgl1-mesa-dev \
  libfontconfig1-dev

archive="$RUNNER_TEMP/Aseprite-v${SPA_ASEPRITE_VERSION}-Source.zip"
source_dir="$RUNNER_TEMP/aseprite-source"
build_dir="$RUNNER_TEMP/aseprite-build"

curl --fail --location --retry 3 \
  --output "$archive" \
  "https://github.com/aseprite/aseprite/releases/download/v${SPA_ASEPRITE_VERSION}/Aseprite-v${SPA_ASEPRITE_VERSION}-Source.zip"
echo "${SPA_ASEPRITE_SOURCE_SHA256}  $archive" | sha256sum --check --strict
mkdir -p "$source_dir" "$build_dir" "$SPA_ASEPRITE_INSTALL_DIR/bin"
unzip -q "$archive" -d "$source_dir"

lscpu | awk -F: '/^Model name:/ {print "Build CPU:" $2}'
echo "Build CPUs: $(nproc)"
cmake -S "$source_dir" -B "$build_dir" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=clang-18 \
  -DCMAKE_CXX_COMPILER=clang++-18 \
  -DCMAKE_C_FLAGS_RELEASE="-O1 -DNDEBUG" \
  -DCMAKE_CXX_FLAGS_RELEASE="-O1 -DNDEBUG" \
  -DENABLE_TESTS=OFF \
  -DENABLE_SCRIPTING=ON \
  -DENABLE_CCACHE=OFF \
  -DLAF_BACKEND=none
time cmake --build "$build_dir" --target aseprite --parallel 2

cp "$build_dir/bin/aseprite" "$SPA_ASEPRITE_INSTALL_DIR/bin/aseprite"
cp -R "$source_dir/data" "$SPA_ASEPRITE_INSTALL_DIR/bin/data"
