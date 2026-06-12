package main

import (
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
)

func ensureDemoAssets(cfg config) error {
	if err := ensurePNG(cfg.PersonImagePath, drawPersonAsset); err != nil {
		return err
	}
	return ensurePNG(cfg.GarmentImagePath, drawGarmentAsset)
}

func ensurePNG(path string, draw func(*image.RGBA)) error {
	if path == "" {
		return nil
	}
	if _, err := os.Stat(path); err == nil {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	img := image.NewRGBA(image.Rect(0, 0, 256, 320))
	draw(img)
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	return png.Encode(file, img)
}

func drawPersonAsset(img *image.RGBA) {
	fill(img, color.RGBA{R: 241, G: 245, B: 249, A: 255})
	rect(img, 105, 34, 151, 80, color.RGBA{R: 216, G: 180, B: 142, A: 255})
	rect(img, 86, 88, 170, 210, color.RGBA{R: 64, G: 99, B: 143, A: 255})
	rect(img, 62, 92, 91, 190, color.RGBA{R: 198, G: 165, B: 128, A: 255})
	rect(img, 165, 92, 194, 190, color.RGBA{R: 198, G: 165, B: 128, A: 255})
	rect(img, 93, 210, 122, 295, color.RGBA{R: 41, G: 52, B: 72, A: 255})
	rect(img, 134, 210, 163, 295, color.RGBA{R: 41, G: 52, B: 72, A: 255})
}

func drawGarmentAsset(img *image.RGBA) {
	fill(img, color.RGBA{R: 248, G: 250, B: 252, A: 255})
	rect(img, 70, 70, 186, 250, color.RGBA{R: 29, G: 78, B: 216, A: 255})
	rect(img, 34, 92, 76, 170, color.RGBA{R: 37, G: 99, B: 235, A: 255})
	rect(img, 180, 92, 222, 170, color.RGBA{R: 37, G: 99, B: 235, A: 255})
	for y := 92; y < 240; y += 28 {
		rect(img, 68, y, 188, y+8, color.RGBA{R: 191, G: 219, B: 254, A: 255})
	}
}

func fill(img *image.RGBA, c color.RGBA) {
	bounds := img.Bounds()
	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			img.SetRGBA(x, y, c)
		}
	}
}

func rect(img *image.RGBA, x0 int, y0 int, x1 int, y1 int, c color.RGBA) {
	for y := y0; y < y1; y++ {
		for x := x0; x < x1; x++ {
			if image.Pt(x, y).In(img.Bounds()) {
				img.SetRGBA(x, y, c)
			}
		}
	}
}
