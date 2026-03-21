#!/bin/bash

# Configuration
PROJECT_ID=$(gcloud config get-value project)
DATABASE_ID="default"  # Use 'default' without parentheses for the gcloud flag
COLLECTION_ID="tools"
FIELD_PATH="embedding"
DIMENSION=768 # text-embedding-004 default

if [ -z "$PROJECT_ID" ]; then
    echo "Error: No active gcloud project found. Run 'gcloud config set project YOUR_PROJECT_ID' first."
    exit 1
fi

echo "Creating Vector Index for project: $PROJECT_ID..."
echo "Database: $DATABASE_ID | Collection: $COLLECTION_ID | Field: $FIELD_PATH | Dimension: $DIMENSION"

# Create the vector index using gcloud firestore indexes composite create
# Note: For vector search, we use the 'flat' configuration for best accuracy with small toolsets.
gcloud firestore indexes composite create \
    --project="$PROJECT_ID" \
    --database="$DATABASE_ID" \
    --collection-group="$COLLECTION_ID" \
    --query-scope=COLLECTION \
    --field-config=field-path="$FIELD_PATH",vector-config='{"dimension": "'$DIMENSION'", "flat": "{}"}'

if [ $? -eq 0 ]; then
    echo "--------------------------------------------------------"
    echo "Index creation started successfully!"
    echo "It may take a few minutes to complete."
    echo "Check status: gcloud firestore indexes composite list"
    echo "--------------------------------------------------------"
else
    echo "Failed to start index creation. Check your gcloud permissions."
fi
