package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"cloud.google.com/go/firestore"
	"github.com/dhowden/tag"
	"github.com/google/generative-ai-go/genai"
	"github.com/joho/godotenv"
	"google.golang.org/api/option"
)

var (
	parenRegex   = regexp.MustCompile(`\(.*?\)`)
	bracketRegex = regexp.MustCompile(`\[.*?\]`)
)

func getLocalArtURL(songID string) string {
	// Point to our backend endpoint that extracts art on the fly
	return fmt.Sprintf("http://192.168.1.100:8000/art/%s", songID)
}

// --- 1. Data Structures ---

type AudioFeatures struct {
	TempoBPM         float64 `firestore:"tempo_bpm"`
	SpectralCentroid float64 `firestore:"spectral_centroid"`
	EnergyRMSE       float64 `firestore:"energy_rmse"`
}

type Song struct {
	ID                   string           `firestore:"id"`
	Filepath             string           `firestore:"filepath"`
	Title                string           `firestore:"title"`
	TitleLowercase       string           `firestore:"title_lowercase"`
	Artist               string           `firestore:"artist"`
	ArtistLowercase      string           `firestore:"artist_lowercase"`
	Album                string           `firestore:"album"`
	Genre                string           `firestore:"genre"`
	Year                 int              `firestore:"year"`
	AlbumArtURL          string           `firestore:"album_art_url,omitempty"`
	AudioFeatures        AudioFeatures    `firestore:"audio_features"`
	DescriptionForSearch string           `firestore:"description_for_search"`
	Embedding            firestore.Vector64 `firestore:"embedding"`
}

type Job struct {
	Path string
}

// --- 2. Worker Logic ---

func worker(ctx context.Context, id int, jobs <-chan Job, results chan<- Song, wg *sync.WaitGroup, aiClient *genai.Client, processedCount *uint64, totalCount int64) {
	defer wg.Done()
	
	emModelName := os.Getenv("EMBEDDING_MODEL_ID")
	if emModelName == "" {
		emModelName = "models/gemini-embedding-001"
	} else if !strings.HasPrefix(emModelName, "models/") {
		emModelName = "models/" + emModelName
	}
	
	genModelName := os.Getenv("MODEL_ID")
	if genModelName == "" {
		genModelName = "models/gemini-2.5-flash"
	} else if !strings.HasPrefix(genModelName, "models/") {
		genModelName = "models/" + genModelName
	}

	emModel := aiClient.EmbeddingModel(emModelName)
	targetDim := 768
	if dimStr := os.Getenv("EMBEDDING_DIM"); dimStr != "" {
		if d, err := strconv.Atoi(dimStr); err == nil {
			targetDim = d
		}
	}
	emModel.TaskType = genai.TaskTypeRetrievalDocument
	
	genModel := aiClient.GenerativeModel(genModelName)

	for job := range jobs {
		// Increment counter atomically
		count := atomic.AddUint64(processedCount, 1)
		
		if count % 10 == 0 || count == uint64(totalCount) {
			log.Printf("[%d / %d] Processing: %s\n", count, totalCount, filepath.Base(job.Path))
		}

		// A. Metadata Extraction
		f, err := os.Open(job.Path)
		var title, artist, album, genre string
		var year int
		if err == nil {
			m, tagErr := tag.ReadFrom(f)
			if tagErr == nil {
				title = m.Title()
				artist = m.Artist()
				album = m.Album()
				genre = m.Genre()
				year = m.Year()
			}
			f.Close()
		}

		// Fallback to filename if title is missing
		if title == "" {
			title = strings.TrimSuffix(filepath.Base(job.Path), filepath.Ext(job.Path))
		}

		// B. Simple Audio Analysis (Placeholder)
		features := AudioFeatures{
			TempoBPM: 120.0, 
			EnergyRMSE: 0.5,
		}

		// C. Gemini-Powered Metadata & Description Inference
		prompt := fmt.Sprintf(`Analyze this song based on its metadata. Title: "%s", Artist: "%s", Album: "%s", Year: %d, Genre: "%s", Filepath: "%s". 
Act as an expert musicologist. Return a JSON object with these keys ONLY:
- "era": (e.g., "1980s", "Late 90s", "Classical")
- "primary_moods": (e.g., "Melancholic, Wistful, Energetic, Aggressive")
- "atmosphere": (e.g., "Dark, Cyberpunk, Cozy, Cinematic")
- "activities": (e.g., "Evening coding, Deep focus, Gym workout, Road trip")
- "instrumentation": (e.g., "Analog synths, Distorted electric guitars, Acoustic piano, Drum machine")
- "vocal_profile": (e.g., "Instrumental, High-pitched male vocals, Choral")`, title, artist, album, year, genre, job.Path)
		
		// Rate limiting for AI API - be conservative to avoid 429s
		time.Sleep(1 * time.Second)
		
		resp, err := genModel.GenerateContent(ctx, genai.Text(prompt))
		
		var aiMeta struct {
			Era             string `json:"era"`
			PrimaryMoods    string `json:"primary_moods"`
			Atmosphere      string `json:"atmosphere"`
			Activities      string `json:"activities"`
			Instrumentation string `json:"instrumentation"`
			VocalProfile    string `json:"vocal_profile"`
		}

		if err != nil {
			log.Printf("AI metadata inference failed for %s: %v", filepath.Base(job.Path), err)
		} else if len(resp.Candidates) > 0 {
			part := resp.Candidates[0].Content.Parts[0]
			if text, ok := part.(genai.Text); ok {
				cleanJSON := strings.TrimSpace(string(text))
				cleanJSON = strings.TrimPrefix(cleanJSON, "```json")
				cleanJSON = strings.TrimSuffix(cleanJSON, "```")
				cleanJSON = strings.TrimSpace(cleanJSON)
				_ = json.Unmarshal([]byte(cleanJSON), &aiMeta)
			}
		}

		description := fmt.Sprintf("Title: %s. Artist: %s. Album: %s. Year: %d. Genre: %s. Era: %s. Moods: %s. Atmosphere: %s. Instruments: %s. Vocals: %s. Good for: %s. Tempo: %.1f BPM.",
			title, artist, album, year, genre, aiMeta.Era, aiMeta.PrimaryMoods, aiMeta.Atmosphere, aiMeta.Instrumentation, aiMeta.VocalProfile, aiMeta.Activities, features.TempoBPM)
		
		if aiMeta.PrimaryMoods != "" {
			log.Printf("AI Inference for %s: %s | %s", filepath.Base(job.Path), aiMeta.PrimaryMoods, aiMeta.Activities)
		}

		// D. Generate Embedding
		res, err := emModel.EmbedContent(ctx, genai.Text(description))
		if err != nil {
			log.Printf("Embedding error for %s: %v", filepath.Base(job.Path), err)
			continue
		}

		// Truncate and convert to Vector64
		vals := res.Embedding.Values
		if len(vals) > targetDim {
			vals = vals[:targetDim]
		}
		emb64 := make(firestore.Vector64, len(vals))
		for i, v := range vals {
			emb64[i] = float64(v)
		}

		// E. Construct Song Object
		songID := strings.ReplaceAll(filepath.Base(job.Path), ".", "_")
		artURL := getLocalArtURL(songID)
		
		song := Song{
			ID:                   songID,
			Filepath:             job.Path,
			Title:                title,
			TitleLowercase:       strings.ToLower(title),
			Artist:               artist,
			ArtistLowercase:      strings.ToLower(artist),
			Album:                album,
			Genre:                genre,
			Year:                 year,
			AlbumArtURL:          artURL,
			AudioFeatures:        features,
			DescriptionForSearch: description,
			Embedding:            emb64,
		}

		results <- song
	}
}

// --- 3. Main Orchestrator ---

func main() {
	// Load .env file
	_ = godotenv.Load()

	ctx := context.Background()
	apiKey := os.Getenv("GEMINI_API_KEY")
	projectID := os.Getenv("GOOGLE_PROJECT_ID")
	if projectID == "" {
		projectID = os.Getenv("GOOGLE_CLOUD_PROJECT")
	}
	databaseID := os.Getenv("FIRESTORE_DATABASE_ID")
	if databaseID == "" {
		databaseID = "default"
	}

	if apiKey == "" || projectID == "" {
		log.Fatal("GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT environment variable not set.")
	}

	if len(os.Args) < 2 {
		log.Fatal("Usage: go run scripts/ingest_music.go <path_to_music_directory>")
	}
	musicDir := os.Args[1]

	isMusicFile := func(path string) bool {
		ext := strings.ToLower(filepath.Ext(path))
		return ext == ".mp3" || ext == ".flac" || ext == ".m4a" || ext == ".mp4" || ext == ".wav"
	}

	// Step 1: Preliminary Scan to get Total Count
	log.Println("🔍 Scanning directory for music files...")
	var totalFiles int64 = 0
	_ = filepath.Walk(musicDir, func(path string, info os.FileInfo, err error) error {
		if err != nil { return nil }
		if !info.IsDir() && isMusicFile(path) {
			totalFiles++
		}
		return nil
	})
	log.Printf("🎵 Found %d potential songs. Checking for existing records...\n", totalFiles)

	if totalFiles == 0 {
		log.Println("No supported music files found. Exiting.")
		return
	}

	// Clients
	fsClient, err := firestore.NewClientWithDatabase(ctx, projectID, databaseID)
	if err != nil {
		log.Fatalf("Firestore client: %v", err)
	}
	defer fsClient.Close()

	aiClient, err := genai.NewClient(ctx, option.WithAPIKey(apiKey))
	if err != nil {
		log.Fatalf("Gemini client: %v", err)
	}
	defer aiClient.Close()

	// Channels & Sync
	jobs := make(chan Job, 100)
	results := make(chan Song, 100)
	var wg sync.WaitGroup
	var processedCount uint64 = 0
	startTime := time.Now()

	// Start Workers
	numWorkers := 8
	for w := 1; w <= numWorkers; w++ {
		wg.Add(1)
		go worker(ctx, w, jobs, results, &wg, aiClient, &processedCount, totalFiles)
	}

	// Start Batch Ingester
	doneChan := make(chan bool)
	go func() {
		batch := fsClient.Batch()
		count := 0
		committedTotal := 0
		for song := range results {
			docRef := fsClient.Collection("songs").Doc(song.ID)
			batch.Set(docRef, song)
			count++

			if count >= 10 {
				_, err := batch.Commit(ctx)
				if err != nil {
					log.Fatalf("FATAL: Batch commit failure: %v. Failing early to prevent data inconsistency.", err)
				}
				committedTotal += count
				batch = fsClient.Batch()
				count = 0
				log.Printf("✅ DB SYNC: Committed %d songs so far...\n", committedTotal)
			}
		}
		if count > 0 {
			_, _ = batch.Commit(ctx)
			committedTotal += count
		}
		log.Printf("🏁 DB SYNC COMPLETE: Total %d songs stored in Firestore.\n", committedTotal)
		doneChan <- true
	}()

	// Producer: Walk and Pipe
	var toProcess int64 = 0
	var skipped int64 = 0
	
	_ = filepath.Walk(musicDir, func(path string, info os.FileInfo, err error) error {
		if err != nil { return nil }
		if !info.IsDir() && isMusicFile(path) {
			id := strings.ReplaceAll(filepath.Base(path), ".", "_")
			
			// Quick existence check
			doc, err := fsClient.Collection("songs").Doc(id).Get(ctx)
			if err == nil && doc.Exists() {
				skipped++
				if skipped % 50 == 0 {
					log.Printf("... Skipped %d existing songs", skipped)
				}
				return nil
			}
			
			toProcess++
			jobs <- Job{Path: path}
		}
		return nil
	})

	log.Printf("⏭️  Skipped %d already indexed files. Processing %d new files.\n", skipped, toProcess)
	
	// Update totalFiles for the final speed calculation
	totalFiles = toProcess

	close(jobs)
	wg.Wait()
	close(results)
	<-doneChan

	duration := time.Since(startTime)
	log.Printf("🚀 Ingestion finished in %v. Average speed: %.2f songs/sec\n", duration, float64(totalFiles)/duration.Seconds())
}
