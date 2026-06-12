#include "tryops_gguf_preflight.hpp"

#include <iostream>
#include <string>

int main(int argc, char** argv) {
  if (argc < 2) {
    std::cerr << "usage: tryops_gguf_preflight_cli <model.gguf> [--llama-cli llama-cli]\n";
    return 1;
  }

  std::string model_path = argv[1];
  std::string llama_cli = "llama-cli";
  for (int index = 2; index < argc; ++index) {
    const std::string arg = argv[index];
    if (arg == "--llama-cli" && index + 1 < argc) {
      llama_cli = argv[++index];
    } else {
      std::cerr << "unknown argument: " << arg << "\n";
      return 1;
    }
  }

  const auto report = tryops::gguf_preflight::inspect_file(model_path, llama_cli);
  std::cout << tryops::gguf_preflight::render_json(report) << "\n";
  return report.passed ? 0 : 2;
}
