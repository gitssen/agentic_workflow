package main

import (
	"context"
	"log"
	"os"

	"cloud.google.com/go/firestore"
	"github.com/joho/godotenv"
	"google.golang.org/api/iterator"
)

func main() {
	_ = godotenv.Load()

	ctx := context.Background()
	projectID := os.Getenv("GOOGLE_PROJECT_ID")
	if projectID == "" {
		projectID = os.Getenv("GOOGLE_CLOUD_PROJECT")
	}
	databaseID := os.Getenv("FIRESTORE_DATABASE_ID")
	if databaseID == "" {
		databaseID = "default"
	}

	if projectID == "" {
		log.Fatal("GOOGLE_CLOUD_PROJECT or GOOGLE_PROJECT_ID environment variable not set.")
	}

	log.Printf("Connecting to Firestore (Project: %s, Database: %s)...\n", projectID, databaseID)
	client, err := firestore.NewClientWithDatabase(ctx, projectID, databaseID)
	if err != nil {
		log.Fatalf("Firestore client error: %v", err)
	}
	defer client.Close()

	col := client.Collection("songs")
	log.Println("Starting deletion of 'songs' collection...")

	batchSize := 20
	totalDeleted := 0

	for {
		iter := col.Limit(batchSize).Documents(ctx)
		numDeleted := 0
		batch := client.Batch()

		for {
			doc, err := iter.Next()
			if err == iterator.Done {
				break
			}
			if err != nil {
				log.Fatalf("Error iterating documents: %v", err)
			}

			batch.Delete(doc.Ref)
			numDeleted++
		}

		if numDeleted == 0 {
			break
		}

		_, err := batch.Commit(ctx)
		if err != nil {
			log.Fatalf("Error committing batch delete: %v", err)
		}

		totalDeleted += numDeleted
		log.Printf("Deleted %d documents so far...", totalDeleted)
	}

	log.Printf("Successfully deleted %d documents from 'songs' collection.\n", totalDeleted)
}
