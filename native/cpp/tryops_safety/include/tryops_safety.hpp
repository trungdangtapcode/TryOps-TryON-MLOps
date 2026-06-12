// TryOps native content-safety gate.
//
// A fast, deterministic pre-LLM screen that scores untrusted prompt text for
// prompt-injection, system-prompt exfiltration, and abusive/toxic content, then
// returns an allow / flag / block verdict. Runs in C++ on the request hot path
// so unsafe inputs are stopped before they reach the model. Heuristic by design
// (pattern + lexicon based) and meant to complement, not replace, a model-based
// classifier — but it is cheap, explainable, and reproducible.
#ifndef TRYOPS_SAFETY_HPP
#define TRYOPS_SAFETY_HPP

#include <map>
#include <string>

namespace tryops {

struct SafetyThresholds {
  double flag = 0.4;
  double block = 0.8;
};

struct SafetyReport {
  std::map<std::string, int> categories;  // category -> match count
  int injection_hits = 0;
  int exfiltration_hits = 0;
  int toxicity_hits = 0;
  double risk_score = 0.0;   // 0..1 (saturating)
  std::string verdict;       // "allow" | "flag" | "block"
};

// Score `text` and apply thresholds to produce a verdict.
SafetyReport classify(const std::string& text,
                      const SafetyThresholds& thresholds = SafetyThresholds{});

}  // namespace tryops

#endif  // TRYOPS_SAFETY_HPP
