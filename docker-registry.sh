#!/bin/bash

if [[ -z "$DOCKER_REGISTRY_URL" ]]; then
    read DOCKER_REGISTRY_URL
fi

list_repositories(){
    http --ignore-stdin --verify=no $DOCKER_REGISTRY_URL/v2/_catalog
}

list_tags() {
   if [[ -z $1 ]]; then
        echo "Usage: get_manifest REPOSITORY"
        return 1
    fi
    http --ignore-stdin --verify=no $DOCKER_REGISTRY_URL/v2/$1/tags/list
}

get_manifest(){
   if [[ -z $1 || -z $2 ]]; then
        echo "Usage: get_manifest REPOSITORY TAG"
        return 1
    fi
    http --ignore-stdin --verify=no GET $DOCKER_REGISTRY_URL/v2/$1/manifests/$2 
}

get_manifest_digest(){
    if [[ -z $1 || -z $2 ]]; then
        echo "Usage: get_manifest_digest REPOSITORY TAG"
        return 1
    fi
    http --ignore-stdin --verify=no -h HEAD $DOCKER_REGISTRY_URL/v2/$1/manifests/$2 \
        Accept:application/vnd.docker.distribution.manifest.v2+json \
    | egrep "^Docker-Content-Digest:" \
    | sed 's/^Docker-Content-Digest: //' 
}

delete_manifest(){
    if [[ -z $1 || -z $2 ]]; then
        echo "Usage: delete_manifest REPOSITORY TAG"
        return 1
    fi
    reference=$(get_manifest_digest $1 $2)
    http --ignore-stdin --verify=no DELETE $DOCKER_REGISTRY_URL/v2/$1/manifests/$reference
}
