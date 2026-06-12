#include <algorithm>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace {

std::string read_file(const std::string& path) {
  std::ifstream input(path);
  if (!input) {
    return "";
  }
  std::ostringstream out;
  out << input.rdbuf();
  return out.str();
}

bool contains(const std::string& text, const std::string& needle) {
  return text.find(needle) != std::string::npos;
}

int count_occurrences(const std::string& text, const std::string& needle) {
  int count = 0;
  std::size_t pos = 0;
  while ((pos = text.find(needle, pos)) != std::string::npos) {
    ++count;
    pos += needle.size();
  }
  return count;
}

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (const char ch : value) {
    switch (ch) {
      case '\\':
        out << "\\\\";
        break;
      case '"':
        out << "\\\"";
        break;
      case '\n':
        out << "\\n";
        break;
      case '\r':
        out << "\\r";
        break;
      case '\t':
        out << "\\t";
        break;
      default:
        out << ch;
        break;
    }
  }
  return out.str();
}

void require_contains(
    const std::string& text,
    const std::string& needle,
    const std::string& reason,
    std::vector<std::string>& reasons) {
  if (!contains(text, needle)) {
    reasons.push_back(reason);
  }
}

void emit_report(
    bool passed,
    int manifest_count,
    int canary_step_count,
    int service_count,
    const std::vector<std::string>& reasons) {
  std::cout << "{";
  std::cout << "\"schema_version\":\"tryops.native_gitops.v1\",";
  std::cout << "\"engine\":{\"name\":\"tryops_gitops\",\"language\":\"cpp\",\"version\":\"0.1.0\"},";
  std::cout << "\"passed\":" << (passed ? "true" : "false") << ",";
  std::cout << "\"manifest_count\":" << manifest_count << ",";
  std::cout << "\"canary_step_count\":" << canary_step_count << ",";
  std::cout << "\"service_count\":" << service_count << ",";
  std::cout << "\"reasons\":[";
  for (std::size_t index = 0; index < reasons.size(); ++index) {
    if (index > 0) {
      std::cout << ",";
    }
    std::cout << "\"" << json_escape(reasons[index]) << "\"";
  }
  std::cout << "]}";
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 3) {
    std::cerr << "usage: tryops_gitops_cli <gitops_dir> <candidate_id>\n";
    return 1;
  }
  const std::string dir = argv[1];
  const std::string candidate_id = argv[2];
  const std::string application = read_file(dir + "/application.yaml");
  const std::string rollout = read_file(dir + "/rollout.yaml");
  const std::string services = read_file(dir + "/services.yaml");
  const std::string kustomization = read_file(dir + "/kustomization.yaml");

  std::vector<std::string> reasons;
  if (application.empty()) {
    reasons.push_back("application.yaml is missing or empty");
  }
  if (rollout.empty()) {
    reasons.push_back("rollout.yaml is missing or empty");
  }
  if (services.empty()) {
    reasons.push_back("services.yaml is missing or empty");
  }
  if (kustomization.empty()) {
    reasons.push_back("kustomization.yaml is missing or empty");
  }

  require_contains(application, "apiVersion: argoproj.io/v1alpha1", "Application apiVersion is not argoproj.io/v1alpha1", reasons);
  require_contains(application, "kind: Application", "Application kind is missing", reasons);
  require_contains(application, "repoURL:", "Application source.repoURL is missing", reasons);
  require_contains(application, "targetRevision:", "Application source.targetRevision is missing", reasons);
  require_contains(application, "destination:", "Application destination is missing", reasons);
  require_contains(application, "syncPolicy:", "Application syncPolicy is missing", reasons);
  require_contains(application, "CreateNamespace=true", "Application CreateNamespace sync option is missing", reasons);

  require_contains(rollout, "apiVersion: argoproj.io/v1alpha1", "Rollout apiVersion is not argoproj.io/v1alpha1", reasons);
  require_contains(rollout, "kind: Rollout", "Rollout kind is missing", reasons);
  require_contains(rollout, "strategy:", "Rollout strategy is missing", reasons);
  require_contains(rollout, "canary:", "Rollout canary strategy is missing", reasons);
  require_contains(rollout, "stableService:", "Rollout stableService is missing", reasons);
  require_contains(rollout, "canaryService:", "Rollout canaryService is missing", reasons);
  require_contains(rollout, "steps:", "Rollout canary steps are missing", reasons);
  require_contains(rollout, "setWeight:", "Rollout canary setWeight step is missing", reasons);
  require_contains(rollout, "pause:", "Rollout canary pause step is missing", reasons);

  require_contains(services, "kind: Service", "Service manifests are missing", reasons);
  require_contains(kustomization, "kind: Kustomization", "Kustomization kind is missing", reasons);
  require_contains(kustomization, "application.yaml", "Kustomization does not reference application.yaml", reasons);
  require_contains(kustomization, "rollout.yaml", "Kustomization does not reference rollout.yaml", reasons);
  require_contains(kustomization, "services.yaml", "Kustomization does not reference services.yaml", reasons);

  const std::string candidate_label = "tryops.io/candidate-id: " + candidate_id;
  require_contains(application, candidate_label, "Application candidate label is missing", reasons);
  require_contains(rollout, candidate_label, "Rollout candidate label is missing", reasons);
  require_contains(services, candidate_label, "Service candidate label is missing", reasons);

  const int manifest_count = (!application.empty() ? 1 : 0) + (!rollout.empty() ? 1 : 0) +
                             (!services.empty() ? 1 : 0) + (!kustomization.empty() ? 1 : 0);
  const int canary_step_count = count_occurrences(rollout, "setWeight:") + count_occurrences(rollout, "pause:");
  const int service_count = count_occurrences(services, "kind: Service");
  if (canary_step_count < 3) {
    reasons.push_back("Rollout canary strategy has fewer than three setWeight/pause steps");
  }
  if (service_count < 2) {
    reasons.push_back("stable and canary Service manifests are both required");
  }

  const bool passed = reasons.empty();
  emit_report(passed, manifest_count, canary_step_count, service_count, reasons);
  return passed ? 0 : 2;
}
