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

        print(f"[TerraformValidator] Tentative {meta['RetryCount'] + 1}/6")

        if meta["RetryCount"] >= 5:
            print("[TerraformValidator] Nombre max de retries atteint. Abandon.")
            exit(1)

        iac_result = results(messages)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "llm_iac.tf"), "w") as f:
                f.write(iac_result)

            init_handle = subprocess.run(
                ["terraform", "init"],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
            )

            if init_handle.returncode != 0:
                error = init_handle.stderr or init_handle.stdout
                print(f"[TerraformValidator] terraform init a échoué :\n{error}")
                meta["RetryCount"] += 1
                return messages + [{"role": "user", "content": error}], True, meta

            tf_handle = subprocess.run(
                ["terraform", "validate", "-json"],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
            )
            tf_json = json.loads(tf_handle.stdout)

            if tf_json["valid"]:
                print("[TerraformValidator] Code Terraform valide !")
                return messages, False, meta

            error = tf_json["diagnostics"][0]["detail"]
            print(f"[TerraformValidator] terraform validate a échoué :\n{error}")
            meta["RetryCount"] += 1
            return messages + [{"role": "user", "content": error}], True, meta
            
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
        completion = self.llm_client.chat.completions.create(
            max_tokens=1024, 
            model=self.model_name, 
            messages=messages
        )

        return (
            messages + [{"role": "assistant", "content": completion.choices[0].message.content}],
            False,
            meta,
        )
