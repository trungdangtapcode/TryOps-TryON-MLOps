package main

import (
	"encoding/xml"
	"fmt"
	"net/http"
	"net/url"
	"path"
	"sort"
	"strconv"
	"strings"
	"time"
)

type listBucketResult struct {
	XMLName               xml.Name        `xml:"ListBucketResult"`
	IsTruncated           bool            `xml:"IsTruncated"`
	NextContinuationToken string          `xml:"NextContinuationToken"`
	Contents              []s3ObjectEntry `xml:"Contents"`
}

type s3ObjectEntry struct {
	Key  string `xml:"Key"`
	Size int64  `xml:"Size"`
}

func summarizeRemoteCache(remote DVCRemote, accessKey string, secretKey string, region string) (CacheSummary, error) {
	prefix := path.Join(remote.Prefix, "files", "md5")
	if prefix != "" {
		prefix += "/"
	}
	var summary CacheSummary
	continuation := ""
	client := http.Client{Timeout: 10 * time.Second}
	for {
		result, err := listObjectsPage(client, remote, prefix, continuation, accessKey, secretKey, region)
		if err != nil {
			return summary, err
		}
		for _, object := range result.Contents {
			summary.Count++
			summary.TotalBytes += object.Size
			if len(summary.Samples) < 8 {
				summary.Samples = append(summary.Samples, object.Key)
			}
		}
		if !result.IsTruncated || result.NextContinuationToken == "" {
			break
		}
		continuation = result.NextContinuationToken
	}
	sort.Strings(summary.Samples)
	return summary, nil
}

func listObjectsPage(
	client http.Client,
	remote DVCRemote,
	prefix string,
	continuation string,
	accessKey string,
	secretKey string,
	region string,
) (listBucketResult, error) {
	endpoint := strings.TrimRight(remote.Endpoint, "/")
	requestURL, err := url.Parse(endpoint + "/" + remote.Bucket)
	if err != nil {
		return listBucketResult{}, fmt.Errorf("parse S3 endpoint: %w", err)
	}
	query := requestURL.Query()
	query.Set("list-type", "2")
	query.Set("prefix", prefix)
	if continuation != "" {
		query.Set("continuation-token", continuation)
	}
	requestURL.RawQuery = query.Encode()

	req, err := http.NewRequest(http.MethodGet, requestURL.String(), nil)
	if err != nil {
		return listBucketResult{}, fmt.Errorf("build ListObjectsV2 request: %w", err)
	}
	signS3Request(req, accessKey, secretKey, region, time.Now())
	resp, err := client.Do(req)
	if err != nil {
		return listBucketResult{}, fmt.Errorf("ListObjectsV2 request failed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return listBucketResult{}, fmt.Errorf("ListObjectsV2 returned HTTP %d", resp.StatusCode)
	}
	var result listBucketResult
	if err := xml.NewDecoder(resp.Body).Decode(&result); err != nil {
		return listBucketResult{}, fmt.Errorf("decode ListObjectsV2 XML: %w", err)
	}
	return result, nil
}

func bytesDetail(count int, bytes int64) string {
	return strconv.Itoa(count) + " objects, " + strconv.FormatInt(bytes, 10) + " bytes"
}
