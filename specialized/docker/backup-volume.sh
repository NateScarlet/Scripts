#!/bin/bash

# https://github.com/moby/moby/issues/31417

set -ex
docker run --rm -v "$1:/v" alpine tar cz -C /v . > $2
