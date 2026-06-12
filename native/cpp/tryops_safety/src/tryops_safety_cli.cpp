// Reads untrusted prompt text on stdin, scores it, prints a JSON verdict.
// Exit: 0 allow, 1 flag, 2 block (so a gateway can branch on exit code).
#include "tryops_safety.hpp"

#include <iostream>
#include <sstream>
#include <string>

int main(int argc, char** argv) {
  tryops::SafetyThresholds th;
  for (int i = 1; i < argc; ++i) {
    const std::string a = argv[i];
    if (a == "--flag" && i + 1 < argc) th.flag = std::atof(argv[++i]);
    else if (a == "--block" && i + 1 < argc) th.block = std::atof(argv[++i]);
  }

  std::ostringstream buffer;
  buffer << std::cin.rdbuf();
  const tryops::SafetyReport r = tryops::classify(buffer.str(), th);

  std::ostringstream score;
  score.setf(std::ios::fixed);
  score.precision(4);
  score << r.risk_score;

  std::cout << "{";
  std::cout << "\"verdict\":\"" << r.verdict << "\",";
  std::cout << "\"risk_score\":" << score.str() << ",";
  std::cout << "\"injection_hits\":" << r.injection_hits << ",";
  std::cout << "\"exfiltration_hits\":" << r.exfiltration_hits << ",";
  std::cout << "\"toxicity_hits\":" << r.toxicity_hits << ",";
  std::cout << "\"categories\":{";
  bool first = true;
  for (const auto& kv : r.categories) {
    if (!first) std::cout << ",";
    first = false;
    std::cout << "\"" << kv.first << "\":" << kv.second;
  }
  std::cout << "}}";
  std::cout << "\n";

  if (r.verdict == "block") return 2;
  if (r.verdict == "flag") return 1;
  return 0;
}
