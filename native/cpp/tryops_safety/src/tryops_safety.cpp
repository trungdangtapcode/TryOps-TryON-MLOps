#include "tryops_safety.hpp"

#include <algorithm>
#include <cctype>
#include <regex>
#include <vector>

namespace tryops {
namespace {

struct Rule {
  std::regex pattern;
  std::string category;
  double weight;
};

std::string to_lower(const std::string& s) {
  std::string out(s.size(), '\0');
  std::transform(s.begin(), s.end(), out.begin(),
                 [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
  return out;
}

const std::vector<Rule>& rules() {
  static const std::vector<Rule> kRules = [] {
    const auto opt = std::regex::optimize | std::regex::icase;
    std::vector<Rule> r;
    // --- prompt injection / instruction override ---
    r.push_back({std::regex(R"(ignore (all |the )?(previous|above|prior|earlier) (instructions|prompts?|messages?))", opt), "injection", 0.6});
    r.push_back({std::regex(R"(disregard (all |the )?(previous|above|prior) (instructions|rules))", opt), "injection", 0.6});
    r.push_back({std::regex(R"(forget (everything|all|your) (instructions|prior|previous))", opt), "injection", 0.5});
    r.push_back({std::regex(R"(you are (now|no longer)\b)", opt), "injection", 0.4});
    r.push_back({std::regex(R"(\b(jailbreak|do anything now|\bDAN\b)\b)", opt), "injection", 0.6});
    r.push_back({std::regex(R"(pretend (you are|to be) (an? )?(unfiltered|uncensored|evil))", opt), "injection", 0.5});
    r.push_back({std::regex(R"(developer mode|sudo mode|admin override)", opt), "injection", 0.4});
    // --- system-prompt / data exfiltration ---
    r.push_back({std::regex(R"((reveal|show|print|repeat|leak|output) (me )?(your |the )?(initial |original |hidden )?(system )?(prompt|instructions|rules))", opt), "exfiltration", 0.6});
    r.push_back({std::regex(R"(repeat (the words|everything) (above|before))", opt), "exfiltration", 0.5});
    r.push_back({std::regex(R"(what (are|were) your (initial |original )?(instructions|system prompt))", opt), "exfiltration", 0.5});
    // --- abusive / toxic (kept clinical) ---
    r.push_back({std::regex(R"(\b(kill|murder|harm|hurt) (yourself|themselves|them|him|her|people)\b)", opt), "toxicity", 0.7});
    r.push_back({std::regex(R"(\b(idiot|moron|stupid|worthless|pathetic)\b)", opt), "toxicity", 0.3});
    r.push_back({std::regex(R"(\b(hate|despise) (you|them|all)\b)", opt), "toxicity", 0.3});
    return r;
  }();
  return kRules;
}

}  // namespace

SafetyReport classify(const std::string& text, const SafetyThresholds& thresholds) {
  SafetyReport rep;
  const std::string lowered = to_lower(text);
  double score = 0.0;

  for (const auto& rule : rules()) {
    auto begin = std::sregex_iterator(lowered.begin(), lowered.end(), rule.pattern);
    auto end = std::sregex_iterator();
    int hits = 0;
    for (auto it = begin; it != end; ++it) {
      hits += 1;
    }
    if (hits > 0) {
      rep.categories[rule.category] += hits;
      if (rule.category == "injection") rep.injection_hits += hits;
      else if (rule.category == "exfiltration") rep.exfiltration_hits += hits;
      else if (rule.category == "toxicity") rep.toxicity_hits += hits;
      // diminishing returns: first hit full weight, repeats half.
      score += rule.weight + (hits - 1) * (rule.weight * 0.5);
    }
  }

  // saturate to [0, 1]
  rep.risk_score = score >= 1.0 ? 1.0 : score;
  if (rep.risk_score >= thresholds.block) {
    rep.verdict = "block";
  } else if (rep.risk_score >= thresholds.flag) {
    rep.verdict = "flag";
  } else {
    rep.verdict = "allow";
  }
  return rep;
}

}  // namespace tryops
