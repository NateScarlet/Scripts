#!/bin/bash

set -ex;

CURRENT_TIMESTAMP=$(date +%s)

remove_dangling_containers() {
    local filter="$1"
    local timeout_secs="${2:-7200}"
    if [ -z "$filter" ]; then
        echo "筛选条件为必填"
        exit 1
    fi
    # 处理容器
    docker ps --filter "$filter" --format '{{.ID}}\t{{.CreatedAt}}' | while IFS='\t' read -r id timestamp; do
        # 转换时间戳为Unix时间
        container_timestamp=$(date -d "$timestamp" +%s 2>/dev/null)
        
        # 计算时间差并判断是否超时
        if [ -n "$container_timestamp" ] && \
           [ $((CURRENT_TIMESTAMP - container_timestamp)) -ge $timeout_secs ]; then
            echo "删除容器 $id (创建时间: $timestamp)"
            docker rm -f "$id"
        fi
    done
}

remove_dangling_volumes() {
    local filter="$1"
    if [ -z "$filter" ]; then
        echo "筛选条件为必填"
        exit 1
    fi

    docker volume ls --filter "$filter" --format '{{.Name}}' | while read -r volume; do
        if [ -z "$(docker ps -a --filter "volume=$volume" --format '{{.ID}}')" ]; then
            echo "Removing unused volume: $volume"
            docker volume rm "$volume"
        fi
    done
}

remove_dangling_containers "name=buildx_buildkit_builder-" $((24*3600))
remove_dangling_volumes "name=buildx_buildkit_builder-" 
remove_dangling_containers "name=GITEA-ACTIONS-TASK-" 7200
remove_dangling_volumes "name=GITEA-ACTIONS-TASK-"
