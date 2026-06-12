package main

import (
	"fmt"
	"os"
	"strings"

	"gopkg.in/yaml.v3"
)

func loadCompose(path string) (composeFile, error) {
	body, err := os.ReadFile(path)
	if err != nil {
		return composeFile{}, err
	}
	var compose composeFile
	if err := yaml.Unmarshal(body, &compose); err != nil {
		return composeFile{}, err
	}
	compose.Raw = string(body)
	if len(compose.Services) == 0 {
		return composeFile{}, fmt.Errorf("compose file has no services")
	}
	return compose, nil
}

func (refs *secretRefs) UnmarshalYAML(node *yaml.Node) error {
	values := []string{}
	switch node.Kind {
	case yaml.SequenceNode:
		for _, item := range node.Content {
			if item.Kind == yaml.ScalarNode {
				values = append(values, item.Value)
				continue
			}
			if item.Kind == yaml.MappingNode {
				for index := 0; index+1 < len(item.Content); index += 2 {
					if item.Content[index].Value == "source" {
						values = append(values, item.Content[index+1].Value)
						break
					}
				}
			}
		}
	case 0:
	default:
		return fmt.Errorf("unsupported secrets YAML node kind %v", node.Kind)
	}
	*refs = values
	return nil
}

func (env *environmentMap) UnmarshalYAML(node *yaml.Node) error {
	values := map[string]string{}
	switch node.Kind {
	case yaml.MappingNode:
		for index := 0; index+1 < len(node.Content); index += 2 {
			key := node.Content[index].Value
			value := node.Content[index+1].Value
			values[key] = value
		}
	case yaml.SequenceNode:
		for _, item := range node.Content {
			key, value, found := strings.Cut(item.Value, "=")
			if !found {
				values[item.Value] = ""
				continue
			}
			values[key] = value
		}
	case 0:
	default:
		return fmt.Errorf("unsupported environment YAML node kind %v", node.Kind)
	}
	*env = values
	return nil
}

func (depends *dependsOnMap) UnmarshalYAML(node *yaml.Node) error {
	values := map[string]string{}
	switch node.Kind {
	case yaml.MappingNode:
		for index := 0; index+1 < len(node.Content); index += 2 {
			serviceName := node.Content[index].Value
			condition := "service_started"
			value := node.Content[index+1]
			if value.Kind == yaml.MappingNode {
				for nested := 0; nested+1 < len(value.Content); nested += 2 {
					if value.Content[nested].Value == "condition" {
						condition = value.Content[nested+1].Value
						break
					}
				}
			} else if value.Kind == yaml.ScalarNode && value.Value != "" {
				condition = value.Value
			}
			values[serviceName] = condition
		}
	case yaml.SequenceNode:
		for _, item := range node.Content {
			values[item.Value] = "service_started"
		}
	case 0:
	default:
		return fmt.Errorf("unsupported depends_on YAML node kind %v", node.Kind)
	}
	*depends = values
	return nil
}
