#!/bin/bash

# Configuration
PROJECT_ID=$(gcloud config get-value project)
DATABASE_ID="default"
DIMENSION=768

if [ -z "$PROJECT_ID" ]; then
    echo "Error: No active gcloud project found. Run 'gcloud config set project YOUR_PROJECT_ID' first."
    exit 1
fi

create_index() {
    local COLLECTION_ID=$1
    echo "Creating Vector Index for collection: $COLLECTION_ID..."
    
    gcloud firestore indexes composite create \
        --project="$PROJECT_ID" \
        --database="$DATABASE_ID" \
        --collection-group="$COLLECTION_ID" \
        --query-scope=COLLECTION \
        --field-config=field-path="embedding",vector-config='{"dimension": "'$DIMENSION'", "flat": "{}"}'
}

# 1. Index for tool discovery
create_index "tools"

# 2. Index for song discovery (New)
create_index "songs"

echo "--------------------------------------------------------"
echo "Index creation started for 'tools' and 'songs'!"
echo "It may take a few minutes for Firestore to build them."
echo "Check status: gcloud firestore indexes composite list"
echo "--------------------------------------------------------"
