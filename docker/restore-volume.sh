#!/bin/bash

set -x
cat $2 | docker run --rm -i -v "$1:/v" alpine tar xvzf - -C /v
