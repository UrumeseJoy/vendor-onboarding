"""Which Gemini model is fast, reliable and has quota right now?

Run from the backend folder:
    python -m scripts.check_gemini                      # the default candidates
    python -m scripts.check_gemini gemini-3.5-flash     # or name the models
    python -m scripts.check_gemini --repeat 3

Sends a tiny request to each model (a few of your daily requests) and prints the latency or the error.
"""

import argparse

from app import llm

DEFAULT_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-flash-lite-latest"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", nargs="*", default=DEFAULT_MODELS)
    parser.add_argument("--repeat", type=int, default=2, help="requests per model (default 2)")
    args = parser.parse_args()

    for model in args.models:
        print(model)
        for attempt in range(1, args.repeat + 1):
            try:
                seconds, reply = llm.ping(model)
                print(f"  {attempt}: OK  {seconds:5.1f}s  (reply: {reply[:20]!r})")
            except Exception as error:  # show every kind of failure
                print(f"  {attempt}: FAIL  {llm.error_summary(error)}")


if __name__ == "__main__":
    main()
