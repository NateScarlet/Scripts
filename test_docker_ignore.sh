#!/bin/bash
set -ex

# https://stackoverflow.com/a/40966234
id=$(docker image build -q -f - . << EOF
FROM busybox
COPY . /build-context
WORKDIR /build-context
CMD find .
EOF
)

docker run --rm $id sh -c 'du -a | sort -g'
docker rmi $id
