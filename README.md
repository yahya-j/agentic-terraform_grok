# Agentic Infrastructure-as-Code

  This repository contains an implementation of a workflow to enhance LLM-generated Infrastructure-as-Code (IaC) using [few-shot prompting](https://en.wikipedia.org/wiki/Prompt_engineering#In-context_learning), [pseudo-RAG](https://en.wikipedia.org/wiki/Retrieval-augmented_generation), and retry mechanism.

## Directory Structure

  ```shell
  ┌── pipeline.py            # Pipeline that integrates all steps below
  ├── steps.py               # Steps in the pipeline
  ├── results/initial.txt    # LLM output without any augmentation
  ├── results/pipelined.txt  # LLM output obtained using the pipeline
  └── Pipefile[.lock]        # Application dependencies (managed using pipenv)
  └── environment.yml        # Environment dependencies (managed using Conda/Mamba)
  ```

## Component

### 1. `FewShot` class (`steps.py`)

  This module demonstrates how to use few-shot examples to guide the LLM in generating accurate IaC.

### 2. `PseudoRAG` (`steps.py`)

  This module generates an appropriate `Terraform` provider clause based on user prompt.
  [tf–idf](https://en.wikipedia.org/wiki/Tf%E2%80%93idf) method is used for classififing the prompt.
  The generated cluase is prefilled onto `messages`.

### 3. `TerraformValidator` (`steps.py`)

  This module validates the generated IaC and retries if the output is incomplete or invalid.

## Installation

### Prerequisites

  - Python 3.12
  - Terraform CLI installed and added to PATH

### Steps

  1. Clone the repository:

      ```shell
      git clone https://github.com/pbrit/iac-agentic.git
      ```

  2. Create a fresh environment using `conda` or `mamba` from `envrionment.yml`

      ```shell
      micromamba create -f environment.yml
      micromamba activate iac-agentic
      ```

  3. Install dependecies using `pipenv`

      ```shell
      pipenv install
      ```

## Usage

  ```shell
  # Drop into virtualenv
  pipenv shell

  export ANTHROPIC_API_KEY=<REPLACE WITH ANTHROPIC_API_KEY>
  python ./main.py
  ```

## Example

  ```python
  import anthropic
  from pipeline import Pipeline
  from steps import FewShot, LLMClient, PseudoRAG, TerraformValidator, UserPrompt

  model_name = "claude-3-5-haiku-latest"

  llm_client = anthropic.Anthropic()

  user_prompt = "Deploy 3 VMs with at least 16 CPUs and 64GB across in 3 availability zones in the Netherlands using Azure"

  steps = [
      FewShot(),
      UserPrompt(),
      PseudoRAG(),
      LLMClient(llm_client, model_name),
      TerraformValidator(),
  ]

  pipeline = Pipeline(steps)
  result = pipeline.run(user_prompt)

  print(result)
  ```

## Validating Terraform Syntax

  The retry mechanism uses `terraform validate -json` to check the IaC syntax.

## Contributing

  1. Fork the repository.
  2. Run `pre-commit install`
  3. Create a new branch for your feature or bugfix.
  4. Submit a pull request with a detailed description of your changes.

## License

  This repository is licensed under the MIT License. See `LICENSE` for details.
