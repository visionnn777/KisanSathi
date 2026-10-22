# ml/

The disease model is saved here by `python -m scripts.download_model` (run from `backend/`).

- Model: [wambugu71/crop_leaf_diseases_vit](https://huggingface.co/wambugu71/crop_leaf_diseases_vit) — maize, potato, rice, wheat + an "Invalid" class.
- Saved to: `ml/model/wambugu71__crop_leaf_diseases_vit/` (about 25 MB).
- `ml/model/` is in `.gitignore`: every laptop that runs the demo downloads its own copy once. Never commit it.
