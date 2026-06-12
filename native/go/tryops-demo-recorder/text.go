package main

import (
	"image"
	"image/color"
	"os"
	"strings"

	"golang.org/x/image/font"
	"golang.org/x/image/font/opentype"
	"golang.org/x/image/math/fixed"
)

type fonts struct {
	Title font.Face
	H2    font.Face
	Body  font.Face
	Small font.Face
	Mono  font.Face
}

func loadFonts(path string) (fonts, error) {
	payload, err := os.ReadFile(path)
	if err != nil {
		return fonts{}, err
	}
	parsed, err := opentype.Parse(payload)
	if err != nil {
		return fonts{}, err
	}
	makeFace := func(size float64) (font.Face, error) {
		return opentype.NewFace(parsed, &opentype.FaceOptions{
			Size:    size,
			DPI:     96,
			Hinting: font.HintingFull,
		})
	}
	title, err := makeFace(30)
	if err != nil {
		return fonts{}, err
	}
	h2, err := makeFace(22)
	if err != nil {
		return fonts{}, err
	}
	body, err := makeFace(15)
	if err != nil {
		return fonts{}, err
	}
	small, err := makeFace(12)
	if err != nil {
		return fonts{}, err
	}
	mono, err := makeFace(13)
	if err != nil {
		return fonts{}, err
	}
	return fonts{Title: title, H2: h2, Body: body, Small: small, Mono: mono}, nil
}

func drawText(img *image.RGBA, face font.Face, x int, y int, text string, c color.Color) {
	d := &font.Drawer{
		Dst:  img,
		Src:  image.NewUniform(c),
		Face: face,
		Dot:  fixed.P(x, y),
	}
	d.DrawString(text)
}

func wrapText(face font.Face, text string, maxWidth int) []string {
	var lines []string
	for _, paragraph := range strings.Split(text, "\n") {
		words := strings.Fields(paragraph)
		if len(words) == 0 {
			lines = append(lines, "")
			continue
		}
		current := words[0]
		for _, word := range words[1:] {
			next := current + " " + word
			if font.MeasureString(face, next).Ceil() <= maxWidth {
				current = next
				continue
			}
			lines = append(lines, current)
			current = word
		}
		lines = append(lines, current)
	}
	return lines
}

func drawWrapped(img *image.RGBA, face font.Face, x int, y int, maxWidth int, lineHeight int, text string, c color.Color, maxLines int) int {
	lines := wrapText(face, text, maxWidth)
	for i, line := range lines {
		if maxLines > 0 && i >= maxLines {
			break
		}
		drawText(img, face, x, y+(i*lineHeight), line, c)
	}
	if maxLines > 0 && len(lines) > maxLines {
		return y + maxLines*lineHeight
	}
	return y + len(lines)*lineHeight
}
