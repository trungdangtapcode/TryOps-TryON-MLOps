package main

import (
	"net/http"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"
)

func TestCanonicalQuerySortsAndEscapes(t *testing.T) {
	values := url.Values{}
	values.Set("prefix", "dvc/files/md5/")
	values.Set("list-type", "2")

	got := canonicalQuery(values)

	if got != "list-type=2&prefix=dvc%2Ffiles%2Fmd5%2F" {
		t.Fatalf("canonical query = %q", got)
	}
}

func TestS3SignerAddsAuthorization(t *testing.T) {
	requestURL, _ := url.Parse("http://127.0.0.1:19000/tryops-artifacts?list-type=2&prefix=dvc%2F")
	req := mustNewGetRequest(t, requestURL.String())

	signS3Request(req, "tryops", "tryops123", "us-east-1", time.Date(2026, 6, 11, 22, 0, 0, 0, time.UTC))

	auth := req.Header.Get("Authorization")
	if !strings.HasPrefix(auth, "AWS4-HMAC-SHA256 Credential=tryops/20260611/us-east-1/s3/aws4_request") {
		t.Fatalf("unexpected authorization header: %q", auth)
	}
	if req.Header.Get("x-amz-content-sha256") != emptySHA256 {
		t.Fatalf("missing payload hash")
	}
}

func TestFlattenLockSummaryRecognizesDVCOutput(t *testing.T) {
	text := `schema: '2.0'
stages:
  validate_demo_manifest:
    outs:
    - path: reports/generated/vton-catvton-2026-06-11-001
      hash: md5
      md5: abc.dir
`
	tmp := t.TempDir()
	writeTestFile(t, tmp+"/dvc.lock", text)

	summary, err := summarizeDVCLock(tmp)
	if err != nil {
		t.Fatalf("summarize dvc.lock: %v", err)
	}
	if !summary.Present || !summary.ContainsDVCOut || !summary.HasOutputHash {
		t.Fatalf("unexpected lock summary: %+v", summary)
	}
}

func mustNewGetRequest(t *testing.T, rawURL string) *http.Request {
	t.Helper()
	req, err := http.NewRequest(http.MethodGet, rawURL, nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	return req
}

func writeTestFile(t *testing.T, path string, body string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatalf("write test file: %v", err)
	}
}
