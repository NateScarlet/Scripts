#!/bin/bash

set -e

# Function to display help information
show_help() {
    echo "Usage: $0 <owner/repo> <workflow_id>"
    echo "Enable a GitHub Actions workflow for a repository."
    echo
    echo "Arguments:"
    echo "  <owner/repo>    GitHub repository in format 'owner/repo'"
    echo "  <workflow_id>   The ID or filename of the workflow to enable"
    echo
    echo "Environment variables:"
    echo "  GITHUB_TOKEN    Personal access token with repo scope (required)"
    echo
    echo "Example:"
    echo "  $0 octocat/hello-world workflow.yml"
    exit 1
}

# Check if help is requested
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_help
fi

# Check if required parameters are provided
if [ $# -lt 2 ]; then
    echo "Error: Missing required arguments."
    echo
    show_help
fi

# Check if GITHUB_TOKEN is set
if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable is not set."
    echo "Please set your GitHub personal access token before running this script."
    echo
    show_help
fi

REPO=$1
WORKFLOW_ID=$2

# Make the API request
curl -L \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/$REPO/actions/workflows/$WORKFLOW_ID/enable"
