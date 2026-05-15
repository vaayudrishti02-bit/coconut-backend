# Plant Disease Inference (Rakshith)

This folder contains everything needed to run the trained plant disease classifier on a single image.

## Contents

- `test_transfer_model.py` — script to run inference on one image.
- `plant_disease_transfer_model.h5` — trained model weights.
- `labels.json` — mapping from numeric class index to class name.
- `requirements.txt` — Python dependencies.

## Setup

1. Create and activate a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

From inside this `Rakshith` folder, run:

```bash
python test_transfer_model.py "path/to/your_image.png"
```

You will see the top-2 predicted classes, the final predicted class, and its confidence.

Make sure the `plant_disease_transfer_model.h5` and `labels.json` files stay in the same folder as `test_transfer_model.py`.
