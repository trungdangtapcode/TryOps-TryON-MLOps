package main

import (
	"flag"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type config struct {
	Root            string
	StoryboardPath  string
	FramesDir       string
	VideoPath       string
	OutputPath      string
	FFmpegPath      string
	FontPath        string
	Width           int
	Height          int
	FPS             int
	SecondsPerFrame int
	Timeout         time.Duration
}

func parseConfig() config {
	cfg := config{}
	flag.StringVar(&cfg.Root, "root", getenv("TRYOPS_ROOT", "."), "repository root")
	flag.StringVar(&cfg.StoryboardPath, "storyboard", getenv("TRYOPS_DEMO_STORYBOARD", "web/src/professor_demo_storyboard.json"), "professor demo storyboard JSON")
	flag.StringVar(&cfg.FramesDir, "frames-dir", getenv("TRYOPS_DEMO_VIDEO_FRAMES_DIR", "artifacts/demo/professor_demo_video/frames"), "rendered frame output directory")
	flag.StringVar(&cfg.VideoPath, "video", getenv("TRYOPS_DEMO_VIDEO", "artifacts/demo/professor_demo_video/professor_demo_backup.mp4"), "MP4 backup demo output path")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_DEMO_VIDEO_REPORT", "artifacts/eval/demo_video/professor_demo_video.json"), "JSON report output path")
	flag.StringVar(&cfg.FFmpegPath, "ffmpeg", getenv("TRYOPS_FFMPEG", "ffmpeg"), "ffmpeg binary path")
	flag.StringVar(&cfg.FontPath, "font", getenv("TRYOPS_DEMO_FONT", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), "TrueType/OpenType font path")
	flag.IntVar(&cfg.Width, "width", 1280, "video width")
	flag.IntVar(&cfg.Height, "height", 720, "video height")
	flag.IntVar(&cfg.FPS, "fps", 30, "encoded video frame rate")
	flag.IntVar(&cfg.SecondsPerFrame, "seconds-per-frame", 2, "seconds to hold each rendered frame")
	flag.DurationVar(&cfg.Timeout, "timeout", 2*time.Minute, "recorder timeout")
	flag.Parse()

	cfg.Root = cleanRoot(cfg.Root)
	cfg.StoryboardPath = resolvePath(cfg.Root, cfg.StoryboardPath)
	cfg.FramesDir = resolvePath(cfg.Root, cfg.FramesDir)
	cfg.VideoPath = resolvePath(cfg.Root, cfg.VideoPath)
	cfg.OutputPath = resolvePath(cfg.Root, cfg.OutputPath)
	return cfg
}

func getenv(key string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func cleanRoot(root string) string {
	root = strings.TrimSpace(root)
	if root == "" {
		root = "."
	}
	abs, err := filepath.Abs(root)
	if err != nil {
		return root
	}
	return abs
}

func resolvePath(root string, path string) string {
	path = strings.TrimSpace(path)
	if path == "" || filepath.IsAbs(path) {
		return path
	}
	return filepath.Join(root, path)
}

func relPath(root string, path string) string {
	rel, err := filepath.Rel(root, path)
	if err != nil {
		return path
	}
	return filepath.ToSlash(rel)
}
