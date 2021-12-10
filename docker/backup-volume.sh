#!/bin/bash

set -ex
docker run --rm -v "$1:/v" -it alpine tar cvz -C /v .
