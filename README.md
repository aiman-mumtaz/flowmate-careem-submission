# FlowMate — AI Design Companion

A lightweight AI design companion built for the Careem Product Designer screening challenge. It turns unstructured product/design notes into user problems, needs, flows, three alternative layout directions, UI copy, usability risks, and questions for the designer.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export GROQ_API_KEY="your_key_here"
streamlit run app.py
```

The app includes a deterministic 200-record synthetic Careem scenario dataset. Choose a feature, customer context, and research-note example from the dropdowns, or download the complete dataset as CSV. The selected note is previewed below its dropdown. These records are fictional, not Careem research. The [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) is provided as a public reference only; the app does not upload or process external files. For live generation, set `GROQ_API_KEY` in your environment or Streamlit secrets; the Streamlit secret takes precedence if both are set. The default Groq model is `openai/gpt-oss-120b`; override it with `GROQ_MODEL` if your account uses another available model.

## Deploy publicly

1. Create a public GitHub repository and upload `app.py`, `requirements.txt`, and this README.
2. Open Streamlit Community Cloud and create an app from the repository.
3. In the app's Secrets settings add:

```toml
GROQ_API_KEY = "your_key_here"
GROQ_MODEL = "openai/gpt-oss-120b"
```

4. Deploy and open the generated public URL.

## Design rationale

FlowMate intentionally generates **three directions** instead of one answer. This keeps the designer in control and makes AI useful for divergent exploration rather than replacing design judgment.

The output is structured around a simple loop:

**Understand → Explore → Make usable → Human decides**

## Submission materials

- Prototype document and run instructions: this README and `app.py`.
- Public dataset: [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
- The interactive prototype can be shared publicly by deploying this project to Streamlit Community Cloud.

## Privacy

Use only public, dummy, or synthetic information. Do not paste confidential company, customer, employee, or proprietary research data into the prototype.
