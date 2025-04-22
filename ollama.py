import json
import requests
import sys


facts = ["some facts: ", "I need ideas."]


def main(prompt: str) -> str:
    with requests.Session().post(
        "http://127.0.0.1:11434/api/chat",
        json={
            "model": "deepseek-v2",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant. You are terse and professional unless asked otherwise. When messaged you should always pose abstract enough questions in order to help the other party figure out their problem.",
                },
                {"role": "user", "content": prompt},
            ],
        },
        stream=True,
    ) as resp:
        for line in resp.iter_lines():
            if line:
                yield json.loads(line.decode("utf-8"))


if __name__ == "__main__":
    while True:
        message = input(">> ")
        print("\n")

        if message.startswith("fact: "):
            facts.append(message)
            continue

        for line_idx, line in enumerate(main("(" + ", ".join(facts) + "); " + message)):
            sym = "<< " if 0 == line_idx else ""
            print(sym + line.get("message", {}).get("content"), end="", flush=True)

        print("\n\n--\n")
