#!/bin/bash

docker run --rm -i -v "$1:/v" alpine tar xvz -C /v
