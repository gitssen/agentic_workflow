package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	"github.com/dhowden/tag"
)

func main() {
	if len(os.Args) < 2 {
		log.Fatal("Usage: go run scripts/check_art.go <path_to_music_directory>")
	}
	musicDir := os.Args[1]

	isMusicFile := func(path string) bool {
		ext := strings.ToLower(filepath.Ext(path))
		return ext == ".mp3" || ext == ".flac" || ext == ".m4a" || ext == ".mp4" || ext == ".wav"
	}

	count := 0
	_ = filepath.Walk(musicDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || !isMusicFile(path) {
			return nil
		}
		if count >= 10 {
			return filepath.SkipDir
		}

		f, err := os.Open(path)
		if err != nil {
			return nil
		}
		defer f.Close()

		m, err := tag.ReadFrom(f)
		if err != nil {
			return nil
		}

		p := m.Picture()
		hasArt := "No"
		if p != nil {
			hasArt = fmt.Sprintf("Yes (%s, %s)", p.MIMEType, p.Ext)
		}

		fmt.Printf("File: %s\n  Artist: %s\n  Album: %s\n  Embedded Art: %s\n\n", 
			filepath.Base(path), m.Artist(), m.Album(), hasArt)
		
		count++
		return nil
	})
}
