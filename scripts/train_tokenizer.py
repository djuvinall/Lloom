"""Stage 0b: train the SentencePiece tokenizer (BPE + byte fallback).
Run AFTER prepare_data.py has produced data/processed/text/*.txt.
Usage: python scripts/train_tokenizer.py
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from textlm.prep import all_special_tokens
from lloom.config import load_config
from lloom.tokenizer import SPTokenizer, train_spm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/tokenizer_config.yaml")
    args = ap.parse_args()
    tok_cfg = load_config(args.config)

    input_files = sorted(Path(tok_cfg.input_dir).glob("*.txt"))
    if not input_files:
        sys.exit(f"No text in {tok_cfg.input_dir} - run scripts/prepare_data.py first")
    specials = all_special_tokens(tok_cfg)
    model_path = train_spm(input_files, tok_cfg.model_dir, tok_cfg.model_prefix,
                           tok_cfg.vocab_size, specials,
                           model_type=tok_cfg.model_type,
                           character_coverage=tok_cfg.character_coverage,
                           byte_fallback=tok_cfg.get("byte_fallback", True))
    tok = SPTokenizer(tok_cfg.model_dir, tok_cfg.model_prefix)
    print(f"trained {model_path} | vocab {tok.vocab_size} | "
          f"specials {len(specials)} (pad={tok.pad_id} eot={tok.eot_id} mask={tok.mask_id})")


if __name__ == "__main__":
    main()
