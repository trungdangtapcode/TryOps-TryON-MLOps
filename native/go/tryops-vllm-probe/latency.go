package main

import "time"

func ms(duration time.Duration) float64 {
	return float64(duration.Microseconds()) / 1000.0
}

func percentile(values []float64, q float64) float64 {
	if len(values) == 0 {
		return 0
	}
	if len(values) == 1 {
		return values[0]
	}
	if q <= 0 {
		return values[0]
	}
	if q >= 1 {
		return values[len(values)-1]
	}
	index := int(float64(len(values)-1) * q)
	return values[index]
}
