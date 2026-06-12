package main

type storyboard struct {
	Metrics []metric `json:"metrics"`
	Steps   []step   `json:"steps"`
}

type metric struct {
	Label  string      `json:"label"`
	Value  interface{} `json:"value"`
	Detail string      `json:"detail,omitempty"`
	Tone   string      `json:"tone,omitempty"`
}

type step struct {
	ID              string   `json:"id"`
	Order           string   `json:"order"`
	Title           string   `json:"title"`
	Track           string   `json:"track"`
	Status          string   `json:"status"`
	Tone            string   `json:"tone"`
	Summary         string   `json:"summary"`
	OperatorLine    string   `json:"operatorLine"`
	Command         string   `json:"command"`
	PrimaryArtifact string   `json:"primaryArtifact"`
	Artifacts       []string `json:"artifacts"`
	Metrics         []metric `json:"metrics"`
	Transcript      []string `json:"transcript"`
}

type frameSummary struct {
	Index int    `json:"index"`
	Path  string `json:"path"`
	Title string `json:"title"`
	Kind  string `json:"kind"`
}

type encodeResult struct {
	Command    []string `json:"command"`
	ExitCode   int      `json:"exit_code"`
	OutputTail string   `json:"output_tail,omitempty"`
}

type videoReport struct {
	SchemaVersion   string         `json:"schema_version"`
	GeneratedAt     string         `json:"generated_at"`
	Passed          bool           `json:"passed"`
	StoryboardPath  string         `json:"storyboard_path"`
	VideoPath       string         `json:"video_path"`
	VideoBytes      int64          `json:"video_bytes"`
	VideoSHA256     string         `json:"video_sha256"`
	FrameCount      int            `json:"frame_count"`
	StepCount       int            `json:"step_count"`
	DurationSeconds int            `json:"duration_seconds"`
	Width           int            `json:"width"`
	Height          int            `json:"height"`
	FPS             int            `json:"fps"`
	Frames          []frameSummary `json:"frames"`
	Encoder         encodeResult   `json:"encoder"`
	Checks          []reportCheck  `json:"checks"`
}

type reportCheck struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail,omitempty"`
}
