# ==============================================================================
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# ==============================================================================

import json
import os
import subprocess
import tempfile

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Concat last messages from "assistant
def results(messages):
    result = []
    for message in messages[::-1]:
        if message["role"] != "assistant":
            break

        result.insert(0, message["content"])

    return "".join(result)


class TerraformValidator:
    def get_messages(self, messages, _, meta):
        if not meta.get("AlreadyRun"):
            meta["AlreadyRun"] = True
            meta["RetryCount"] = 0

        if meta["RetryCount"] >= 5:
            print("Bail")
            exit(1)

        iac_result = results(messages)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "llm_iac.tf"), "w") as iac_file:
                iac_file.write(iac_result)

            try:
                subprocess.run(
                    ["terraform", "init"],
                    cwd=tmp_dir,
                    check=True,
                )

                tf_handle = subprocess.run(
                    ["terraform", "validate", "-json"],
                    cwd=tmp_dir,
                    capture_output=True,
                    check=False,
                    text=True,
                )

                tf_json_status = json.loads(tf_handle.stdout)

                if tf_json_status["valid"]:
                    return messages, False, meta

                tf_error_diagnostics = tf_json_status["diagnostics"][0]["detail"]
                tf_retry_prompot = f"{tf_error_diagnostics}"

                meta["RetryCount"] += 1

                return (
                    messages + [{"role": "user", "content": tf_retry_prompot}],
                    True,
                    meta,
                )

            except subprocess.CalledProcessError as e:
                print("Terraform init failed", e)
            except json.JSONDecodeError as e:
                print("Malformed JSON", e)


class PseudoRAG:
    terraform_providers = {
        "azure": {
            "name": "azurerm",
            "keywords": [
                "azure",
            ],
        },
        "aws": {
            "name": "aws",
            "keywords": [
                "aws",
                "amazon",
                "amazon web services",
            ],
        },
        "gcp": {
            "name": "google",
            "keywords": [
                "gcp",
                "google cloud",
            ],
        },
    }

    def __init__(self):
        # Compute text corpus
        self.corpus = {
            "data": [],
            "provider": [],
        }

        for _, provider in self.terraform_providers.items():
            for keyword in provider["keywords"]:
                self.corpus["data"].append(keyword.lower())
                self.corpus["provider"].append(provider["name"])

        self.vectorizer = TfidfVectorizer()
        self.tfidf_matrix = self.vectorizer.fit_transform(self.corpus["data"])

    def get_messages(self, messages, user_prompt, meta):
        user_prompt_vector = self.vectorizer.transform([user_prompt])
        scores = cosine_similarity(user_prompt_vector, self.tfidf_matrix).tolist()[0]
        max_score = max(scores)
        max_score_index = scores.index(max_score)
        provider_name = self.corpus["provider"][max_score_index]

        message = {
            "role": "assistant",
            "content": f"""
                    provider "{provider_name}" {{
                        features {{}}
                    }}""",
        }

        return messages + [message], False, meta


class FewShot:
    messages = [
        {
            "role": "user",
            "content": "Create an Ubuntu VM with 4 CPUs and 16GB RAM on AWS in the us-west-2 region.",
        },
        {
            "role": "assistant",
            "content": """
            resource "aws_instance" "vm" {
                ami           = "ami-0abcdef1234567890"
                instance_type = "t2.xlarge"
                availability_zone = "us-west-2a"
            }
            """,
        },
        {
            "role": "user",
            "content": "Deploy an S3 bucket with versioning enabled in the ap-southeast-1 region.",
        },
        {
            "role": "assistant",
            "content": """
            resource "aws_s3_bucket" "example" {
                bucket = "example-bucket"
                versioning {
                    enabled = true
                }
                region = "ap-southeast-1"
            }
            """,
        },
    ]

    def get_messages(self, messages, _, meta):
        if meta.get("AlreadyRun"):
            return messages, False, meta

        meta["AlreadyRun"] = True

        return messages + self.messages, False, meta


class UserPrompt:
    def get_messages(self, messages, user_prompt, meta):
        if meta.get("AlreadyRun"):
            return messages, False, meta

        message = {"role": "user", "content": user_prompt}
        meta["AlreadyRun"] = True

        return messages + [message], False, meta


class LLMClient:
    def __init__(self, llm_client, model_name):
        self.llm_client = llm_client
        self.model_name = model_name

    def get_messages(self, messages, _, meta):
        completion = self.llm_client.messages.create(
            max_tokens=1024, model=self.model_name, messages=messages
        )

        return (
            messages + [{"role": "assistant", "content": completion.content[0].text}],
            False,
            meta,
        )
